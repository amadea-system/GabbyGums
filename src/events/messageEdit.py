"""
Cog for the on_raw_message_edit event.
Logs from this event include:
    When a message is edited (message_edit)

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

import db
from embeds import edited_message_embed

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class MemberUpdate(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        event_type = "message_edit"

        if 'content' in payload.data and payload.data['content'] != '':  # Makes sure there is a message content
            if "guild_id" not in payload.data:
                return  # We are in a DM, Don't log the message

            after_msg = payload.data['content']
            guild_id = int(
                payload.data["guild_id"])  # guild_id needs to be typecast to int since raw payload id's are str.
            message_id = payload.message_id

            db_cached_message = await db.get_cached_message(self.bot.db_pool, guild_id, payload.message_id)
            if payload.cached_message is not None:
                before_msg = payload.cached_message.content
                author = payload.cached_message.author
                author_id = author.id
                channel_id = payload.cached_message.channel.id
            else:
                before_msg = db_cached_message.content if db_cached_message is not None else None

                # author_id needs to be typecast to int since raw payload id's are str.
                author_id = int(payload.data['author']['id'])
                channel_id = payload.channel_id
                author = None

            if self.bot.user.id == author_id:
                # This is a Gabby Gums message. Do not log the event.
                return

            if after_msg == before_msg:
                # The message content has not changed. This is a pin/unpin, embed edit (which would be from a bot or discord)
                return

            if await self.bot.is_channel_ignored(guild_id, channel_id):
                return

            channel: discord.TextChannel = await self.bot.get_channel_safe(channel_id)
            if await self.bot.is_category_ignored(guild_id, channel.category):
                return

            log_channel = await self.bot.get_event_or_guild_logging_channel(guild_id, event_type, author_id)
            if log_channel is None:
                # Silently fail if no log channel is configured or if the event or user is ignored.
                return

            if author is None:
                await self.bot.wait_until_ready()
                # TODO: Consider removing to prevent potential API call
                author = self.bot.get_user(author_id)
                if author is None:
                    logging.warning(f"get_user failed in raw msg_edit: {author_id}")
                    author = await self.bot.fetch_user(author_id)

            embed = edited_message_embed(author_id, author.name, author.discriminator, channel_id, before_msg,
                                         after_msg, message_id, guild_id)

            await self.bot.send_log(log_channel, event_type, embed=embed)

            if db_cached_message is not None:
                await db.update_cached_message(self.bot.db_pool, guild_id, payload.message_id, after_msg)


def setup(bot):
    bot.add_cog(MemberUpdate(bot))
