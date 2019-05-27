import asyncio
from controllers.ingest_controller import IngestController
from sfu.rtmp_input import RTMPInput
import aiohttp


class RTMPIngestController(IngestController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        asyncio.ensure_future(self._create_media())

        timeout = aiohttp.ClientTimeout(total=10)
        self.client = aiohttp.ClientSession(timeout=timeout, raise_for_status=True)

    async def _create_media(self):
        location = "not_used"
        media_id = "123"
        rtmp_input = RTMPInput(media_id=media_id, location=location, media_pipeline=self.media_pipeline)
        await self.media_pipeline.add_input_media(rtmp_input)
