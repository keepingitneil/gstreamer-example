import asyncio
import aiohttp.web as web
from config import config


class WSProxy(object):
    def __init__(self, ws, loop):
        self.ws = ws
        self.done = False
        self.msg_queue = asyncio.Queue()

    async def add_msg(self, msg):
        await self.msg_queue.put(msg)

    async def set_done(self):
        self.done = True
        await self.msg_queue.put('done')

    async def __aiter__(self):
        return self

    async def __anext__(self):
        if self.done:
            raise StopAsyncIteration

        msg = await self.msg_queue.get()
        self.msg_queue.task_done()

        if msg == 'done':
            raise StopAsyncIteration

        return msg

    async def send_json(self, payload):
        await self.ws.send_json(payload)

    async def close(self):
        await self.ws.close()


class WSServer(object):
    def __init__(self, **kwargs):
        self.app = kwargs['app']
        self.route = kwargs['route']
        self.app.add_routes([web.get(self.route, self._websocket_handler)])
        self.ws_handlers = {}

    async def new_websocket(self, ws, query, match_info):
        print('override me')

    async def _timeout_loop(self, ws):
        while True:
            if ws.closed:
                break
            await ws.send_str('ping')
            await asyncio.sleep(config.WS_PING_INTERVAL)

    async def _websocket_handler(self, request):
        try:
            ws = web.WebSocketResponse(max_msg_size=1024*1024*1)
            await ws.prepare(request)
            asyncio.ensure_future(self._timeout_loop(ws))
            ws_proxy = WSProxy(ws, asyncio.get_event_loop())
            await self.new_websocket(ws_proxy, request.query, request.match_info)
            async for msg in ws:
                await ws_proxy.add_msg(msg)

            await ws_proxy.set_done()

            return ws
        except Exception:
            pass
