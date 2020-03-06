"""
Cog for the on_raw_bulk_message_delete event.
Logs from these event include:
    Bulk message deletion

Part of the Gabby Gums Discord Logger.
"""

import asyncio
import time
import logging

from io import StringIO
from random import randint
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Match, Pattern

import discord
from discord.ext import commands
# import regex as re  # Using external regex lib as it's slightly faster and offers more features.
# from markupsafe import Markup, escape
from jinja2 import Markup, escape


import db
# import utils
import utils.chatArchiver as chatArchiver
from utils.discordMarkdownParser import markdown

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class CannotReadMessageHistory(Exception):
    def __init__(self):
        super().__init__(f"⚠️Missing the `Read Message History` permission!\n")


class CouldNotDownloadFile(Exception):
    pass


class WrongFileType(Exception):
    pass


class CompositeMessage:
    """Object storage for handling mem cache AND bot cache messages."""

    def __init__(self, bot: 'GGBot', message_id: int, mem_message: Optional[discord.Message] = None, db_message: Optional[db.CachedMessage] = None):
        self.bot = bot
        self._msg_id = message_id
        self.mem_msg: Optional[discord.Message] = mem_message
        self.db_msg:  Optional[db.CachedMessage] = db_message

        self.exists = True if (self.mem_msg is not None or self.db_msg is not None) else False

        self._author: Union[discord.User, discord.Member] = self.get_author()
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
    def raw_content(self) -> str:
        """Returns the raw unmarkdowned conttent of the message (if any)"""
        if self.db_msg is None and self.mem_msg is None:
            return "Message was not in the cache"

        output = self.mem_msg.content if self.mem_msg is not None else self.db_msg.content
        return output


    @property
    def content(self) -> str:
        """Returns the content of the message (if any)"""
        if self.db_msg is None and self.mem_msg is None:
            return "Message was not in the cache"

        output = self.mem_msg.content if self.mem_msg is not None else self.db_msg.content
        markdowned = markdown.markdown(output)
        # safe_output = escape(markdowned)
        return Markup(markdowned)

    @property
    def created_at(self) -> Optional[datetime]:
        """Returns the creation date of the message (UTC)"""
        if self.db_msg is None and self.mem_msg is None:
            return None

        return self.mem_msg.created_at if self.mem_msg else self.db_msg.ts

    def get_author(self):
        if self.db_msg is None and self.mem_msg is None:
            return None

        author = self.mem_msg.author if self.mem_msg is not None else self.bot.get_user(self.db_msg.user_id)
        if author is None:
            log.warning("Could not find the author!!!")
        return author

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
            if self._author is None:
                log.warning("Could not find the author!!!")
        return self._author

    @property
    def author_pfp(self) -> str:
        """Needed for old messages in case we can't get the user (Particularly for webhooks)"""
        default = f"https://cdn.discordapp.com/embed/avatars/{randint(0,4)}.png"
        pfp_url = str(self.author.avatar_url_as(static_format='png')) if self._author else default
        return pfp_url

    @property
    def display_name(self) -> Optional[str]:
        """Returns the display name (with no discrim)"""
        if self.db_msg is None and self.mem_msg is None:
            return "None"

        if self.db_msg is not None and self.db_msg.webhook_author_name is not None:
            return self.db_msg.webhook_author_name

        if self._author is None:
            _ = self.author

        return self._author.display_name

    @property
    def user_name_and_discrim(self) -> Optional[str]:
        """Returns the user name with discrim"""
        if self.db_msg is None and self.mem_msg is None:
            return "None"

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

    @property
    def attachments(self) -> List[discord.Attachment]:
        # TODO: Implement something with the DB attachments.
        return self.mem_msg.attachments if self.mem_msg else []

    @property
    def embeds(self) -> List[discord.Embed]:
        return self.mem_msg.embeds if self.mem_msg else []

    @property
    def reactions(self) -> List[discord.Reaction]:
        return self.mem_msg.reactions if self.mem_msg else []

    @property
    def pinned(self) -> bool:
        return self.mem_msg.pinned if self.mem_msg else None

    @property
    def edited_at(self):
        return self.mem_msg.edited_at if self.mem_msg else None


