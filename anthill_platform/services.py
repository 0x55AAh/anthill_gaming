import logging
from tornado.gen import coroutine

from microservices_framework.core.celery.worker import start_worker
from microservices_framework.core.servers import BaseService as _BaseService
from microservices_framework.apps.builder import app
from .utils.celery import celery

logger = logging.getLogger('app.server')


class BaseService(_BaseService):
    def get_server_kwargs(self):
        return dict(xheaders=True)

    @coroutine
    def __on_internal_receive__(self, context, method, *args, **kwargs):
        ...

    @coroutine
    def on_start(self):
        logger.info('Service \'%s\' started.' % self.name)
        with start_worker(app=celery):
            ...

    @coroutine
    def on_stop(self):
        logger.info('Service \'%s\' stopped.' % self.name)


class PlainService(BaseService):
    @coroutine
    def register_on_discovery(self):
        label = app.label
        data = app.registry_entry
        key = 'DISCOVERY_SERVICE_SECRET_KEY'

    @coroutine
    def discover(self, names=None, network=None):
        ...

    @coroutine
    def on_start(self):
        yield self.register_on_discovery()
        yield super(PlainService, self).on_start()


class AdminService(PlainService):
    ...


class RegisterNotAllowed(Exception):
    ...


class DiscoveryService(BaseService):
    @coroutine
    def register_service(self, name, data, key):
        if not self.register_allowed(key):
            raise RegisterNotAllowed
        entry = {
            name: data
        }
        # Add the entry to discovery services registry

    def register_allowed(self, key):
        if app.settings.SECRET_KEY == key:
            return True
        return False
