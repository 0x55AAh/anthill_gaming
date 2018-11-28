from anthill.platform.api.internal import RequestTimeoutError


class ServiceContextMixin:
    """
    Put current request handler into special service context.
    Need for url kwarg `name` to identify target service.
    """

    async def get_service_metadata(self):
        service_name = self.path_kwargs['name']
        return await self.internal_request(
            service_name, method='get_service_metadata')

    async def get_context_data(self, **kwargs):
        context = await super().get_context_data(**kwargs)
        try:
            metadata = await self.get_service_metadata()
        except RequestTimeoutError:
            pass  # ¯\_(ツ)_/¯
        else:
            context.update(metadata=metadata)
        return context