class FakeDateTime:
    """A VERYY TERRIBLE TEMPORARY HACK"""

    def __init__(self):
        pass

    def strftime(self, *args, **kwargs):
        return ""


class MessageGroup:

    def __init__(self, message: CompositeMessage):
        self.messages = [message]
        self.uncached_group = (not message.exists)
        self.author = message.author
        self.created_at = message.created_at or FakeDateTime()
        self.author_pfp = message.author_pfp
        self.author_username = message.user_name_and_discrim
        self.author_display_name = message.display_name
        self.is_pk = message.is_pk

        if self.is_pk:
            self.author_info = f"(System ID: {message.system_id}, Member ID: {message.member_id})"
        elif self.uncached_group or self.author is None:
            self.author_info = ""
        else:
            self.author_info = f"({self.author.id})"

    def __getitem__(self, item):
        return self.messages[item]


    @property
    def count(self)-> int:
        return len(self.messages)


    def append(self, message: CompositeMessage):
        if not message.exists and self.uncached_group:
            # Handle uncached messages specially.
            self.messages.append(message)
        elif message.author is not None and self.author is not None and self.author.id == self.author.id and message.author.name == self.author.name:
            self.messages.append(message)
        else:
            raise ValueError

    # @property
    # def content(self) -> str:
    #     txt = []
    #     for message in self.messages:
    #         txt.append(message.content)
    #
    #     return "\n".join(txt)


class MessageGroups:
    """List like Class that automatically sorts CompositeMessage into appropriate the appropriate message groups"""

    def __init__(self):
        self._message_groups: List[MessageGroup] = []


    def __getitem__(self, item):
        return self._message_groups[item]

    def len(self):
        # TODO: Return total number of individual messages
        return len(self._message_groups)

    @property
    def last_message_group(self) -> MessageGroup:
        return self._message_groups[-1]

    def append(self, message: CompositeMessage):
        if len(self._message_groups) == 0:
            self._message_groups.append(MessageGroup(message))
        else:
            try:
                self.last_message_group.append(message)
            except ValueError:
                self._message_groups.append(MessageGroup(message))


