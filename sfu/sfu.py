import asyncio
import gi
import traceback
from subprocess import call
from collections import OrderedDict, defaultdict
import json
from gi.repository import Gst


class SFU(object):
    def __init__(self, **kwargs):
        self.medias = []
        self.pipeline = Gst.Pipeline.new('sfu-pipeline')
        self.pipeline.set_state(Gst.State.PLAYING)

    def generate_dot(self, name):
        print('generating dotfile: {}'.format(name))
        Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails(15), '{}'.format(name))
        call(['dot', '-T', 'png', '/tmp/dot_files/{}.dot'.format(name), '-o', '/tmp/dot_files/{}.png'.format(name)])

    async def add_media(self, media):
        self.medias.append(media)
        await media.add_to_pipeline(self.pipeline)

    async def add_output(self, output_media):
        await output_media.add_to_pipeline(self.pipeline)

    def get_media_infos(self):
        return [x.get_info() for x in self.medias]

    def get_media(self, media_id):
        medias = [m for m in self.medias if m.media_id==media_id]
        if len(medias):
            return medias[0]

        raise KeyError('')

    async def cleanup(self):
        print('cleaning up sfu')
        for m in self.medias:
            print('cleaning up media: {}'.format(m.media_id))
            await m.cleanup()

        print('cleaned up medias')

        self.pipeline.set_state(Gst.State.NULL)
