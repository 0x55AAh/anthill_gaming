"""
Internal api methods for current service.

Example:

    from anthill.platform.api.internal import as_internal, InternalAPI

    @as_internal()
    async def your_internal_api_method(api: InternalAPI, *params, **options):
        # current_service = api.service
        ...
"""
from anthill.platform.api.internal import as_internal, InternalAPI
from message.routes import MESSENGER_NAMESPACE


@as_internal()
async def get_messenger_namespace(api: InternalAPI, **options):
    return MESSENGER_NAMESPACE
