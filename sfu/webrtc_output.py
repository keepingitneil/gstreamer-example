import asyncio
from sfu.media import OutputMedia
from sfu.participant import WebsocketParticipant

from gi.repository import Gst
from sfu.gst_utils import link_many
from gi.repository import GstWebRTC
from gi.repository import GstSdp
from sfu.gst_utils import send_eos_and_wait, wait_for_pending_state_none
import threading
import time


class WebrtcOutput(OutputMedia):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.media_pipeline = kwargs['media_pipeline']
        ws = kwargs['ws']
        participant_id = kwargs['participant_id']

        self.participant = WebsocketParticipant(participant_id=participant_id)
        self.add_participant_handler()
        self.participant.set_ws(ws)
        self.input = None
        self.webrtcbin = None
        self.elements = []
        self.pipeline = None
        self.signal_connections = []
        self.tee_pad_links = []

    def add_participant_handler(self):
        class Handler:
            async def handle_payload(payload):
                try:
                    media_id = payload['media_id']
                    if media_id != self.media_id:
                        return
                except KeyError:
                    return

                try:
                    payload_type = payload['type']
                except KeyError:
                    return

                if payload_type == 'answer':
                    self.handle_answer(payload)
                    return

                if payload_type == 'ice_candidate':
                    self.handle_remote_ice_candidate(payload)
                    return

            async def handle_close():
                await self.media_pipeline.remove_output_media(self)

        self.participant.add_handler(Handler)

    def set_input_media(self, input_obj):
        self.input = input_obj

    def get_input_media(self):
        return self.input

    async def add_to_pipeline(self, pipeline):
        print('add to pipeline')

        self.webrtcbin = Gst.ElementFactory.make('webrtcbin')
        pipeline.add(self.webrtcbin)
        self.webrtcbin.set_property('stun-server', 'stun://stun.l.google.com:19302')
        self.signal_connections.extend([
            self.webrtcbin.connect('on-negotiation-needed', self.on_negotiation_needed),
            self.webrtcbin.connect('on-ice-candidate', self.on_ice_candidate),
            ])

        try:
            tees = [t[1] async for t in self.input.get_tees()]
        except Exception as e:
            raise e

        print('got tees')

        for t in tees:
            queue = Gst.ElementFactory.make('queue')
            queue.set_property('leaky', 1)
            queue.set_property('silent', True)
            pipeline.add(queue)
            tee_pad = t.get_request_pad('src_%u')
            queue_pad = queue.get_static_pad('sink')
            tee_pad.link(queue_pad)
            self.tee_pad_links.append((t, tee_pad, queue_pad))
            link_many(queue, self.webrtcbin)
            queue.set_state(Gst.State.PLAYING)
            self.elements.append(queue)

        self.webrtcbin.set_state(Gst.State.PLAYING)

        self.pipeline = pipeline

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element)
        element.emit('create-offer', None, promise)

    def on_offer_created(self, promise, element):

        promise.wait()
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        sdp_text = offer.sdp.as_text()

        msg = {
                'media_id': self.media_id,
                'type': 'offer',
                'sdp': sdp_text,
                }
        if offer.type != GstWebRTC.WebRTCSDPType.OFFER:
            return

        set_local_description_promise = Gst.Promise.new()
        element.emit('set-local-description', offer, set_local_description_promise)
        promise.wait()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.participant.send_payload(msg))
        except Exception:
            pass

    def on_ice_candidate(self, element, mlineindex, candidate):

        payload = {
                'media_id': self.media_id,
                'type': 'ice_candidate',
                'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}
                }
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.participant.send_payload(payload))
        except Exception:
            pass

    def on_new_transceiver(self, el, trans):
        # trans.direction = GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY
        pass

    def handle_remote_ice_candidate(self, payload):
        ice = payload['ice']
        candidate = ice['candidate']
        sdpmlineindex = ice['sdpMLineIndex']
        self.webrtcbin.emit('add-ice-candidate', sdpmlineindex, candidate)

    def handle_answer(self, payload):
        sdp = payload['sdp']
        res, sdpmsg = GstSdp.SDPMessage.new()
        GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
        answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)

        def did_set_remote_description(prom):
            pass

        promise = Gst.Promise.new_with_change_func(did_set_remote_description)
        self.webrtcbin.emit('set-remote-description', answer, promise)

    async def handle_payload(self, payload):
        action = payload['action']
        if action == 'ice_candidate':
            self.handle_remote_ice_candidate(payload)
        elif action == 'answer':
            self.handle_answer(payload)

    async def remove_from_pipeline(self, pipeline):
        try:
            if self.webrtcbin:
                for c in self.signal_connections:
                    self.webrtcbin.disconnect(c)

            for (tee, tee_pad, el_pad) in self.tee_pad_links:
                tee_pad.unlink(el_pad)
                tee.release_request_pad(tee_pad)

            def set_to_null(element):
                element.set_state(Gst.State.NULL)

            def wait_for_null(element):
                (_, state, _) = element.get_state(0.1)
                tries = 0
                while state != Gst.State.NULL:
                    tries += 1
                    time.sleep(0.1)
                    if tries == 3:
                        break
                    (_, state, _) = element.get_state(0.1)

            for e in self.elements:
                e.unlink(self.webrtcbin)
                t = threading.Thread(target=set_to_null, args=[e])
                t.start()
                wait_for_null(e)

            if self.webrtcbin:
                t = threading.Thread(target=set_to_null, args=[self.webrtcbin])
                t.start()
                wait_for_null(self.webrtcbin)

            for e in self.elements:
                self.pipeline.remove(e)

            if self.webrtcbin:
                pipeline.remove(self.webrtcbin)

        except Exception:
            pass

    async def cleanup(self):
        await self.participant.cleanup()
