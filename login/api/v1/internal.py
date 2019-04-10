"""
Internal api methods for current service.

Example:

    from anthill.platform.api.internal import as_internal, InternalAPI

    @as_internal()
    async def your_internal_api_method(api: InternalAPI, *params, **options):
        # current_service = api.service
        ...
"""
from anthill.platform.api.internal import as_internal, InternalAPI, connector
from anthill.framework.auth import authenticate as _authenticate, get_user_model
from anthill.framework.utils.asynchronous import thread_pool_exec
from anthill.framework.utils.urls import reverse, build_absolute_uri
from typing import Optional
import functools

User = get_user_model()


def request_profile():
    return functools.partial(connector.internal_request, 'profile')


PAGINATED_BY = 50


async def _get_user_data(user: User, include_profile: bool = False, **options) -> Optional[dict]:
    if user is not None:
        data = user.dump().data
        if include_profile:
            data['profile'] = await user.get_profile()
        return data


async def _get_user(user_id: str, include_profile: bool = False, **options) -> dict:
    user = await thread_pool_exec(User.query.get, user_id)
    return await _get_user_data(user, include_profile)


async def _get_users(request=None, include_profiles: bool = False,
                     pagination: int = None, page: int = None, filter_by: dict = None, **options) -> dict:
    filter_by = filter_by or {}
    pagination_kwargs = {
        'page': page,
        'per_page': pagination,
        'max_per_page': pagination
    }
    users = await thread_pool_exec(User.query.filter_by, **filter_by)
    users = users.paginate(request, **pagination_kwargs)
    users_data = User.dump_many(users.items).data
    if include_profiles:
        profiles_data = await request_profile()(
            'get_profiles', user_ids=[u['id'] for u in users_data])
        profiles_data_dict = {p['user_id']: p for p in profiles_data['data']}
        for user in users_data:
            user['profile'] = profiles_data_dict[user['id']]
    return {'data': users_data}


@as_internal()
async def get_user(
        api: InternalAPI,
        user_id: str,
        include_profile: bool = False,
        **options) -> dict:
    return await _get_user(user_id, include_profile)


@as_internal()
async def get_users(
        api: InternalAPI,
        request=None,
        include_profiles: bool = False,
        pagination: int = None,
        page: int = None,
        filter_by: dict = None,
        **options) -> dict:
    return await _get_users(request, include_profiles, pagination, page, filter_by)


@as_internal()
async def authenticate(api: InternalAPI, credentials: dict, **options) -> dict:
    user = await _authenticate(request=None, **credentials)  # None or User
    data = await _get_user_data(user)  # None or user data dict
    return data or {'error': 'User not found'}


@as_internal()
async def logout(api: InternalAPI, token: str, **options) -> str:
    pass


@as_internal()
async def get_login_url(api: InternalAPI, **options) -> str:
    path = reverse('login')
    host_url = api.service.app.registry_entry['external']
    return build_absolute_uri(host_url, path)
