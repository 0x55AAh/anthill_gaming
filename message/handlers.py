from anthill.platform.core.messenger.handlers import MessengerHandler
from anthill.platform.core.messenger.client import BaseClient


class User:
    def __init__(self, _id):
        self.id = _id


class Client(BaseClient):
    def get_user_serialized(self):
        pass

    async def get_friends(self, id_only=False):
        pass

    async def get_groups(self):
        pass

    async def create_group(self, group_name, group_data):
        pass

    async def delete_group(self, group_name):
        pass

    async def update_group(self, group_name, group_data):
        pass

    async def join_group(self, group_name):
        pass

    async def leave_group(self, group_name):
        pass

    async def enumerate_group(self, group, new=None):
        pass

    async def create_message(self, group, message):
        pass

    async def get_messages(self, group, message_ids):
        pass

    async def delete_messages(self, group, message_ids):
        pass

    async def update_messages(self, group, messages_data):
        pass

    async def read_messages(self, group, message_ids):
        pass

    async def forward_messages(self, group, message_ids, group_to):
        pass


class TestMessengerHandler(MessengerHandler):
    client_class = Client

    def get_client_instance(self):
        return self.client_class(user=User(1))
