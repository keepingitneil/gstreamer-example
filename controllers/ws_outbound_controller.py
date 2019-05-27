from controllers.outbound_controller import OutboundController
from ws.ws_server import WSServer
from sfu.webrtc_output import WebrtcOutput
from aiohttp import web
from config import config


class WSOutboundController(OutboundController, WSServer):
    def __init__(self, **kwargs):
        WSServer.__init__(self, **kwargs, route='/')
        OutboundController.__init__(self, **kwargs)

    async def new_websocket(self, ws, query, match_info):
        try:
            participant_id = query['participant_id']
            _ = query['token']
            stream_id = query['stream_id']
        except KeyError:
            await ws.close()
            return ws

        try:
            output = WebrtcOutput(ws=ws, participant_id=participant_id, media_id=stream_id, media_pipeline=self.media_pipeline)
            await self.media_pipeline.add_output_media(output, stream_id)
        except Exception:
            return

    async def health(self, request):
        total_len = len(self.media_pipeline.get_all_output_medias())

        if total_len > config.MAX_OUTBOUND_STREAMS:
            return web.Response(text='unhealthy', status=503)

        return web.Response(text='ok')
