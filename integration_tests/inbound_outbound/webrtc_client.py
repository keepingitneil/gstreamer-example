import gi
import aiohttp
import asyncio
import time
import traceback
import json
import uuid
from aiohttp import web

gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)
from gi.repository import GstSdp
from gi.repository import GstWebRTC

PING_INTERVAL = 10

http_session = aiohttp.ClientSession()


class WebrtcClient(object):
    def __init__(self, **kwargs):
        self.ws_url = kwargs['ws_url']
        self.media_id = kwargs['media_id']
        self.ws_task = None
        self.ws = None
        self.webrtcbin = Gst.ElementFactory.make('webrtcbin')
        self.webrtcbin.connect('on-ice-candidate', self.on_ice_candidate)
        self.webrtcbin.connect('pad-added', self.pad_added)
        self.webrtcbin.connect('pad-removed', self.pad_removed)
        self.webrtcbin.connect('no-more-pads', self.no_more_pads)
        self.pipeline = Gst.Pipeline.new('main')
        self.setup_pipeline()
        self.video_future = asyncio.Future()
        self.audio_future = asyncio.Future()

    def setup_pipeline(self):
        self.pipeline.add(self.webrtcbin)
        self.pipeline.set_state(Gst.State.PLAYING)

    async def wait_for_media(self):
        await self.video_future
        await self.audio_future

    async def stop(self):
        self.pipeline.set_state(Gst.State.NULL)
        await self.ws.close()

    async def send_payload(self, payload):
        print('webrtc_client >>> {}'.format(payload))
        await self.ws.send_json(payload)

    async def handle_remote_ice_candidate(self, payload):
        ice = payload['ice']
        candidate = ice['candidate']
        sdpmlineindex = ice['sdpMLineIndex']
        self.webrtcbin.emit('add-ice-candidate', sdpmlineindex, candidate)

    async def handle_offer(self, payload):
        sdp = payload['sdp']
        res, sdpmsg = GstSdp.SDPMessage.new()
        GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
        offer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdpmsg)

        def did_create_answer_promise(prom):
            prom_res = prom.wait()
            print('client did_create answer')
            if prom_res != Gst.PromiseResult.REPLIED:
                print('ERROR setting answer')
                return

            reply = prom.get_reply()
            answer = reply.get_value('answer')

            try:
                set_local_description_promise = Gst.Promise.new()
                self.webrtcbin.emit('set-local-description', answer, set_local_description_promise)
                set_local_description_promise.interrupt()
            except Exception:
                traceback.print_exc()

            payload = {
                    'media_id': self.media_id,
                    'type': 'answer',
                    'sdp': answer.sdp.as_text(),
                    }
            asyncio.new_event_loop().run_until_complete(self.send_payload(payload))

        if offer.type != GstWebRTC.WebRTCSDPType.OFFER:
            print('TODO: is this right?')
            return

        def did_set_remote_description(prom):
            prom_res = prom.wait()
            if prom_res != Gst.PromiseResult.REPLIED:
                print('ERROR setting remote description')
                return

            create_answer_promise = Gst.Promise.new_with_change_func(did_create_answer_promise)
            self.webrtcbin.emit('create_answer', None, create_answer_promise)

        remote_description_promise = Gst.Promise.new_with_change_func(did_set_remote_description)
        self.webrtcbin.emit('set-remote-description', offer, remote_description_promise)

    def on_ice_candidate(self, element, mlineindex, candidate):
        payload = {
                'media_id': self.media_id,
                'type': 'ice_candidate',
                'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}
                }
        asyncio.new_event_loop().run_until_complete(self.send_payload(payload))

    def pad_added(self, element, pad):
        print('WOAH pad_added')
        caps_string = pad.get_current_caps().to_string()
        if 'video' in caps_string:
            video_fakesink = Gst.ElementFactory.make('fakesink')
            self.pipeline.add(video_fakesink)
            video_sink = video_fakesink.get_static_pad('sink')
            pad.link(video_sink)
            video_fakesink.set_state(Gst.State.PLAYING)
            video_fakesink.set_property('signal-handoffs', True)
            handoff_connection = None

            def handoff(*args):
                self.video_future.set_result(True)
                video_fakesink.disconnect(handoff_connection)
            handoff_connection = video_fakesink.connect('handoff', handoff)

        elif 'audio' in caps_string:
            audio_fakesink = Gst.ElementFactory.make('fakesink')
            self.pipeline.add(audio_fakesink)
            audio_sink = audio_fakesink.get_static_pad('sink')
            pad.link(audio_sink)
            audio_fakesink.set_state(Gst.State.PLAYING)
            audio_fakesink.set_property('signal-handoffs', True)
            handoff_connection = None
            def handoff(*args):
                self.audio_future.set_result(True)
                audio_fakesink.disconnect(handoff_connection)
            handoff_connection = audio_fakesink.connect('handoff', handoff)

    def pad_removed(self, element, pad):
        print('ERROR pad_removed')

    def no_more_pads(self, element):
        pass

    async def _handle_payload(self, payload):
        print('webrtc_client <<< {}'.format(payload))

        try:
            payload_type = payload['type']
        except KeyError:
            return

        if payload_type == 'medias':
            try:
                media_id = payload['data'][0]['media_id']
                req_id = str(uuid.uuid4())
                await self.send_payload({'action': 'subscribe', 'media_id': media_id, 'req_id': req_id})
            except Exception:
                traceback.print_exc()
                pass
            return

        if payload_type == 'offer':
            try:
                await self.handle_offer(payload)
            except Exception:
                traceback.print_exc()
            return

        if payload_type == 'ice_candidate':
            await self.handle_remote_ice_candidate(payload)
            return

    def start(self):
        self.ws_task = asyncio.ensure_future(self._start())

    async def start_ping_loop(self, ws):
        while True:
            try:
                if ws.closed:
                    break
                await ws.send_str('ping')
                await asyncio.sleep(PING_INTERVAL)
            except Exception:
                traceback.print_exc()

    async def _start(self):
        try:
            print('connecting to ws...')
            ws = await http_session.ws_connect(self.ws_url)
            print('connected to ws')
            self.ws = ws
            self.ping_task = asyncio.ensure_future(self.start_ping_loop(ws))
            await self.receive_message(ws)
        except Exception:
            traceback.print_exc()

    async def receive_message(self, ws):
        async for msg in ws:
            try:

                if msg.type == aiohttp.WSMsgType.ERROR:
                    break

                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data in ['ping', 'pong']:
                        continue

                    try:
                        payload = json.loads(msg.data)
                    except json.JSONDecodeError:
                        print('not valid json')
                        continue

                    await self._handle_payload(payload)
            except Exception:
                traceback.print_exc()
