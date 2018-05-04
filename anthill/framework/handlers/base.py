from tornado.web import RequestHandler as BaseRequestHandler
from tornado.websocket import WebSocketHandler as BaseWebSocketHandler
from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.http import HttpGoneError
from anthill.framework.utils.format import bytes2human
from anthill.framework.context_processors import build_context_from_context_processors
from anthill.framework.utils.json import json
from anthill.framework.conf import settings


class RequestHandler(BaseRequestHandler):
    def reverse_url(self, name, *args):
        url = super(RequestHandler, self).reverse_url(name, *args)
        return url[:-1] if url.endswith('?') else url

    def data_received(self, chunk):
        pass


class WebSocketHandler(BaseWebSocketHandler):
    def __init__(self, application, request, **kwargs):
        super(WebSocketHandler, self).__init__(application, request, **kwargs)
        self.settings.update(websocket_ping_interval=settings.WEBSOCKET_PING_INTERVAL)
        self.settings.update(websocket_ping_timeout=settings.WEBSOCKET_PING_TIMEOUT)
        self.settings.update(websocket_max_message_size=settings.WEBSOCKET_MAX_MESSAGE_SIZE)

    def on_message(self, message):
        """Handle incoming messages on the WebSocket."""
        raise NotImplementedError

    def data_received(self, chunk):
        """Implement this method to handle streamed request data."""

    def open(self, *args, **kwargs):
        """Invoked when a new WebSocket is opened."""

    def on_close(self):
        """Invoked when the WebSocket is closed."""

    def on_ping(self, data):
        """Invoked when the a ping frame is received."""

    def on_pong(self, data):
        """Invoked when the response to a ping frame is received."""

    def get_compression_options(self):
        return None


class JsonWebSocketHandler(BaseWebSocketHandler):
    def data_received(self, chunk):
        """Implement this method to handle streamed request data."""

    def on_message(self, message):
        """Handle incoming messages on the WebSocket."""
        raise NotImplementedError


class JSONHandlerMixin:
    extra_context = None

    def dumps(self, data):
        return json.dumps(data, escape_forward_slashes=False)

    async def get_context_data(self, **kwargs):
        if self.extra_context is not None:
            kwargs.update(self.extra_context)
        return kwargs

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')


class ContextMixin:
    """
    A default context mixin that passes the keyword arguments received by
    get_context_data() as the template context.
    """
    extra_context = None

    async def get_context_data(self, **kwargs):
        if self.extra_context is not None:
            kwargs.update(self.extra_context)
        kwargs.update(await build_context_from_context_processors(self.request))
        return kwargs


class RedirectMixin:
    query_string = False
    handler_name = None
    url = None

    def initialize(self, query_string=None, handler_name=None, url=None):
        if query_string is not None:
            self.query_string = query_string
        if handler_name is not None:
            self.handler_name = handler_name
        if url is not None:
            self.url = url

    def get_redirect_url(self, *args, **kwargs):
        """
        Return the URL redirect to. Keyword arguments from the URL pattern
        match generating the redirect request are provided as kwargs to this
        method.
        """
        if self.url:
            url = self.url.format(*args)
        elif self.handler_name:
            try:
                from anthill.framework.utils.urls import reverse as reverse_url
                url = reverse_url(self.handler_name, *args, **kwargs)
            except KeyError:
                return None
        else:
            return None

        request_query = self.request.query
        if request_query and self.query_string:
            url = "%s?%s" % (url, request_query)
        return url


class TemplateMixin:
    """A mixin that can be used to render a template."""
    template_name = None

    def initialize(self, template_name=None):
        if template_name is not None:
            self.template_name = template_name

    def render(self, **kwargs):
        template_name = self.get_template_name()
        return super(TemplateMixin, self).render(template_name, **kwargs)

    def get_template_namespace(self):
        from anthill.framework.apps import app
        namespace = super(TemplateMixin, self).get_template_namespace()
        namespace.update(app_version=app.version)
        namespace.update(debug=app.debug)
        namespace.update(bytes2human=bytes2human)
        return namespace

    def get_template_name(self):
        """
        Return a template name to be used for the request.
        """
        if self.template_name is None:
            raise ImproperlyConfigured(
                "TemplateMixin requires either a definition of "
                "'template_name' or an implementation of 'get_template_name()'")
        else:
            return self.template_name


class TemplateHandler(TemplateMixin, ContextMixin, RequestHandler):
    """
    Render a template. Pass keyword arguments to the context.
    """
    async def get(self, *args, **kwargs):
        context = await self.get_context_data(**kwargs)
        return self.render(**context)


class RedirectHandler(RedirectMixin, RequestHandler):
    """Provide a redirect on any GET request."""
    permanent = False

    async def get(self, *args, **kwargs):
        url = self.get_redirect_url(*args, **kwargs)
        if url:
            self.redirect(url, permanent=self.permanent)
        else:
            raise HttpGoneError

    async def head(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def options(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def put(self, *args, **kwargs):
        await self.get(*args, **kwargs)

    async def patch(self, *args, **kwargs):
        await self.get(*args, **kwargs)


class JSONHandler(JSONHandlerMixin, RequestHandler):
    async def get(self, *args, **kwargs):
        self.write(self.dumps(await self.get_context_data(**kwargs)))