"""
General helper functions for Gabby Gums.
Function abilities include:
    Functions for handling long text
    Sending Error Logs to the Global error log channel
    Getting Audit logs.
    Check permissions on a channel.
    
Part of the Gabby Gums Discord Logger.
"""

import sys
import string
import asyncio
import logging
import traceback

from datetime import datetime, timedelta
from typing import Union, Optional, Dict, List, TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)

# Type aliases
GuildChannel = Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel]


async def send_long_msg(channel: [discord.TextChannel, commands.Context], message: str, code_block: bool = False, code_block_lang: str = "python"):

    if code_block:
        if len(code_block_lang) > 0:
            code_block_lang = code_block_lang + "\n"
        code_block_start = f"```{code_block_lang}"
        code_block_end = "```"
        code_block_extra_length = len(code_block_start) + len(code_block_end)
        chunks = split_text(message, max_size=2000 - code_block_extra_length)
        message_chunks = [code_block_start + chunk + code_block_end for chunk in chunks]

    else:
        message_chunks = split_text(message, max_size=2000)

    for chunk in message_chunks:
        await channel.send(chunk)


def split_text(text: Union[str, List], max_size: int = 2000, delimiter: str = "\n") -> List[str]:
    """Splits the input text such that no entry is longer that the max size """
    delim_length = len(delimiter)

    if isinstance(text, str):
        if len(text) < max_size:
            return [text]
        text = text.split(delimiter)
    else:
        if sum(len(i) for i in text) < max_size:
            return ["\n".join(text)]

    output = []
    tmp_str = ""
    count = 0
    for fragment in text:
        fragment_length = len(fragment) + delim_length
        if fragment_length > max_size:
            raise ValueError("A single line exceeded the max length. Can not split!")  # TODO: Find a better way than throwing an error.
        if count + fragment_length > max_size:
            output.append(tmp_str)
            tmp_str = ""
            count = 0

        count += fragment_length
        tmp_str += f"{fragment}{delimiter}"

    output.append(tmp_str)

    return output


async def log_error_msg(bot: 'GGBot', error_messages: Optional[Union[str, List[str], Exception]], header: Optional[str] = None, code_block: bool = False) -> bool:
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
    elif isinstance(error_messages, Exception):
        error_messages = full_stack()
        code_block = True  # Override code block for exceptions.
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


def full_stack():
    exc = sys.exc_info()[0]
    if exc is not None:
        f = sys.exc_info()[-1].tb_frame.f_back
        stack = traceback.extract_stack(f, limit=5)
    else:
        stack = traceback.extract_stack(limit=5)[:-1]  # last one would be full_stack()
    trc = 'Traceback (most recent call last):\n'
    stackstr = trc + ''.join(traceback.format_list(stack))
    if exc is not None:
        stackstr += '  ' + traceback.format_exc().lstrip(trc)
    return stackstr


class MissingAuditLogPermissions(Exception):
    pass


async def get_audit_logs(guild: discord.Guild, audit_action: discord.AuditLogAction, target_user: Union[discord.User, discord.Member, discord.Object],
                         in_last: Optional[timedelta] = None, delay_before_fetch: int = 1) -> List[discord.AuditLogEntry]:
    """
    Fetches the audit logs from Discord API, then filters the logs to include
     only those that match the audit log action and target user in the last timedelta period specified.
    Additionally, you can specify a delay before fetching the logs using delay_before_fetch.
     This is useful for avoiding a race condition with Discord.

    Raises utils.miscUtils.MissingAuditLogPermissions if we are missing permissions to view the audit logs.

    :param guild: The Guild to fettch the audit logs from
    :param audit_action: The audit log type that we want to filter on
    :param target_user: The user we want to filter on
    :param in_last: How far back in time should we request logs for
    :param delay_before_fetch: How long should we wait (in seconds) before fetching the logs.
    :return: All the logs that match.
    """

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

        await asyncio.sleep(delay_before_fetch)  # Sleep for a bit to ensure we don't hit a race condition with the Audit Log.
        audit_log_entries = await guild.audit_logs(action=audit_action, oldest_first=False).filter(predicate).flatten()

        return audit_log_entries
    else:
        raise MissingAuditLogPermissions


def prettify_permission_name(perm_name: str) -> str:
    """Takes a internal D.py permission name (such as send_tts_messages) and converts it to a prettified form suitable for showing to users (send_tts_messages -> Send TTS Messages)"""
    pretty_perm_name = string.capwords(f"{perm_name}".replace('_', ' '))  # Capitalize the permission names and replace underlines with spaces.
    pretty_perm_name = "Send TTS Messages" if pretty_perm_name == "Send Tts Messages" else pretty_perm_name  # Mak sure that we capitalize the TTS acronym properly.
    return pretty_perm_name


def check_permissions(channel: GuildChannel, additional_perms: Optional[Dict[str, bool]] = None) -> List[str]:
    """Checks to see if the channel has the default needed permissions (Read, Send, Embed) and the passed additional permissions.
    Returns a list of missing permissions."""

    standard_perms = {'read_messages': True, 'send_messages': True, 'embed_links': True}  # Permissions that EVERY channel requires.
    additional_perms = {} if additional_perms is None else additional_perms
    missing_perms = []

    # make sure all the permissions we are checking are valid
    for perm, value in additional_perms:
        if perm not in discord.Permissions.VALID_FLAGS:
            raise TypeError('%r is not a valid permission name.' % perm)

    ch_perms: discord.Permissions = channel.guild.me.permissions_in(channel)
    for perm, value in ch_perms:

        if (perm in standard_perms and standard_perms[perm] != value) or (perm in additional_perms and standard_perms[perm] != value):
            missing_perms.append(perm)

    return missing_perms
