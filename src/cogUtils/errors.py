"""
Utility functions for handling exceptions.

Part of the Gabby Gums Discord Logger.
"""

import logging

from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)

EventPayload = Union[discord.Member, discord.User, discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel,
                     discord.RawBulkMessageDeleteEvent, discord.RawMessageDeleteEvent, discord.RawMessageUpdateEvent]

permissions_error_support_link = "https://discord.gg/yJU7FKN"


async def handle_permissions_error(bot: 'GGBot', errored_channel: discord.TextChannel, event_type: str, exception: Exception, event_payload: EventPayload):

    guild: discord.Guild = errored_channel.guild
    bot.has_permission_problems.append(guild.id)

    ch_perm: discord.Permissions = guild.me.permissions_in(errored_channel)
    sent_msg = False
    # Default to logging the perm prob to the affected channel if possible, attempt fall back to the defualt
    if ch_perm.send_messages:
        log_ch = errored_channel
        log_ch_perm = ch_perm
    else:
        log_ch = await bot.get_event_or_guild_logging_channel(guild.id)
        log_ch_perm = guild.me.permissions_in(log_ch) if log_ch != errored_channel else ch_perm

    if log_ch_perm.send_messages:
        # We are sending the error msg as normal text as it has the highest probability of going through.
        error_msg = f"\N{WARNING SIGN} Unable to send log in <#{errored_channel.id}> due to the following missing permissions:\n"

        if not ch_perm.send_messages:
            error_msg += "**Send Messages**\n"

        if not ch_perm.embed_links:
            error_msg += "**Embed Links**\n"

        if event_type == "channel_update" and not ch_perm.external_emojis:
            error_msg += "**Use External Emoji**\n"

        if event_type == "message_delete" and not ch_perm.attach_files:
            error_msg += "**Attach Files**\n"

        error_msg += "\n"

        error_msg += f"You can use the `{bot.command_prefix}permissions` command to show all the permission problems your server may have.\n" \
                     f"If you were trying to disable {event_type} events, please use the {bot.command_prefix}!events command instead of revoking Gabby Gums permissions to help conserve Gabby Gums CPU and Memory resources.\n" \
                     f"Feel free to join our support server, <{permissions_error_support_link}>, if you need any assistance in fixing this error."

        await log_ch.send(error_msg)
        sent_msg = True

    error_msg = f"Permissions error in {errored_channel.id} - {guild.id}. Notice sent: {sent_msg}"
    log.warning(error_msg)

    if 'permissions_error_log_channel' in bot.config:
        error_log_channel = bot.get_channel(bot.config['permissions_error_log_channel'])
    elif 'error_log_channel' in bot.config:
        error_log_channel = bot.get_channel(bot.config['error_log_channel'])
    else:
        return

    await error_log_channel.send(error_msg)

