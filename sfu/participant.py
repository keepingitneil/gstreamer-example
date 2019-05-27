import asyncio
import aiohttp
import json
from config import config


class Participant(object):
    def __init__(self, **kwargs):
        self.participant_id = kwargs['participant_id']
        self.handlers = set()

    async def _handle_payload(self, payload):
        print(" <<< {}".format(payload))
        await asyncio.gather(*[h.handle_payload(payload) for h in self.handlers])

    async def _handle_close(self):
        try:
            await asyncio.gather(*[h.handle_close() for h in self.handlers])
        except Exception:
            pass

    def add_handler(self, handler):
        if not hasattr(handler, 'handle_payload'):
            raise Exception('handler needs handle_payload method')

        if not hasattr(handler, 'handle_close'):
            raise Exception('handler needs handle_close method')

        self.handlers.add(handler)

    async def send_payload(self, payload):
        print(" >>> {}".format(payload))

    async def cleanup(self):
        self.handlers = set()


class WebsocketParticipant(Participant):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_task = None
        self.ws = None
        self.timeout_task = None
        self.msg_queue = asyncio.Queue(maxsize=500)
        self.msg_queue_task = asyncio.ensure_future(self.message_loop())

    def set_ws(self, ws):
        self.ws = ws
        asyncio.ensure_future(self.receive_message(ws))

    async def message_loop(self):
        while True:
            try:
                msg = await self.msg_queue.get()
                self.msg_queue.task_done()
                payload = json.loads(msg)
                await self._handle_payload(payload)
            except asyncio.CancelledError as e:
                raise e
            except Exception:
                pass

    async def reset_timeout(self):
        if self.timeout_task:
            self.timeout_task.cancel()

        async def timeout():
            try:
                await asyncio.sleep(config.WS_PING_INTERVAL * 2)

                await self.cleanup()
            except asyncio.CancelledError as e:
                raise e
            except Exception:
                return

        self.timeout_task = asyncio.ensure_future(timeout())

    async def receive_message(self, ws):

        # start the timeout
        await self.reset_timeout()

        async for msg in ws:
            try:
                await self.reset_timeout()
                if msg.type == aiohttp.WSMsgType.ERROR:
                    break

                if msg.type == aiohttp.WSMsgType.CLOSE:
                    break

                if msg.type == aiohttp.WSMsgType.TEXT:

                    if msg.data == 'ping':
                        try:
                            await ws.send_str('pong')
                        except Exception:
                            pass
                        continue

                    if msg.data == 'pong':
                        continue

                    try:
                        self.msg_queue.put_nowait(msg.data)
                    except asyncio.QueueFull:
                        pass
                        break

            except Exception:
                pass

        if self.timeout_task:
            self.timeout_task.cancel()

        self.msg_queue_task.cancel()
        self.msg_queue.put('/close')

        await self._handle_close()

    async def send_payload(self, payload):
        if self.ws is None:
            raise Exception('You need to call set_ws first')
        try:
            await super().send_payload(payload)
            await self.ws.send_json(payload)
        except Exception:
            pass

    async def close(self):
        try:
            if self.ws is None:
                return
            await asyncio.ensure_future(self.ws.close())
        except Exception:
            pass

    async def cleanup(self):
        await self.close()
        await super().cleanup()


class WebsocketClientParticipant(WebsocketParticipant):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ws_url = kwargs['ws_url']
        self.http_session = aiohttp.ClientSession()
        self.ws_task = None

    def start(self):
        self.ws_task = asyncio.ensure_future(self._start())

    async def _start(self):
        try:
            ws = await self.http_session.ws_connect(self.ws_url, timeout=5)
            self.ws = ws
            await self.receive_message(ws)
        except Exception:
            pass
            await self._handle_close()
