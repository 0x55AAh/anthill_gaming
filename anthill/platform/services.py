from anthill.framework.core.servers import BaseService as _BaseService
from anthill.platform.utils.celery import CeleryMixin
from anthill.platform.api.internal import JSONRPCInternalConnection
from anthill.framework.utils.geoip import GeoIP2
from functools import partial
import logging

logger = logging.getLogger('anthill.server')


class ServiceAlreadyRegistered(Exception):
    def __init__(self, name, message=None):
        super().__init__(message)
        self.name = name


class BaseService(CeleryMixin, _BaseService):
    internal_api_connection_class = JSONRPCInternalConnection

    def __init__(self, handlers=None, default_host=None, transforms=None, **kwargs):
        super().__init__(handlers, default_host, transforms, **kwargs)
        self.internal_connection = self.internal_api_connection_class(service=self)
        self.gis = GeoIP2() if getattr(self.config, 'GEOIP_PATH', None) else None

    def setup(self) -> None:
        log_streaming_config = getattr(self.config, 'LOG_STREAMING', None)
        if log_streaming_config:
            from tornado.web import url
            from anthill.framework.handlers import LogStreamingHandler
            custom_handler_class = log_streaming_config.get('handler', {}).get('class')
            if not custom_handler_class:
                handler_class = LogStreamingHandler
            else:
                from anthill.framework.utils.module_loading import import_string
                handler_class = import_string(custom_handler_class)
            handler_kwargs = log_streaming_config.get('handler', {}).get('kwargs', dict(handler_name='anthill'))
            url_name = log_streaming_config.get('name', 'log')
            url_path = log_streaming_config.get('path', '/log/').rstrip('/') + '/'
            self.add_handlers(r'^(.*)$', [
                url(r'^%s?$' % url_path, handler_class, kwargs=handler_kwargs, name=url_name),
            ])
        super().setup()

    def get_server_kwargs(self) -> dict:
        kwargs = super().get_server_kwargs()
        kwargs.update(xheaders=True)
        return kwargs

    async def on_start(self) -> None:
        logger.info('Service `%s` started.' % self.name)
        await self.internal_connection.connect()
        self.start_celery()

    async def on_stop(self) -> None:
        logger.info('Service `%s` stopped.' % self.name)
        await self.internal_connection.disconnect()


class PlainService(BaseService):
    auto_register_on_discovery = True

    def __init__(self, handlers=None, default_host=None, transforms=None, **kwargs):
        super().__init__(handlers, default_host, transforms, **kwargs)
        self.discovery_request = partial(self.internal_connection.request, 'discovery')

    async def register_on_discovery(self) -> None:
        kwargs = {'name': self.name, 'networks': self.app.registry_entry}
        await self.discovery_request('set_service_bulk', **kwargs)

    async def unregister_on_discovery(self) -> None:
        await self.discovery_request('remove_service', name=self.name)

    async def discover(self, name: str, network: str=None) -> dict:
        return await self.discovery_request('get_service', name=name, network=network)

    async def on_start(self) -> None:
        await super().on_start()
        if self.auto_register_on_discovery:
            await self.register_on_discovery()

    async def on_stop(self) -> None:
        if self.auto_register_on_discovery:
            await self.unregister_on_discovery()
        await super().on_stop()


class AdminService(PlainService):
    pass


class DiscoveryService(BaseService):
    cleanup_storage_on_stop = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_start(self) -> None:
        await super().on_start()
        await self.setup_storage()
        await self.setup_services()

    async def on_stop(self) -> None:
        await super().on_stop()
        if self.cleanup_storage_on_stop:
            await self.remove_services()

    async def setup_services(self) -> None:
        registry = self.app.registry
        for service_name, networks in registry.items():
            await self.setup_service(service_name, networks)

    async def remove_services(self) -> None:
        for service_name in await self.get_registered_services():
            await self.remove_service(service_name)

    async def list_services(self) -> list:
        raise NotImplementedError

    async def setup_service(self, name: str, networks: dict) -> None:
        raise NotImplementedError

    async def remove_service(self, name: str) -> None:
        raise NotImplementedError

    async def is_service_exists(self, name: str) -> bool:
        raise NotImplementedError

    async def get_service(self, name: str, networks: list=None) -> dict:
        raise NotImplementedError

    async def setup_storage(self) -> None:
        raise NotImplementedError

    # Request for register service

    async def create_request_for_register_service(self, name: str, networks: dict) -> str:
        raise NotImplementedError

    async def delete_request_for_register_service(self, request_id: str) -> None:
        raise NotImplementedError

    async def get_request_for_register_service(self, request_id: str) -> tuple:
        raise NotImplementedError

    async def get_requests_for_register_service(self) -> dict:
        raise NotImplementedError

    async def register_service(self, request_id: str) -> None:
        name, networks = await self.get_request_for_register_service(request_id)
        if name in await self.get_registered_services():
            raise ServiceAlreadyRegistered(name)
        await self.setup_service(name, networks)

    async def unregister_service(self, name: str) -> None:
        await self.remove_service(name)

    # /Request for register service
