from anthill.framework.handlers import TemplateHandler, RedirectHandler
from anthill.framework.core.channels.handlers.websocket import (
    WebSocketChannelHandler, JsonWebSocketChannelHandler
)
from .ui.modules import ServiceCard
import json


class AuthenticatedHandlerMixin:
    access_token_key = 'access_token'

    async def logout(self):
        self.clear_cookie(self.access_token_key)

    def get_current_user(self):
        if self.token is None:
            return None


class HomeHandler(TemplateHandler):
    template_name = 'index.html'
    extra_context = {
        'service_cards': [
            ServiceCard.Entry(title='Configuration', icon_class='icon-gear',
                              description='Configure your application dynamically', color='primary'),
            ServiceCard.Entry(title='Craft', icon_class='icon-hammer', description='Craft', color='danger'),
            ServiceCard.Entry(title='Discovery', icon_class='icon-direction',
                              description='Map each service location dynamically', color='success'),
            ServiceCard.Entry(title='DLC', icon_class='icon-cloud-download2',
                              description='Deliver downloadable content to the user', color='warning'),
            ServiceCard.Entry(title='Environment', icon_class='icon-cube',
                              description='Sandbox Test environment from Live', color='info'),
            ServiceCard.Entry(title='Events', icon_class='icon-calendar',
                              description='Compete the players with time-limited events', color='pink'),
            ServiceCard.Entry(title='Exec', icon_class='icon-circle-code',
                              description='Execute custom javascript code server-side', color='violet'),
            ServiceCard.Entry(title='Game', icon_class='icon-steam',
                              description='Manage game server instances', color='purple'),
            ServiceCard.Entry(title='Leader board', icon_class='icon-sort-numeric-asc',
                              description='See and edit player ranking', color='indigo'),
            ServiceCard.Entry(title='Login', icon_class='icon-key',
                              description='Manage user accounts, credentials and access tokens', color='blue'),
            ServiceCard.Entry(title='Market', icon_class='icon-basket', description='Market', color='teal'),
            ServiceCard.Entry(title='Messages', icon_class='icon-envelope',
                              description='Deliver messages from the user, to the user', color='green'),
            ServiceCard.Entry(title='Profiles', icon_class='icon-user',
                              description='Manage the profiles of the users', color='orange'),
            ServiceCard.Entry(title='Promo', icon_class='icon-gift',
                              description='Reward users with promo-codes', color='brown'),
            ServiceCard.Entry(title='Report', icon_class='icon-flag3',
                              description='User-submitted reports service', color='grey'),
            ServiceCard.Entry(title='Social', icon_class='icon-share3',
                              description='Manage social networks, groups and friend connections', color='slate'),
            ServiceCard.Entry(title='Store', icon_class='icon-cart',
                              description='In-App Purchasing, with server validation', color='primary'),
        ]
    }

    async def get_context_data(self, **kwargs):
        context = await super(HomeHandler, self).get_context_data(**kwargs)

        async def test_send_receive():
            from tornado.gen import sleep
            layer = get_channel_layer()
            message = {"type": "test.message"}
            await layer.send("specific.yPlPzPtO", message)
            # await sleep(1)
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()
        await test_send_receive()

        return context


class LoginHandler(TemplateHandler):
    template_name = 'login.html'

    async def post(self, *args, **kwargs):
        pass

    async def get_context_data(self, **kwargs):
        context = await super(LoginHandler, self).get_context_data(**kwargs)
        return context


class LogoutHandler(AuthenticatedHandlerMixin, RedirectHandler):
    handler_name = 'login'

    async def get(self, *args, **kwargs):
        await self.logout()
        await super(LogoutHandler, self).get(*args, **kwargs)


class DebugHandler(TemplateHandler):
    template_name = 'debug.html'

    async def get_context_data(self, **kwargs):
        context = await super(DebugHandler, self).get_context_data(**kwargs)
        return context


class TestWSHandler(WebSocketChannelHandler):
    groups = ['test', 'test1', 'test2']

    async def receive(self, message):
        """Receives message from current channel"""
        print(message)


class TestJWSHandler(JsonWebSocketChannelHandler):
    groups = ['test', 'test1', 'test2']

    async def receive_json(self, message):
        """Receives message from current channel"""
        print(message)
