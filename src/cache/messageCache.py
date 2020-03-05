"""
A temporary message queue for messages that need to be stored in the DB.
We will hold them here in a queue for a few seconds (5?-10?) and then commit them to the DB using Bulk writes.

All DB Writes, Reads, and Updates must go through this class to ensure GG is interacting with fresh data.

Part of the Gabby Gums Discord Logger.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, List

import db

import discord

log = logging.getLogger(__name__)


@dataclass
class QueuedMessage:
    message_id: int
    server_id: int
    user_id: int
    ts: datetime
    content: Optional[str]
    attachments: Optional[List[str]]
    webhook_author_name: Optional[str]
    system_pkid: Optional[str]
    member_pkid: Optional[str]
    pk_system_account_id: Optional[int]


class ReplicationQueue(deque):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_pool = kwargs['bot'].db_pool
        self.wait_time = timedelta(seconds=60*5)  # In seconds.

    def pop_next_valid_message(self) -> Optional[QueuedMessage]:

        # Messages are stored from oldest to newest. As such, just check the first message.
        if len(self) <= 0:
            return None

        message: QueuedMessage = self[0]
        if (datetime.utcnow() - message.ts) > self.wait_time:
            return self.popleft()

        return None

    def pop_all_valid_messages(self) -> Optional[List[QueuedMessage]]:

        messages = []

        while True:
            message = self.pop_next_valid_message()

            if message is None:
                break
            messages.append(message)

        if len(messages) == 0:
            return None
        else:
            return messages


    def queue_message(self, message: QueuedMessage):
        self.append(message)


    async def get_message(self, message_id: int) -> Optional[QueuedMessage]:

        # Optimize by using snowflake to determine how old the msg is and skip the queue if it's more than a few minutes old.
        message = self._get_queued_msg(message_id)
        if message is None:
            return await db.get_cached_message(self.db_pool, -1, message_id)

        return message


    def _get_queued_msg(self, message_id: int) -> Optional[QueuedMessage]:
        for message in self:
            if message.message_id == message_id:
                return message  # Assume that message_id is unique.
        return None


    async def update_message_contents(self, message_id: int, new_content: str):

        message = self._get_queued_msg(message_id)
        if message is None:
            await db.update_cached_message(self.db_pool, message_id, new_content)
            return

        message.content = new_content


    async def update_message_pk_info(self, message_id: int, system_pkid: str, member_pkid: str, pk_system_account_id: int):

        message = self._get_queued_msg(message_id)
        if message is None:
            await db.update_cached_message_pk_details(self.db_pool, -1, message_id, system_pkid, member_pkid, pk_system_account_id)
            return

        message.system_pkid = system_pkid
        message.content = member_pkid
        message.content = pk_system_account_id


    async def delete_message(self, message_id: int):

        message = self._get_queued_msg(message_id)
        if message is None:
            await db.delete_cached_message(self.db_pool, message_id)
            return

        try:
            self.remove(message)
        except ValueError:
            log.warning("Attempted to remove message that was not in the replication queue.")
