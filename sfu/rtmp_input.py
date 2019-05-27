import asyncio
from sfu.gst_utils import link_many, add_many, set_many_to_state, create_capsfilter
from gi.repository import Gst
from sfu.media import InputMedia
from threading import Timer


class RTMPInput(InputMedia):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.media_pipeline = kwargs['media_pipeline']

        self.video_src = Gst.ElementFactory.make('videotestsrc')
        self.video_src.set_property('is-live', True)
        self.video_src_capsfilter = create_capsfilter('video/x-raw,framerate=10/1,width=320,height=240')

        self.video_queue = Gst.ElementFactory.make('queue')

        self.video_queue.set_property('silent', True)

        self.video_enc = Gst.ElementFactory.make('vp8enc')
        self.video_enc.set_property('cpu-used', 3)
        self.video_enc.set_property('end-usage', 1)
        self.video_enc.set_property('target-bitrate', 1500000)

        self.video_pay = Gst.ElementFactory.make('rtpvp8pay')
        self.video_pay_capsfilter = create_capsfilter('application/x-rtp,media=video,clock-rate=90000,payload=96')
        self.video_tee = Gst.ElementFactory.make('tee')
        self.video_tee.set_property('allow-not-linked', True)
        self.video_fakesink = Gst.ElementFactory.make('fakesink')
        self.video_frame_timeout = None

        self.audio_src = Gst.ElementFactory.make('audiotestsrc')
        self.audio_src.set_property('is-live', True)

        self.audio_queue = Gst.ElementFactory.make('queue')
        self.audio_queue.set_property('silent', True)

        self.audio_rate = Gst.ElementFactory.make('audioresample')
        self.audio_convert = Gst.ElementFactory.make('audioconvert')
        self.audio_enc = Gst.ElementFactory.make('opusenc')
        self.audio_pay = Gst.ElementFactory.make('rtpopuspay')
        self.audio_pay_capsfilter = create_capsfilter('application/x-rtp,media=audio,clock-rate=48000,payload=97')
        self.audio_tee = Gst.ElementFactory.make('tee')
        self.audio_tee.set_property('allow-not-linked', True)
        self.audio_fakesink = Gst.ElementFactory.make('fakesink')

        self.video_tee_future = asyncio.Future(loop=self.media_pipeline.event_loop)
        self.audio_tee_future = asyncio.Future(loop=self.media_pipeline.event_loop)

    def setup_pipeline(self, pipeline):
        print('setup pipeline')
        add_many(
                pipeline,
                self.video_src,
                self.video_src_capsfilter,
                self.video_queue,
                self.video_enc,
                self.video_pay,
                self.video_pay_capsfilter,
                self.video_tee,
                self.video_fakesink
                )

        link_many(
                self.video_src,
                self.video_src_capsfilter,
                self.video_queue,
                self.video_enc,
                self.video_pay,
                self.video_pay_capsfilter,
                self.video_tee,
                self.video_fakesink
                )
        set_many_to_state(
                Gst.State.PLAYING,
                self.video_src,
                self.video_src_capsfilter,
                self.video_queue,
                self.video_enc,
                self.video_pay,
                self.video_pay_capsfilter,
                self.video_tee,
                self.video_fakesink
                )

        self.video_tee_future.set_result(self.video_tee)
        print('added video')

        add_many(
                pipeline,
                self.audio_src,
                self.audio_queue,
                self.audio_rate,
                self.audio_convert,
                self.audio_enc,
                self.audio_pay,
                self.audio_pay_capsfilter,
                self.audio_tee,
                self.audio_fakesink
                )
        link_many(
                self.audio_src,
                self.audio_queue,
                self.audio_rate,
                self.audio_convert,
                self.audio_enc,
                self.audio_pay,
                self.audio_pay_capsfilter,
                self.audio_tee,
                self.audio_fakesink
                )
        set_many_to_state(
                Gst.State.PLAYING,
                self.audio_src,
                self.audio_queue,
                self.audio_rate,
                self.audio_convert,
                self.audio_enc,
                self.audio_pay,
                self.audio_pay_capsfilter,
                self.audio_tee,
                self.audio_fakesink
                )

        self.audio_tee_future.set_result(self.audio_tee)
        print('added audio')

    async def add_to_pipeline(self, pipeline):
        print('rtmp add to pipeline')
        self.setup_pipeline(pipeline)
        await self.video_tee_future
        await self.audio_tee_future
        print('rtmp added to pipeline')

    async def get_tees(self):
        audio_tee = await self.audio_tee_future
        video_tee = await self.video_tee_future
        yield ('audio', audio_tee)
        yield ('video', video_tee)

    async def remove_from_pipeline(self, pipeline):
        self.rtmp_src.set_state(Gst.State.NULL)
        all_els = [
                self.video_src,
                self.video_src_capsfilter,
                self.video_queue,
                self.video_enc,
                self.video_pay,
                self.video_pay_capsfilter,
                self.video_tee,
                self.video_fakesink,

                self.audio_src,
                self.audio_queue,
                self.audio_rate,
                self.audio_convert,
                self.audio_enc,
                self.audio_pay,
                self.audio_pay_capsfilter,
                self.audio_tee,
                self.audio_fakesink,
                ]
        els_to_remove = [el for el in all_els if el is not None]
        for el in els_to_remove:
            el.set_state(Gst.State.NULL)
            pipeline.remove(el)

    async def cleanup(self):
        pass
