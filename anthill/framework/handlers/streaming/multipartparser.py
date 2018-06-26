"""
Multi-part parsing for file uploads.

Exposes one class, ``MultiPartParser``, which feeds chunks of uploaded data to
file upload handlers for processing.
"""
from anthill.framework.core.files.uploadhandler import StopFutureHandlers
from anthill.framework.utils.encoding import force_text
from tornado.httputil import HTTPHeaders
# noinspection PyProtectedMember
from tornado.httputil import _parse_header
from tornado.log import gen_log
from anthill.framework.conf import settings
import cgi


PHASE_BOUNDARY = 1
PHASE_HEADERS = 2
PHASE_BODY = 3


class MultiPartParserError(Exception):
    pass


class StreamingMultiPartParser:
    """
    Streaming multipart/form-data parser

    Most common use case is to create a parser in `prepare` method of `.RequestHandler`
    decorated with stream_request_body using self as the delegate and pass a chunk of data
    to `data_received` method.
    """
    def __init__(self, headers, upload_handlers, encoding=None):
        """
        Initialize the MultiPartParser object.

        :request:
            The standard ``headers`` dictionary in tornado request object.
        :upload_handlers:
            A list of UploadHandler instances that perform operations on the
            uploaded data.
        """
        # Content-Type should contain multipart and the boundary information.
        content_type = headers.get('Content-Type', '')
        if not content_type.startswith('multipart/'):
            raise MultiPartParserError('Invalid Content-Type: %s' % content_type)

        # Parse the header to get the boundary to split the parts.
        ctypes, opts = _parse_header(content_type)
        boundary = opts.get('boundary')
        if not boundary or not cgi.valid_boundary(boundary):
            raise MultiPartParserError('Invalid boundary in multipart: %s' % boundary.decode())

        # Content-Length should contain the length of the body we are about
        # to receive.
        try:
            content_length = int(headers.get('Content-Length', 0))
        except (ValueError, TypeError):
            content_length = 0

        if content_length < 0:
            # This means we shouldn't continue...raise an error.
            raise MultiPartParserError("Invalid content length: %r" % content_length)

        self.boundary = boundary
        if self.boundary.startswith('"') and self.boundary.endswith('"'):
            self.boundary = self.boundary[1:-1]

        self._boundary_delimiter = "--{}\r\n".format(self.boundary).encode('ascii')
        self._end_boundary = "\r\n--{}--\r\n".format(self.boundary).encode('ascii')
        self._boundary = self.boundary.encode('ascii')

        self.upload_handlers = upload_handlers
        self.content_length = content_length
        self.encoding = encoding or settings.DEFAULT_CHARSET

        self.current_phase = PHASE_BOUNDARY  # Initial phase

        self._buffer = None
        self._data_size = 0
        self._field_name = None
        self._skip_field_name = None

        self.files = {}
        self.variables = {}

    async def upload_start(self):
        for i, handler in enumerate(self.upload_handlers):
            await handler.upload_start(self.content_length, self._boundary, self.encoding)

    async def new_file(self, field_name, file_name, content_type, content_length,
                       charset=None, content_type_extra=None):
        for i, handler in enumerate(self.upload_handlers):
            try:
                await handler.new_file(
                    field_name, file_name, content_type, content_length,
                    charset, content_type_extra)
            except StopFutureHandlers:
                self._skip_field_name = (field_name, i + 1)
                break

    async def receive_data_chunk(self, raw_data):
        for i, handler in enumerate(self.upload_handlers):
            if self._skip_field_name == (self._field_name, i):
                break
            chunk = await handler.receive_data_chunk(raw_data)
            if chunk is None:
                # Don't continue if the chunk received by the handler is None.
                break

    async def complete_file(self):
        for i, handler in enumerate(self.upload_handlers):
            if self._skip_field_name == (self._field_name, i):
                break
            file_obj = await handler.complete_file(self._data_size)
            if file_obj and self._field_name is not None:
                # If it returns a file object, then set the files dict.
                self.files.setdefault(self._field_name, []).append(file_obj)

    async def upload_complete(self):
        for i, handler in enumerate(self.upload_handlers):
            await handler.upload_complete()

    async def data_received(self, chunk):
        """
        Receive chunk of multipart/form-data.
        """
        if self._buffer is None:
            await self.upload_start()

        if not self._buffer:
            self._buffer = chunk
        else:
            self._buffer += chunk

        while True:
            if self.current_phase == PHASE_BOUNDARY:
                if len(self._buffer) > len(self._boundary_delimiter):
                    if self._buffer.startswith(self._boundary_delimiter):
                        self.current_phase = PHASE_HEADERS
                        self._buffer = self._buffer[len(self._boundary_delimiter):]
                    elif self._buffer.startswith(self._end_boundary):
                        await self.complete_file()
                        return
                    else:
                        gen_log.warning("Invalid multipart/form-data")
                        return
                else:
                    # Wait for next chunk
                    return

            if self.current_phase == PHASE_HEADERS:
                if b"\r\n\r\n" in self._buffer:
                    headers, remaining_part = self._buffer.split(b"\r\n\r\n", 1)

                    if headers:
                        headers = HTTPHeaders.parse(headers.decode(self.encoding))
                    else:
                        gen_log.warning("multipart/form-data missing headers")
                        return

                    disposition_header = headers.get("Content-Disposition", "")
                    disposition, disposition_params = _parse_header(disposition_header)
                    if disposition != "form-data":
                        gen_log.warning("Invalid multipart/form-data")
                        return

                    self._buffer = remaining_part

                    self.current_phase = PHASE_BODY
                    self._data_size = 0  # Reset data size counter before enter PHASE_BODY phase

                    try:
                        field_name = disposition_params['name'].strip()
                    except (KeyError, IndexError, AttributeError):
                        return
                    field_name = force_text(field_name, self.encoding, errors='replace')
                    self._field_name = field_name

                    file_name = disposition_params.get('filename')
                    if file_name:
                        file_name = force_text(file_name, self.encoding, errors='replace')
                    if not file_name:
                        return

                    content_type = headers.get('Content-Type', '')
                    content_type, content_type_extra = _parse_header(content_type)
                    charset = content_type_extra.get('charset')

                    try:
                        content_length = int(headers.get('Content-Length', 0))
                    except (TypeError, ValueError):
                        content_length = None

                    await self.new_file(
                        field_name, file_name, content_type, content_length,
                        charset, content_type_extra)
                else:
                    # Wait for all headers for current file
                    return

            if self.current_phase == PHASE_BODY:
                if self._boundary_delimiter in self._buffer:
                    data, remaining_data = self._buffer.split(self._boundary_delimiter, 1)
                    self._buffer = remaining_data
                    self._data_size += len(data[:-2])
                    await self.receive_data_chunk(data[:-2])
                    await self.complete_file()
                    self._field_name = None

                    self.current_phase = PHASE_HEADERS
                    continue
                elif self._end_boundary in self._buffer:
                    remaining_data = self._buffer.split(self._end_boundary)[0]
                    self._data_size += len(remaining_data)
                    await self.receive_data_chunk(remaining_data)
                    await self.complete_file()
                    self._field_name = None
                    return
                else:
                    if self._buffer:
                        self._data_size += len(self._buffer)
                        await self.receive_data_chunk(self._buffer)
                    self._buffer = b""
                    return
