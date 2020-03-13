"""
Cog for the on_raw_message_delete event.
Logs from this event include:
    When a message is deleted (message_delete)

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import aiohttp
import discord
from discord.ext import commands

import db
import miscUtils
from embeds import deleted_message_embed
from utils.pluralKit import get_pk_message, CouldNotConnectToPKAPI, UnknownPKError

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class MemberUpdate(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        event_type = "message_delete"

        # Exit function to ensure message is removed from the cache.
        async def cleanup_message_cache():
            if db_cached_message is not None:
                await db.delete_cached_message(self.bot.db_pool, payload.guild_id, db_cached_message.message_id)


        if payload.guild_id is None:
            return  # We are in a DM, Don't log the message

        # Get the cached msg from the DB (if possible). Will be None if msg does not exist in DB
        db_cached_message = await db.get_cached_message(self.bot.db_pool, payload.guild_id, payload.message_id)

        # Check if the channel we are in is ignored. If it is, bail
        if await self.bot.is_channel_ignored(payload.guild_id, payload.channel_id):
            await cleanup_message_cache()
            return

        # Check if the category we are in is ignored. If it is, bail
        channel: discord.TextChannel = await self.bot.get_channel_safe(payload.channel_id)
        if await self.bot.is_category_ignored(payload.guild_id, channel.category):
            await cleanup_message_cache()
            return

        channel_id = payload.channel_id

        # Check to see if we got results from the memory or DB cache.
        if payload.cached_message is not None or db_cached_message is not None:
            cache_exists = True
            # Pull the message content and author from the Memory/DB Cache. Favor the Memory cache over the DB Cache.
            msg = payload.cached_message.content if payload.cached_message is not None else db_cached_message.content
            author = payload.cached_message.author if payload.cached_message is not None else self.bot.get_user(db_cached_message.user_id)

            # Check if the message is from Gabby Gums or an ignored user. If it is, bail.
            if author is not None and (self.bot.user.id == author.id):
                await cleanup_message_cache()
                return

            author_id = author.id if author is not None else None
        else:
            # Message was not in either cache. Set msg and author to None.
            cache_exists = False
            msg = None
            author_id = None
            author = None

        # Not doing anything with this check yet. Leaving it here for now to ensure that it is reliable.
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        if guild is not None:
            pk_is_here = await self.bot.is_pk_here(guild)

        try:
            pk_msg = await get_pk_message(payload.message_id)
            if pk_msg is not None and self.verify_message_is_preproxy_message(payload.message_id, pk_msg):
                # We have confirmed that the message is a pre-proxied message.
                await self.cache_pk_message_details(payload.guild_id, pk_msg)
                await cleanup_message_cache()
                return  # Message was a pre-proxied message deleted by PluralKit. Return instead of logging message.

        except CouldNotConnectToPKAPI:
            logging.warning("Could not connect to PK server with out errors. Assuming message should be logged.")
        except UnknownPKError as e:
            await miscUtils.log_error_msg(self.bot, e)

        if db_cached_message is not None and db_cached_message.pk_system_account_id is not None:
            pk_system_owner = self.bot.get_user(db_cached_message.pk_system_account_id)
        else:
            pk_system_owner = None

        effective_author_id = pk_system_owner.id if pk_system_owner is not None else author_id

        # Get the servers logging channel.
        log_channel = await self.bot.get_event_or_guild_logging_channel(payload.guild_id, event_type, effective_author_id)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            await cleanup_message_cache()
            return

        attachments = self.load_attachments(db_cached_message, channel)  # Load any possible attachments

        embed = deleted_message_embed(message_content=msg, author=author, channel_id=channel_id,
                                      message_id=payload.message_id, webhook_info=db_cached_message,
                                      pk_system_owner=pk_system_owner, cached=cache_exists)

        await self.bot.send_log(log_channel, event_type, embed=embed)
        if len(attachments) > 0:
            await log_channel.send(content="Deleted Attachments:",
                                   files=attachments)  # Not going to bother using the safe log sender here yet.

        await cleanup_message_cache()


    def load_attachments(self, db_message: db.CachedMessage, channel: discord.TextChannel):
        """Checks if we have any attachments saved on disk and returns them as a list of discord.Files"""

        # Handle any attachments
        attachments = []
        if db_message is not None and db_message.attachments is not None:
            for attachment_name in db_message.attachments:
                spoil = True if "SPOILER" in attachment_name else False
                if spoil is False:
                    # channel = await get_channel_safe(payload.channel_id)
                    if channel.is_nsfw():
                        spoil = True  # Make ANY image from an NSFW board spoiled to keep log channels SFW.
                try:
                    # max file sizee 8000000  # TODO: Make sure that we don't send files bigger than 8000000 bytes.
                    new_attachment = discord.File(f"./image_cache/{db_message.server_id}/{attachment_name}",
                                                  filename=attachment_name, spoiler=spoil)
                    attachments.append(new_attachment)
                except FileNotFoundError:
                    pass  # The file may have been too old and has since been deleted.
        return attachments


    def verify_message_is_preproxy_message(self, message_id: int, pk_response: Dict) -> bool:
        # Compare the proxied msg id reported from the API with this messages id
        #   to determine if this message is actually a proxyed message.
        if 'id' in pk_response:  # Message ID (Discord Snowflake) of the proxied message
            pk_message_id = int(pk_response['id'])
            if message_id == pk_message_id:
                # This is a false positive. We actually do need to log the message.
                return False
            else:
                # Message is indeed a preproxied message
                return True
        else:
            # Message is indeed a preproxied message
            return True


    async def cache_pk_message_details(self, guild_id: int, pk_response: Dict):

        error_msg = []
        error_header = '[cache_pk_message_details]: '
        if 'id' in pk_response:  # Message ID (Discord Snowflake) of the proxied message
            message_id = int(pk_response['id'])
        else:
            # If we can not pull the message ID there is no point in continuing.
            msg = "'WARNING! 'id' not in PK msg API Data. Aborting JSON Decode!"
            error_msg.append(msg)
            logging.warning(msg)
            await miscUtils.log_error_msg(self.bot, error_msg, header=f"{error_header}!ERROR!")
            return

        if 'sender' in pk_response:  # User ID of the account that sent the pre-proxied message. Presumed to be linked to the PK Account
            sender_discord_id = int(pk_response['sender'])
        else:
            sender_discord_id = None
            msg = "WARNING! 'Sender' not in MSG Data"
            error_msg.append(msg)

        if 'system' in pk_response and 'id' in pk_response['system']:  # PK System Id
            system_pk_id = pk_response['system']['id']
        else:
            system_pk_id = None
            msg = "WARNING! 'system' not in MSG Data or 'id' not in system data!"
            error_msg.append(msg)

        if 'member' in pk_response and 'id' in pk_response['member']:  # PK Member Id
            member_pk_id = pk_response['member']['id']
        else:
            member_pk_id = None
            msg = "WARNING! 'member' not in MSG Data or 'id' not in member data!"
            error_msg.append(msg)

        # TODO: Remove verbose Logging once feature deemed to be stable .
        logging.debug(
            f"Updating msg: {message_id} with Sender ID: {sender_discord_id}, System ID: {system_pk_id}, Member ID: {member_pk_id}")
        await db.update_cached_message_pk_details(self.bot.db_pool, guild_id, message_id, system_pk_id, member_pk_id,
                                                  sender_discord_id)

        if len(error_msg) > 0:
            await miscUtils.log_error_msg(self.bot, error_msg, header=error_header)


def setup(bot):
    bot.add_cog(MemberUpdate(bot))
