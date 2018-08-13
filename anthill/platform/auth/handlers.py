from anthill.framework.conf import settings
from anthill.platform.auth.forms import AuthenticationForm
from anthill.framework.handlers.edit import FormHandler
from anthill.framework.utils.crypto import constant_time_compare
from anthill.framework.auth import (
    _get_user_session_key,
    _get_backends,
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    REDIRECT_FIELD_NAME,
    SESSION_KEY,
    load_backend
)
from functools import partial


class InvalidLoginError(Exception):
    pass


class LoginHandlerMixin:
    # access_token_key = 'access_token'

    # noinspection PyAttributeOutsideInit
    def _login(self, user, backend=None):
        """
        Persist a user id and a backend in the request. This way a user doesn't
        have to reauthenticate on every request. Note that data set during
        the anonymous session is retained when the user logs in.
        """
        session_auth_hash = ''
        if user is None:
            user = self.current_user
        if 'session_auth_hash' in user:
            session_auth_hash = user['session_auth_hash']

        if SESSION_KEY in self.session:
            if _get_user_session_key(self) != user['id'] or (
                    session_auth_hash and
                    not constant_time_compare(self.session.get(HASH_SESSION_KEY, ''), session_auth_hash)):
                # To avoid reusing another user's session, create a new, empty
                # session if the existing session corresponds to a different
                # authenticated user.
                self.session.flush()
        else:
            self.session.cycle_key()

        try:
            backend = backend or user['backend']
        except AttributeError:
            backends = _get_backends(return_tuples=True)
            if len(backends) == 1:
                _, backend = backends[0]
            else:
                raise ValueError(
                    'You have multiple authentication backends configured and '
                    'therefore must provide the `backend` argument or set the '
                    '`backend` attribute on the user.'
                )
        else:
            if not isinstance(backend, str):
                raise TypeError('backend must be a dotted import path string (got %r).' % backend)

        self.session[SESSION_KEY] = user['id']
        self.session[BACKEND_SESSION_KEY] = backend
        self.session[HASH_SESSION_KEY] = session_auth_hash
        self.current_user = user

    async def login(self, user, backend=None):
        do_login = partial(self.internal_request, 'login', 'login')
        token = await do_login(user_id=user['id'])
        if token:
            self._login(user, backend)
        else:
            self.invalid_login_error()

    def invalid_login_error(self):
        raise InvalidLoginError('Invalid token.')


class LoginHandler(LoginHandlerMixin, FormHandler):
    """
    Display the login form and handle the login action.
    """

    form_class = AuthenticationForm
    authentication_form = None
    redirect_field_name = REDIRECT_FIELD_NAME
    template_name = 'login.html'
    redirect_authenticated_user = False
    extra_context = None

    def get_success_url(self):
        url = self.get_redirect_url()
        return url or self.reverse_url(settings.LOGIN_REDIRECT_URL)

    def get_redirect_url(self):
        """Return the user-originating redirect URL."""
        redirect_to = self.get_argument(
            self.redirect_field_name,
            self.get_query_argument(self.redirect_field_name, '')
        )
        return redirect_to

    def get_form_class(self):
        return self.authentication_form or self.form_class

    async def form_valid(self, form):
        """Security check complete. Log the user in."""
        user = await form.authenticate(self.internal_request)
        try:
            await self.login(user=user)
            self.redirect(self.get_success_url())
        except InvalidLoginError as e:
            pass