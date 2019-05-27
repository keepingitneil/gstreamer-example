import os
import uuid


class BaseConfig(object):
    API_URL = 'http://sidecar:8000'
    MAX_OUTBOUND_STREAMS = 3
    HTTP_PORT = 8442
    REDIS_URL = 'redis://redis'
    INSTANCE_ID = uuid.uuid4()
    WS_PING_INTERVAL = 5


config = BaseConfig()
