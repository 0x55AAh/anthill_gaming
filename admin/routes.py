# For more details about routing, see
# http://www.tornadoweb.org/en/stable/routing.html
from tornado.web import url
from . import handlers

route_patterns = [
    url(r'/test/', handlers.TestHandler, name='test'),
]
