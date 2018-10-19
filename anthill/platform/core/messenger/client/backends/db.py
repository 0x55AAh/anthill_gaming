from anthill.platform.core.messenger.client.backends.base import BaseClient
from typing import Optional


class Client(BaseClient):
    def get_user_serialized(self) -> dict:
        """Returns user as dict object."""
        return self.user.to_dict()

    async def get_friends(self, id_only: bool=False) -> list:
        pass

    async def get_groups(self) -> list:
        pass

    async def create_group(self, group_name: str, group_data: dict) -> str:
        pass

    async def delete_group(self, group_name: str) -> None:
        pass

    async def update_group(self, group_name: str, group_data: dict) -> None:
        pass

    async def join_group(self, group_name: str) -> None:
        pass

    async def leave_group(self, group_name: str) -> None:
        pass

    async def enumerate_group(self, group: str, new=None) -> list:
        pass

    async def create_message(self, group: str, message: dict) -> str:
        pass

    async def get_messages(self, group: str, message_ids: list) -> list:
        pass

    async def delete_messages(self, group: str, message_ids: list):
        pass

    async def update_messages(self, group: str, messages_data: dict):
        pass

    async def read_messages(self, group: str, message_ids: list):
        pass

    async def forward_messages(self, group: str, message_ids: list, group_to: str):
        pass