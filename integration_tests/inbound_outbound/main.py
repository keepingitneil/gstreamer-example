import aiohttp
import asyncio
from webrtc_client import WebrtcClient


async def dot(name):

    async with aiohttp.ClientSession() as session:
        async with session.get('http://rtc-ingest:8442/dotfile/?name={}'.format(name)) as resp:
            print(resp.status)
            print(await resp.text())


async def test():
    print('running test')

    await asyncio.sleep(5)

    await dot('test_1')

    print('creating clients')
    clients = []
    media_id = "123"
    for i in range(1):
        p_id = "abc_{}".format(i)
        print('creating client: {}'.format(media_id))
        ws_url = 'ws://rtc-ingest:8442/?token=abc&participant_id={}&stream_id={}'.format(p_id, media_id)
        c1 = WebrtcClient(ws_url=ws_url, media_id=media_id)
        c1.start()
        try:
            await c1.wait_for_media()
            clients.append(c1)
            print('got media for {}'.format(media_id))
        except asyncio.TimeoutError:
            print('ERROR: media timed out')
            c1.stop()

    await asyncio.sleep(5)

    asyncio.sleep(2)

    print('shutting down')
    await asyncio.sleep(5)


async def run_tests():
    print('running test 1')
    await(test())

asyncio.get_event_loop().run_until_complete(run_tests())
