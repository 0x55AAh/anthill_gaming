from tornado.web import stream_request_body
from anthill.framework.conf import settings
from anthill.framework.core.files.uploadhandler import load_handler
from anthill.framework.handlers import TemplateHandler
from anthill.framework.handlers.streaming.multipartparser import StreamingMultiPartParser


@stream_request_body
class UploadFileStreamHandler(TemplateHandler):
    max_upload_size = settings.FILE_UPLOAD_MAX_BODY_SIZE
    multipart_parser_class = StreamingMultiPartParser
    template_name = None

    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.multipart_parser = None
        self._upload_handlers = None
        self._content_type = None

    async def prepare(self):
        self._content_type = self.request.headers.get('Content-Type', '')
        if self._content_type.startswith('multipart/form-data'):
            self.request.connection.set_max_body_size(self.max_upload_size)
            self.multipart_parser = self.multipart_parser_class(
                self.request.headers, self.upload_handlers)
            self.request.files = self.multipart_parser.files

    async def data_received(self, chunk):
        if self._content_type.startswith('multipart/form-data'):
            await self.multipart_parser.data_received(chunk)

    def _initialize_handlers(self):
        self._upload_handlers = list(map(
            lambda x: load_handler(x), settings.FILE_UPLOAD_HANDLERS))

    @property
    def upload_handlers(self):
        if not self._upload_handlers:
            # If there are no upload handlers defined, initialize them from settings.
            self._initialize_handlers()
        return self._upload_handlers

    @upload_handlers.setter
    def upload_handlers(self, upload_handlers):
        if hasattr(self.request, 'files'):
            raise AttributeError("You cannot set the upload handlers after the upload has been processed.")
        self._upload_handlers = upload_handlers

    async def post(self):
        """
        Example:
        >>> from anthill.framework.core.files.storage import default_storage
        >>>
        >>> for files in self.request.files.values():
        >>>    for f in files:
        >>>        default_storage.save(f.name, f.file)
        >>>        f.close()
        """
        # Finalize uploading
        await self.multipart_parser.upload_complete()