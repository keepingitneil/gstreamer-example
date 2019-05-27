import asyncio
import time
import gi
from config import config
from threading import Thread
import aiohttp.web as web
from media_pipeline import MediaPipeline
from controllers.ws_outbound_controller import WSOutboundController
from controllers.rtmp_ingest_controller import RTMPIngestController

gi.require_version('Gst', '1.0')
gi.require_version('GObject', '2.0')
from gi.repository import Gst, GLib
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
Gst.init(None)


def start_gi_main():
    loop = GLib.MainLoop()
    loop.run()


t = Thread(target=start_gi_main)
t.start()


while True:
    try:
        media_pipeline = MediaPipeline()

        def generate_dotfile(request):
            try:
                name = request.query['name']
                media_pipeline.generate_dotfile(name)
                return web.Response(text='Ok')
            except Exception:
                pass

        app = web.Application()

        outbound_controller = WSOutboundController(app=app, media_pipeline=media_pipeline)
        ingest_controller = RTMPIngestController(media_pipeline=media_pipeline)

        app.add_routes([web.get('/dotfile/', generate_dotfile)])
        app.add_routes([web.get('/health', outbound_controller.health)])
        web.run_app(app, port=config.HTTP_PORT, host='0.0.0.0')
    except Exception:
        asyncio.set_event_loop(asyncio.new_event_loop())
        time.sleep(5)
