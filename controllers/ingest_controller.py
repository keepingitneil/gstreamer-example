class IngestController(object):
    def __init__(self, **kwargs):
        self.media_pipeline = kwargs['media_pipeline']

    def cleanup(self):
        pass
