"""
Cog for the on_raw_bulk_message_delete event.
Logs from these event include:
    Bulk message deletion

Part of the Gabby Gums Discord Logger.
"""

import asyncio
import logging

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

import db
# import utils
import cogUtils.chatArchiver as chatArchiver

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class CompositeMessage:
    """Object storage for handling mem cache AND bot cache messages."""

    def __init__(self, bot: 'GGBot', message_id: int, mem_message: Optional[discord.Message] = None, db_message: Optional[db.CachedMessage] = None):
        self.bot = bot
        self._msg_id = message_id
        self.mem_msg: Optional[discord.Message] = mem_message
        self.db_msg: Optional[db.CachedMessage] = db_message
        self._author: Union[discord.User, discord.Member] = None
        self._linked_pk_account = None
        self._guild = None

    @property
    def id(self) -> Optional[int]:
        return self._msg_id
        # if self.db_msg is None and self.mem_msg is None:
        #     return None
        # return self.mem_msg.id if self.mem_msg is not None else self.db_msg.message_id

    @property
    def guild(self) -> Optional[discord.Guild]:
        """Returns the Guild the message was sent in."""
        if self.db_msg is None and self.mem_msg is None:
            return None

        if self._guild is None:
            self._guild = self.mem_msg.guild if self.mem_msg is not None else self.bot.get_guild(self.db_msg.server_id)

        return self._guild

    @property
    def content(self) -> Optional[str]:
        """Returns the content of the message (if any)"""
        if self.db_msg is None and self.mem_msg is None:
            return None

        return self.mem_msg.content if self.mem_msg is not None else self.db_msg.content

    @property
    def created_at(self) -> Optional[datetime]:
        """Returns the creation date of the message (UTC)"""
        if self.db_msg is None and self.mem_msg is None:
            return None

        return self.mem_msg.created_at if self.mem_msg else self.db_msg.ts


    @property
    def author(self) -> Optional[Union[discord.Member, discord.User]]:
        """
        Returns the Member or User who sent the message.
        NOTE currently this will result in an Object whos ID is a webhook id in the case of a PK message.
        This will be fixed in the future.
        """
        if self.db_msg is None and self.mem_msg is None:
            return None

        if self._author is None:
            self._author = self.mem_msg.author if self.mem_msg is not None else self.bot.get_user(self.db_msg.user_id)

        return self._author


    @property
    def display_name(self) -> Optional[str]:
        """Returns the display name (with no discrim)"""
        if self.db_msg is None and self.mem_msg is None:
            return None

        if self.db_msg is not None and self.db_msg.webhook_author_name is not None:
            return self.db_msg.webhook_author_name

        if self._author is None:
            _ = self.author

        return self._author.display_name


    @property
    def user_name_and_discrim(self) -> Optional[str]:
        """Returns the user name with discrim"""
        if self.db_msg is None and self.mem_msg is None:
            return None

        if self.db_msg is not None and self.db_msg.webhook_author_name is not None:
            return f"{self.db_msg.webhook_author_name}#0000"

        if self._author is None:
            _ = self.author

        return f"{self._author.name}#{self._author.discriminator}"


    @property
    def is_pk(self) -> bool:
        """Returns bool indicating if this is a PK Webhook msg"""
        return True if self.system_id is not None else False

    @property
    def system_id(self) -> Optional[str]:
        """returns the PK System ID (if any) belonging to the author of the message"""
        return self.db_msg.system_pkid if self.db_msg is not None else None


    @property
    def member_id(self) -> Optional[str]:
        """returns the PK Member ID (if any) belonging to the author of the message"""
        return self.db_msg.member_pkid if self.db_msg is not None else None


    @property
    def pk_system_owner(self) -> Optional[discord.User]:
        """returns the Discord User that is linked to the PK account that sent the message(if any)"""
        if self.db_msg is None or self.db_msg.pk_system_account_id is None:
            return None

        if self._linked_pk_account is None:
            self._linked_pk_account = self.bot.get_user(self.db_msg.pk_system_account_id)

        return self._linked_pk_account


