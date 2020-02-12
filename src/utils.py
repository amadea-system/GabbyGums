import textwrap
from typing import Union, Optional, Dict, List
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from bot import GGBot

log = logging.getLogger(__name__)


async def send_long_msg(channel: [discord.TextChannel, commands.Context], message: str, code_block: bool = False, code_block_lang: str = "python"):

    if code_block:
        if len(code_block_lang) > 0:
            code_block_lang = code_block_lang + "\n"
        code_block_start = "```" + code_block_lang
        code_block_end = "```"
        code_block_extra_length = len(code_block_start) + len(code_block_end)
        chunks = textwrap.wrap(message, width=2000 - code_block_extra_length)
        message_chunks = [code_block_start + chunk + code_block_end for chunk in chunks]

    else:
        message_chunks = textwrap.wrap(message, width=2000)

    for chunk in message_chunks:
        await channel.send(chunk)


async def send_error_msg_to_log(bot: GGBot, error_messages: Optional[Union[str, List[str]]], header: Optional[str] = None, code_block: bool = False,) -> bool:
    """
    Attempts to send a message to the Global Error Discord Channel.

    Returns False if the error_log_channel is not defined in the Config,
        if the error_log_channel can not be resolved to an actual channel, or if the message fails to send.

    Returns True if successful.
    """

    if 'error_log_channel' not in bot.config:
        return False  # No error log channel defined in config, can not log

    # Check to see if there was an error message passed and bail if there wasn't
    if error_messages is None:
        return True  # Should this be True? False isn't really accurate either....
    # If list is empty, return
    elif isinstance(error_messages, list):  # If type is list

        if len(error_messages) == 0:  # List is empty. Bail
            return True  # Should this be True? False isn't really accurate either....
        # Convert it into a single string.
        error_messages = "\n".join(error_messages)
    else:
        if error_messages == "":  # Empty
            return True  # Should this be True? False isn't really accurate either....

    # Try to get the channel from discord.py.
    error_log_channel = bot.get_channel(bot.config['error_log_channel'])
    if error_log_channel is None:
        return False

    # If the header option is used, include the header message at the front of the message
    if header is not None:
        error_messages = f"{header}\n{error_messages}"
    # Attempt to send the message
    try:
        await send_long_msg(error_log_channel, error_messages, code_block=code_block)
        return True
    except discord.DiscordException as e:
        log.exception(f"Error sending log to Global Error Discord Channel!: {e}")
        return False


class MissingAuditLogPermissions(Exception):
    pass


async def get_audit_logs(guild: discord.Guild, audit_action: discord.AuditLogAction, target_user: Union[discord.User, discord.Member, discord.Object],
                         in_last: Optional[timedelta] = None) -> List[discord.AuditLogEntry]:

    permissions: discord.Permissions = guild.me.guild_permissions
    if permissions.view_audit_log:
        # if in_last is None:
        #     in_last = timedelta.max
        after_time = datetime.utcnow() - in_last if in_last else datetime.min

        def predicate(entry: discord.AuditLogEntry):
            if target_user is not None and entry.target is not None:
                return entry.created_at > after_time and entry.target.id == target_user.id
            else:
                return entry.created_at > after_time

        audit_log_entries = await guild.audit_logs(action=audit_action, oldest_first=False).filter(predicate).flatten()
        # entries = []
        # async for audit_log in audit_log_entries:
        #     entries.append(audit_log)
        #     log.info(f"Entry: {audit_log} @ {audit_log.created_at}")
        return audit_log_entries
    else:
        raise MissingAuditLogPermissions