class Archive(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

    # ----- Commands ----- #
    # TODO: Move to a command cog once CompositeMessage is in it's own file.


    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    @commands.is_owner()
    @commands.command(name="txtarc",
                      brief="Recod.",
                      description="adw")
    async def txt_archive(self, ctx: commands.Context, number_of_msg: int = 1000):
        channel: discord.TextChannel = ctx.channel

        # Check for permissions
        permissions: discord.Permissions = ctx.channel.permissions_for(ctx.guild.me)
        if not permissions.read_message_history:
            raise CannotReadMessageHistory

        if number_of_msg > 10000:
            await ctx.send(f"The maximum number of achievable messages is 10000!")

        # Todo: Figure out the best number of max number of msg
        # Todo: Date/Time/snowflake Option?

        # Todo: Add archive specific cooldown error handling
        # Todo: Add archive specific max concurancy error handling

        # Fixme: Uncomment
        # await ctx.send(
        #     f"Beginning archive of the last {number_of_msg} messages. This may take a while for large numbers of messages.")

        start_time = time.perf_counter()
        async with channel.typing():
            # Get the specified num of messages from this channel BEFORE the command was sent.
            messages = await channel.history(limit=number_of_msg, before=ctx.message, oldest_first=False).flatten()

            # Fixme: Uncomment
            # alert user if channel has less messages than they asked for.
            # if len(messages) < number_of_msg:
            #     number_of_msg = len(messages)
            #     await ctx.send(f"#{channel.name} only contained {number_of_msg}. Archiving the entire channel.")

            # Construct CompositeMessages with the history we just got and DB data.
            comp_messages: List[CompositeMessage] = []
            for msg in messages:
                db_msg = await db.get_cached_message(self.bot.db_pool, ctx.guild.id, msg.id)
                comp_messages.append(CompositeMessage(self.bot, msg.id, msg, db_msg))
        #
        # with chatArchiver.generate_txt_archive(comp_messages, ctx.channel.name) as archive_file:
        #     file_name = f"{channel.name} - Archive.txt"
        #     end_time = time.perf_counter()
        #     await ctx.send(f"Archived {number_of_msg} messages in {(end_time - start_time):.2f} seconds.",
        #                    file=discord.File(archive_file, filename=file_name))


            chatArchiver.save_htmlDebug_txt_archive(comp_messages, ctx.channel.name)
            end_time = time.perf_counter()
            log.info(f"Archived {number_of_msg} messages in {(end_time - start_time):.2f} seconds.")

    # TODO: Move to a commands cog once CompositeMessage is in it's own file.
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    @commands.command(name="archive",
                      brief="Creates an archive file for the number of messages specified.",
                      description="Creates an archive file for the number of messages specified.")
    async def archive(self, ctx: commands.Context, number_of_msg: int, channel: Optional[discord.TextChannel], message_id: Optional[int]):

        if channel is None:
            channel: discord.TextChannel = ctx.channel

        timestamp = discord.Object(message_id) if message_id is not None else ctx.message

        # Check for permissions
        permissions: discord.Permissions = ctx.channel.permissions_for(ctx.guild.me)
        if not permissions.read_message_history:
            raise CannotReadMessageHistory

        if number_of_msg > 10000:
            await ctx.send(f"The maximum number of achievable messages is 10000!")
            number_of_msg = 10000

        # Todo: Figure out the best number of max number of msg (Maybe User/Guild Daily Maximum?)
        # Todo: Add archive specific max concurancy error handling

        start_time = time.perf_counter()
        hist_start_time = time.perf_counter()
        async with ctx.channel.typing():
            # Construct CompositeMessages with the history we just got and DB data.
            message_groups: MessageGroups = MessageGroups()
            actual_msg_count = 0
            # Get the specified num of messages from this channel BEFORE the command was sent.

            # flatten Implementation
            messages = await channel.history(limit=number_of_msg, before=timestamp, oldest_first=False).flatten()
            messages.reverse()
            hist_end_time = time.perf_counter()
            db_start_time = time.perf_counter()

            async with self.bot.db_pool.acquire() as conn:  # Acquire the connection here so it only has to be done once for ALL the get_cached_message DB calls.
                for msg in messages:
                    actual_msg_count += 1
                    db_msg = await db.get_cached_message_for_archive(conn, ctx.guild.id, msg.id)
                    comp_msg = CompositeMessage(self.bot, msg.id, msg, db_msg)
                    message_groups.append(comp_msg)
            db_time = time.perf_counter() - db_start_time

        archive_start_time = time.perf_counter()

        with await chatArchiver.generate_html_archive(self.bot, channel, message_groups, actual_msg_count) as archive_file:
            archive_end_time = time.perf_counter()

            hmac_start = time.perf_counter()
            chatArchiver.write_hmac(archive_file, security_key=self.bot.hmac_key)
            log.info(f"HMAC: {(time.perf_counter()-hmac_start):.2f}")

            hash_start_time = time.perf_counter()
            sha_hash = chatArchiver.generate_SHA256_hash(archive_file)
            hash_end_time = time.perf_counter()

            file_name = f"{channel.name} - Archive.html"
            end_time = time.perf_counter()
            log.info(f"hist: {(hist_end_time-hist_start_time):.2f}, DB: {db_time:.2f}, archive: {(archive_end_time-archive_start_time):.2f}, hash: {(hash_end_time-hash_start_time):.2f}")
            await ctx.send(f"Archived {actual_msg_count} messages in {(end_time - start_time):.2f} seconds.\n"
                           f"SHA-256 Hash: `{sha_hash}`",
                           file=discord.File(archive_file, filename=file_name))

        # For debugging.
        # chatArchiver.save_html_archive(channel, message_groups, len(messages))
        # end_time = time.perf_counter()
        # log.info(f"Archived {number_of_msg} messages in {(end_time - start_time):.2f}s for storage in {ctx.guild.id}.")

    # TODO: Move to a commands cog once CompositeMessage is in it's own file.
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    @commands.command(name="verify_archive",
                      aliases=["verify", "va"],
                      brief="Verifies that an archive file has not been tampered with.",
                      description="Verifies that an archive file has not been tampered with.")
    async def verify_cmd(self, ctx: commands.Context):
        message: discord.Message = ctx.message
        if len(message.attachments) == 0:
            await ctx.send("No archive file uploaded!")
            return
        try:
            authentic = await self.verify_archive_file(ctx.message)
        except CouldNotDownloadFile:
            await ctx.send("Could not retrieve the uploaded archive file. Discord may be having problems. Please try again in a little bit.")
            return

        if authentic is None:
            await ctx.send("Could not retrieve the uploaded archive file. Discord may be having problems. Please try again in a little bit.")
            return
        elif authentic:
            await ctx.message.add_reaction("✅")
            await ctx.send("✅ The archive file is unmodified!!!")
        else:
            await ctx.message.add_reaction("❌")
            await ctx.send("❌ The archive file has been modified!!!")


    async def verify_archive_file(self, message: discord.Message) -> Optional[bool]:

        file: discord.Attachment = message.attachments[0]
        archive = StringIO()

        try:
            file_bytes = await file.read()
            written = archive.write(file_bytes.decode("utf-8"))
        except (discord.HTTPException, discord.NotFound):
            raise CouldNotDownloadFile()

        hmac_start = time.perf_counter()
        authentic = chatArchiver.verify_file(archive, self.bot.hmac_key)
        log.info(f"Verification Time: {(time.perf_counter() - hmac_start):.2f}")

        return authentic

    # ----- Events ----- #


    # @commands.Cog.listener()
    # async def on_message(self, message: discord.Message):
    #     """For automatic verification of uploaded Archive Files."""
    #
    #     # Make sure it's not a command.
    #     # Make sure there is an attachment to even do something with...
    #     if not message.author.bot and not message.content.startswith(self.bot.command_prefix) and len(message.attachments) > 0:
    #         attachment: discord.Attachment = message.attachments[0]  # Only going to focus on the first attachemnt for now.
    #         file_name_parts = attachment.filename.split(".")  # split up the file name/extention
    #         if len(file_name_parts) > 1 and file_name_parts[-1].lower() == "html":  # Make sure it's an HTML file.
    #             try:
    #                 authentic = await self.verify_archive_file(message)
    #             except (CouldNotDownloadFile, chatArchiver.CouldNotFindAuthenticationCode):
    #                 return  # If we error, do nothing.
    #
    #             if authentic:
    #                 await message.add_reaction("✅")
    #             else:
    #                 await message.add_reaction("❌")





class BulkMsgDelete(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

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
        # messages: List[CompositeMessage] = []
        message_groups: MessageGroups = MessageGroups()
        msg_count = 0
        msg_ids = sorted(payload.message_ids)  # Make sure the id's are sorted in chronological order (Thank goodness for snowflakes.)
        for msg_id in msg_ids:
            db_msg = await db.get_cached_message(self.bot.db_pool, payload.guild_id, msg_id)
            mem_msg = discord.utils.get(payload.cached_messages, id=msg_id)
            if db_msg is not None:
                db_cached_messages.append(db_msg)

            comp_msg = CompositeMessage(self.bot, msg_id, mem_msg, db_msg)
            message_groups.append(comp_msg)
            msg_count += 1
            # messages.append(comp_msg)

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

        with await chatArchiver.generate_html_archive(self.bot, channel, message_groups, msg_count) as archive_file:
            file_name = f"{channel.name} - Archive.html"
            embed = self.get_bulk_delete_embed(msg_count, payload.channel_id)
            # await log_channel.send(embed=embed, file=discord.File(archive_file, filename=file_name))
            await self.bot.send_log(log_channel, event_type, embed=embed, file=discord.File(archive_file, filename=file_name))

        log.info(f"archived {msg_count} messages out of {len(payload.message_ids)} deleted messages.")
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
    bot.add_cog(Archive(bot))
