import asyncio
from gi.repository import Gst
from subprocess import call
import threading
from threading import Thread
import queue


class MediaPipeline(object):
    def __init__(self):
        self._pipeline = Gst.Pipeline.new('pipeline')
        self._pipeline.set_state(Gst.State.PLAYING)
        self._input_medias = []
        self._output_medias = []
        self.coro_queue = queue.Queue(maxsize=200)
        self.event_loop = asyncio.new_event_loop()
        t = Thread(target=self.thread_entry)
        t.start()

    def thread_entry(self):
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self.queue_loop())

    async def queue_loop(self):
        while True:
            try:
                fn, args = self.coro_queue.get()
                self.coro_queue.task_done()
                await asyncio.wait_for(fn(*args), 10)
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

    async def cleanup(self):
        for m in self.medias:
            await m.remove_from_pipeline(self._pipeline)

        self.pipeline.set_state(Gst.State.NULL)

    async def add_input_media(self, input_media):
        try:
            self.coro_queue.put_nowait((self._add_input_media, [input_media]))
        except queue.Full:
            pass
        except Exception:
            pass

    async def _add_input_media(self, media):
        print('adding input media: {}'.format(media))
        try:
            self._input_medias.append(media)

            await media.add_to_pipeline(self._pipeline)
        except Exception:
            self._input_medias = [m for m in self._input_medias if m != media]

            try:
                await media.remove_from_pipeline(self._pipeline)
            except Exception:
                pass

    async def remove_input_media(self, media):
        try:
            outputs_to_cleanup = [o for o in self._output_medias if o.get_input_media() == media]
            for o in outputs_to_cleanup:
                await self.remove_output_media(o)

            await media.cleanup()
            self.coro_queue.put_nowait((self._remove_input_media, [media]))
        except queue.Full:
            pass

    async def _remove_input_media(self, media):
        try:
            await media.remove_from_pipeline(self._pipeline)
            self._input_medias = [m for m in self._input_medias if m != media]
        except Exception:
            pass

    def get_input_media(self, media_id):

        for m in self._input_medias:
            if m.media_id == media_id:
                return m

        return None

    async def add_output_media(self, output_media, input_media_id):
        try:
            self.coro_queue.put_nowait((self._add_output_media, [output_media, input_media_id]))
        except queue.Full:
            pass

    async def _add_output_media(self, output_media, input_media_id):
        print('adding output media: {}'.format(output_media))
        try:
            self._output_medias.append(output_media)
            input_media = [m for m in self._input_medias if m.media_id == input_media_id][0]

            output_media.set_input_media(input_media)
            await output_media.add_to_pipeline(self._pipeline)
        except Exception:
            pass
            self._output_medias = [m for m in self._output_medias if m != output_media]
            try:
                await output_media.remove_from_pipeline(self._pipeline)
            except Exception:
                pass

    def remove_output_media_id(self, media_id):
        try:
            output_media = [m for m in self._output_medias if m.media_id == media_id][0]
            self.remove_output_media(output_media)
        except Exception:
            pass

    async def remove_output_media(self, media):
        try:
            await media.cleanup()
            self.coro_queue.put_nowait((self._remove_output_media, [media]))
        except queue.Full:
            pass

    async def _remove_output_media(self, media):
        try:
            await media.remove_from_pipeline(self._pipeline)
            self._output_medias = [m for m in self._output_medias if m != media]
        except Exception:
            pass

    def get_all_input_medias(self):
        return self._input_medias

    def get_all_output_medias(self):
        return self._output_medias

    async def cleanup_input_media_with_matcher(self, matcher_fn):
        try:
            input_medias_to_cleanup = [i for i in self._input_medias if matcher_fn(i)]

            for m in input_medias_to_cleanup:
                await self.remove_input_media(m)

        except Exception:
            pass

    def generate_dotfile(self, name):
        Gst.debug_bin_to_dot_file(self._pipeline, Gst.DebugGraphDetails(15), '{}'.format(name))
        call([
            'dot',
            '-T',
            'png',
            '/tmp/dot_files/{}.dot'.format(name),
            '-o',
            '/tmp/dot_files/{}.png'.format(name)])