class BulkMsgDelete(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

    # ----- Commands ----- #
    # TODO: Move to a cog command once CompositeMessage is in it's own file.
    @commands.is_owner()
    @commands.command(name="archive")
    async def archive(self, ctx: commands.Context, number_of_msg: int):
        channel: discord.TextChannel = ctx.channel
        if number_of_msg > 10000:
            await ctx.send(f"The max number of achievable messages is 10000!")
        # Todo: Check Permissions
        # Todo: Max number of msg
        # Todo: Date/Time/snowflake Option?
        # Todo: Add cooldown to prevent DDOS

        messages = await channel.history(limit=number_of_msg, oldest_first=False).flatten()
        comp_messages: List[CompositeMessage] = []

        for msg in messages:
            db_msg = await db.get_cached_message(self.bot.db_pool, ctx.guild.id, msg.id)
            comp_messages.append(CompositeMessage(self.bot, msg.id, msg, db_msg))

        with chatArchiver.generate_txt_archive(comp_messages, ctx.channel.name) as archive_file:
            await ctx.send(f"Archived {number_of_msg} messages.", file=discord.File(archive_file, filename="archive.txt"))


    # ----- Events ----- #

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        """Handles the 'on_bulk_message_delete' event."""
        event_type = "message_delete"  # Share the Message Delete event type unless there is demand to make it it's own event type.

        if payload.guild_id is None:  # In DMs
            return

        async def cleanup_message_cache():
            if len(db_cached_messages) > 0:
                for cached_msg in db_cached_messages:
                    log.info(f"Cleaning msg {cached_msg.message_id} from db.")
                    await db.delete_cached_message(self.bot.db_pool, payload.guild_id, cached_msg.message_id)

        # Pull as many messages as possible from the DB and the d.py mem cache.
        # Combine them in CompositeMessages and add them to the messages list.
        db_cached_messages = []
        messages: List[CompositeMessage] = []
        msg_ids = sorted(payload.message_ids)  # Make sure the id's are sorted in chronological order (Thank goodness for snowflakes.)
        for msg_id in msg_ids:
            db_msg = await db.get_cached_message(self.bot.db_pool, payload.guild_id, msg_id)
            mem_msg = discord.utils.get(payload.cached_messages, id=msg_id)
            if db_msg is not None:
                db_cached_messages.append(db_msg)
            messages.append(CompositeMessage(self.bot, msg_id, mem_msg, db_msg))

        # Check if the channel we are in is ignored. If it is, bail
        if await self.bot.is_channel_ignored(payload.guild_id, payload.channel_id):
            await cleanup_message_cache()
            return

        # Check if the category we are in is ignored. If it is, bail
        channel: discord.TextChannel = await self.bot.get_channel_safe(payload.channel_id)
        if await self.bot.is_category_ignored(payload.guild_id, channel.category):
            await cleanup_message_cache()
            return

        log_channel = await self.bot.get_event_or_guild_logging_channel(payload.guild_id, event_type)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            await cleanup_message_cache()
            return

        with chatArchiver.generate_txt_archive(messages, channel.name) as archive_file:
            embed = self.get_bulk_delete_embed(len(messages), payload.channel_id)
            await log_channel.send(embed=embed, file=discord.File(archive_file, filename="archive.txt"))

        log.info(f"archived {len(messages)} messages out of {len(payload.message_ids)} deleted messages.")
        await cleanup_message_cache()


    @staticmethod
    def get_bulk_delete_embed(number_deleted: int, channel_id: int):

        embed = discord.Embed(description=f"{number_deleted} Messages were deleted in <#{channel_id}>",
                              color=discord.Color.purple(), timestamp=datetime.utcnow())
        embed.set_author(name="Bulk Message Deletion")
        embed.set_footer(text="\N{Zero Width Space}")  # Workaround for timestamps not showing up on mobile.

        return embed


def setup(bot):
    bot.add_cog(BulkMsgDelete(bot))
