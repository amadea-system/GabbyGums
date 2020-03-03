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

    # if guild.id not in bot.alerted_guilds:  # Make sure we don't spam guilds with permission errors.
    #     bot.alerted_guilds.append(guild.id)
    #
    #     guild_owner: discord.User = guild.owner
    #
    #     dm_chan: discord.DMChannel = guild_owner.dm_channel
    #     if dm_chan is None:
    #         log.info("DM Channel was None. Creating Channel")
    #         dm_chan = await guild_owner.create_dm()
    #
    #     # msg = "⚠ Alert!!\n" \
    #     #       f"{event_type.capitalize()} logs **can not be sent** in your server *{guild.name}* due to a **permissions problem** with the configured log channel <#{errored_channel.id}> (#{errored_channel.name}) !\n" \
    #     #     f"This is the only notice you will receive until the next time the bot is rebooted. However, this may not be the only event there may be other permission problems in other channels that would prevent Gabby Gums from logging those events too." \
    #     #     f"Please fix the permissions error or chose a new log channel that has correctly configured permissions.\n" \
    #     #     f"You can use the `{bot.command_prefix}permissions` command in your server to debug all the permission problems your server may have.\n" \
    #     #     f"Feel free to join our support server, <{permissions_error_support_link}>, if you need any assistance in fixing this error."
    #
    #     msg = "⚠ Alert!!\n" \
    #         f"One or more permission errors have been detected in your server *{guild.name}* that is preventing one or more event type logs from being sent to their configured log channels!\n" \
    #         f"This is the **only notice** you will receive until the next time the bot is rebooted.\n" \
    #         f"Please fix the permissions error(s) in order to enable Gabby Gums to properly log the events you have configured to be logged.\n" \
    #         f"You can use the `{bot.command_prefix}permissions` command in your server to debug all the permission problems your server may have.\n" \
    #         f"Feel free to join our support server, <{permissions_error_support_link}>, if you need any assistance in fixing this error."
    #
    #     try:
    #         await dm_chan.send(msg)
    #     except discord.Forbidden:

        # # Fall back to this so we can try to help the effected user.
        # error_msg = f"Could not send permissions error notice to guild {guild.name} ({guild.id})"
        # log.warning(error_msg)
        #
        # if 'error_log_channel' not in bot.config:
        #     return
        # error_log_channel = bot.get_channel(bot.config['error_log_channel'])
        # await error_log_channel.send(error_msg)



