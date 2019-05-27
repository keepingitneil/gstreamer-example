class Media(object):
    def __init__(self, **kwargs):
        self.direction = 'not_implemented'
        self.media_id = kwargs['media_id']

    async def add_to_pipeline(self, pipeline):
        raise NotImplementedError

    """
    gets called on the media_pipeline's thread and event_loop
    """
    async def remove_from_pipeline(self, pipeline):
        raise NotImplementedError

    """
    gets called on the main thread and event_loop
    """
    async def cleanup(self):
        pass

    def get_info(self):
        return {'media_id': self.media_id}


class InputMedia(Media):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.direction = 'input'

    async def get_tees(self):
        raise NotImplementedError


class OutputMedia(Media):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.direction = 'output'

    def set_input_media(self, media):
        raise NotImplementedError

    def get_input_media(self):
        raise NotImplementedError
