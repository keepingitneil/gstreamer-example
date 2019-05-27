"""
OutboundController's resposibility is to add
output_medias into the media_pipeline
"""


class OutboundController(object):
    def __init__(self, **kwargs):
        self.media_pipeline = kwargs['media_pipeline']
