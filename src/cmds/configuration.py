"""
Cog containing various developer only commands used for debugging purposes only.
Commands include:
    devtest
    dump
    past_messages

Part of the Gabby Gums Discord Logger.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

import db
import utils
from uiElements import StringPage, StringReactPage
from GuildConfigs import GuildLoggingConfig, EventConfig

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


async def show_event_configuration(ctx: commands.Context):

    guild_logging_channel = await ctx.bot.get_event_or_guild_logging_channel(ctx.guild.id)

    if guild_logging_channel is not None:
        default_msg = f"Logging to the default log channel: <#{guild_logging_channel.id}>"
    else:
        default_msg = "**Event disabled because no specific OR default Log channel has been configured.**"

    event_config_msg_fragments = []
    event_configs = await db.get_server_log_configs(ctx.bot.db_pool, ctx.guild.id)
    for event_type in event_configs.available_event_types():
        event = event_configs[event_type]
        if event is None or event.log_channel_id is None:
            event_config_msg_fragments.append(f"**{event_type}:**\n{default_msg}\n")
        elif not event.enabled:
            event_config_msg_fragments.append(f"**{event_type}:**\nEvent Currently Disabled\n")
        else:
            event_config_msg_fragments.append(f"**{event_type}:**\nLogging to <#{event.log_channel_id}>\n")

    event_config_msg_fragments.append(f"\n\nPlease type an event type to edit it's settings or 'cancel' to cancel the operation.")

    event_config_msg = "\n".join(event_config_msg_fragments)
    #
    # embed.add_field(name="Event Configurations", value=f"{event_config_msg}\n\N{ZERO WIDTH NON-JOINER}",
    #                 inline=True)
    embed = discord.Embed(title="Current Event Configurations", description=event_config_msg)
    await ctx.send(embed=embed)


async def get_event_configuration_embed(ctx: commands.Context):

    guild_logging_channel = await ctx.bot.get_event_or_guild_logging_channel(ctx.guild.id)

    if guild_logging_channel is not None:
        default_msg = f"Logging to the default log channel: <#{guild_logging_channel.id}>"
    else:
        default_msg = "**Event disabled because no specific OR default Log channel has been configured.**"

    event_config_msg_fragments = []
    event_configs = await db.get_server_log_configs(ctx.bot.db_pool, ctx.guild.id)
    for event_type in event_configs.available_event_types():
        event = event_configs[event_type]
        if event is None or event.log_channel_id is None:
            event_config_msg_fragments.append(f"**{event_type}:**\n{default_msg}\n")
        elif not event.enabled:
            event_config_msg_fragments.append(f"**{event_type}:**\nEvent Currently Disabled\n")
        else:
            event_config_msg_fragments.append(f"**{event_type}:**\nLogging to <#{event.log_channel_id}>\n")

    event_config_msg_fragments.append(f"\n\n**Enter an event type to edit it's settings**")

    event_config_msg = "\n".join(event_config_msg_fragments)

    embed = discord.Embed(title="Current Event Configurations", description=event_config_msg)
    return embed, event_configs


def get_edit_event_embed(event_type_name: str, event_configs: GuildLoggingConfig) -> discord.Embed:
    configs: EventConfig = event_configs[event_type_name]

    enable_text = "Yes" if configs.enabled else "No"
    log_channel = f"<#{configs.log_channel_id}>" if configs.log_channel_id else "Default Log Channel"
    msg = f"Enabled: {enable_text}\nCurrent Log Channel: {log_channel}\n\n\n**Click the 🔀 to toggle this event or enter a new log channel**\n**Enter 'clear' to set the logging channel back to the default log channel.**\n"

    embed = discord.Embed(title=f"Current {event_type_name} Configuration:",
                          description= msg)
    return embed


class Configuration(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.guild_only()
    @commands.command(brief="Owner only test command")
    async def configtest(self, ctx: commands.Context):
        await ctx.send(f"hello from {__name__}")


    @commands.is_owner()
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command(name="events", aliases=['event', 'configure_events', "setup_events"],
                      brief="Allows for setting per event log channels and/or disabling specific events from being logged.",
                      description="Allows for setting per event log channels and/or disabling specific events from being logged.",
                      usage='<command> [channel]')
    async def configure_event(self, ctx: commands.Context):
        # menu = HWConfigMenu()
        # await menu.start(ctx)
        await self.config_event_menu(ctx)


    async def config_event_menu(self, ctx: commands.Context):
        embed, event_configs = await get_event_configuration_embed(ctx)

        # await show_event_configuration(ctx)
        page = StringReactPage(embed=embed, allowable_responses=event_configs.available_event_types())
        event_type_rsp = await page.run(ctx)
        if event_type_rsp is None:
            return

        # await ctx.send(f"You chose: {response}")
        #
        # edit_responses = ['enable', 'enabled', 'disable', 'channel']
        edit_buttons = [('🔀', 'toggle'), ('🔙', 'back'), ('🛑', 'stop')]
        while True:
            embed = get_edit_event_embed(event_type_rsp, event_configs)
            edit_page = StringReactPage(embed=embed, buttons=edit_buttons, allowable_responses=[])
            edit_rsp = await edit_page.run(ctx)
            # await ctx.send(f"You chose: {edit_rsp}")
            if edit_rsp is None:
                await ctx.send(f"Done!")
                return
            edit_rsp = edit_rsp.lower().strip()
            if edit_rsp == 'stop':
                await ctx.send(f"Done!")
                return
            elif edit_rsp == 'back':
                await self.config_event_menu(ctx)
                return
            elif edit_rsp == 'toggle':
                config: EventConfig = event_configs[event_type_rsp]
                enable_text = "On" if config.enabled else "Off"
                await ctx.send(f'{event_type_rsp} is now {enable_text}!!!')
            elif edit_rsp == 'clear':
                await ctx.send(f'{event_type_rsp} events will now be logged to the Default Log Channel!')
            else:
                try:
                    log_chan = await commands.TextChannelConverter().convert(ctx, edit_rsp)
                    await ctx.send(f'{event_type_rsp} events will now be logged to {log_chan.name}')
                except commands.BadArgument:
                    await ctx.send('Invalid channel!')

    async def edit_event(self, new_configs: GuildLoggingConfig):
        pass

def setup(bot):
    bot.add_cog(Configuration(bot))
