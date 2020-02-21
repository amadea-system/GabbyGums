"""
Cog containing various developer only commands used for debugging purposes only.
Commands include:
    devtest
    dump
    past_messages

Part of the Gabby Gums Discord Logger.
"""

# import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Type, Any

import discord
from discord.ext import commands

import db
import utils
from uiElements import StringPage, StringReactPage, Page
from GuildConfigs import GuildLoggingConfig, EventConfig, GuildConfigDocs

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)
guild_config_docs = GuildConfigDocs()


# region Embed Getters
async def get_event_configuration_embed(ctx: commands.Context, event_configs: GuildLoggingConfig) -> discord.Embed:

    guild_logging_channel = await ctx.bot.get_event_or_guild_logging_channel(ctx.guild.id)

    if guild_logging_channel is not None:
        default_msg = f"Logging to the default log channel: <#{guild_logging_channel.id}>"
    else:
        default_msg = "Event disabled. No **Dedicated Log Channel** OR **Default Log Channel** has been configured."

    event_config_msg_fragments = []
    for event_type in event_configs.available_event_types():
        event_config_msg_fragments.append(f"**{event_type}:**\n⁃ _{guild_config_docs[event_type].brief}_")
        event = event_configs[event_type]
        if event is None or (event.log_channel_id is None and event.enabled):
            event_config_msg_fragments.append(f"⁃ {default_msg}\n")
        elif not event.enabled:
            event_config_msg_fragments.append(f"⁃ Event Currently Disabled\n")
        else:
            event_config_msg_fragments.append(f"⁃ Logging to <#{event.log_channel_id}>\n")

    event_config_msg_fragments.append(f"\n\n**Enter an event type to edit it's settings or click the 🛑 to exit**")

    event_config_msg = "\n".join(event_config_msg_fragments)

    embed = discord.Embed(title="Current Event Configurations", description=event_config_msg)
    return embed


def get_edit_event_embed(event_type_name: str, event_configs: GuildLoggingConfig) -> discord.Embed:
    # log.info(event_configs)
    configs: EventConfig = event_configs[event_type_name]
    if configs is None:
        # Generate a default config
        configs = EventConfig()

    enable_text = "Yes" if configs.enabled else "No"
    onoff_toggle_text = "Off" if configs.enabled else "On"
    log_channel = f"<#{configs.log_channel_id}>" if configs.log_channel_id else "Default Log Channel"
    msg = f"_{guild_config_docs[event_type_name].full}_\n\nEnabled: **{enable_text}**\n" \
        f"Current Log Channel: **{log_channel}**\n\n\n" \
        f"**Click** the 🔀 to turn this event **{onoff_toggle_text}**.\n" \
        f"**Enter** a **new log channel** to change which channel this event will log to.\n" \
        f"**Enter** `clear` to set the logging channel back to the **default log channel**.\n" \
        f"**Click** the <:backbtn:677188923310735361> to go back to list of all event configurations."

    embed = discord.Embed(title=f"Current {event_type_name} Configuration:",
                          description=msg)
    return embed
# endregion


class Configuration(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

    async def handle_errors(self, ctx: commands.Context, error: Type[Exception], errors_to_ignore: Tuple[Type[Exception]]):

        if len(errors_to_ignore) > 0 and isinstance(error, errors_to_ignore):
            # Don't handle exceptions that have already been handled.
            return

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("⚠ This command can not be used in DMs!!!")
            return
        elif isinstance(error, commands.CommandNotFound):
            await ctx.send("⚠ Invalid Command!!!")
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "⚠ You need the **Manage Messages** permission to use this command".format(error.missing_perms))
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("⚠ {}".format(error))
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠ {}".format(error))
        else:
            await ctx.send("⚠ {}".format(error))
            raise error

    @commands.is_owner()
    @commands.guild_only()
    @commands.command(brief="Owner only test command")
    async def configtest(self, ctx: commands.Context):
        await ctx.send(f"hello from {__name__}")


    # region Event Configuration Menu System
    @commands.has_permissions(manage_messages=True)
    @commands.max_concurrency(1, per=commands.BucketType.member, wait=False)
    @commands.guild_only()
    @commands.command(name="events", aliases=['event', 'configure_events', "setup_events", "config_event"],
                      brief="Allows for setting per event log channels and/or disabling specific events from being logged.",
                      description="Allows for setting per event log channels and/or disabling specific events from being logged.",
                      usage='<command> [channel]')
    async def configure_event(self, ctx: commands.Context):
        await self.config_event_menu(ctx)

    @configure_event.error
    async def configure_event_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            # await ctx.send('The Event Configuration Menu is already running!')
            pass

        await self.handle_errors(ctx, error, (commands.MaxConcurrencyReached,))

    async def config_event_menu(self, ctx: commands.Context, previous_ui_element: Optional[discord.Message] = None):
        event_configs = await db.get_server_log_configs(ctx.bot.db_pool, ctx.guild.id)
        embed = await get_event_configuration_embed(ctx, event_configs)

        page = StringReactPage(embed=embed, allowable_responses=event_configs.available_event_types())
        event_type_rsp = await page.run(ctx)
        if event_type_rsp is None:
            return

        edit_buttons = [('🔀', 'toggle'), ('<:backbtn:679032730243301397>', 'back')]#('🔙', 'back')]  # , ('🛑', 'stop')]

        # edit_msg = None
        while True:
            # last_msg = edit_msg or event_type_rsp.ui_message
            embed = get_edit_event_embed(event_type_rsp.response, event_configs)
            edit_page = StringReactPage(embed=embed, buttons=edit_buttons, allowable_responses=[])
            edit_rsp = await edit_page.run(ctx)

            if edit_rsp is None:
                # await ctx.send(f"Done!")
                return
            # edit_msg = edit_rsp.ui_message
            edit_rsp_str = edit_rsp.response.lower().strip()
            if edit_rsp_str == 'stop':
                await ctx.send(f"Done!")
                # log.info("exiting config_event_menu via stop button.")
                return
            elif edit_rsp_str == 'back':
                # log.info("Recursively calling config_event_menu via back button.")
                await self.config_event_menu(ctx)
                # log.info("exiting from back button.")
                return
            elif edit_rsp_str == 'toggle':
                event_configs = await self.toggle_event(ctx, event_type_rsp.response, event_configs)

            elif edit_rsp_str == 'clear':
                event_configs = await self.clear_log_channel(ctx, event_type_rsp.response, event_configs)

            else:
                # Try to get a Valid Channel. If successful, set the log channel, commit changes to the DB, and alert the user.
                try:
                    log_chan = await commands.TextChannelConverter().convert(ctx, edit_rsp_str)
                    event_configs = await self.set_log_channel(ctx, log_chan, event_type_rsp.response, event_configs)
                except commands.BadArgument:
                    await ctx.send('Invalid channel!')

    async def toggle_event(self, ctx: commands.Context, event_name: str, event_configs: GuildLoggingConfig) -> GuildLoggingConfig:
        # Invert the current status, commit changes to the DB, and alert the user.
        config: EventConfig = event_configs[event_name]
        if config is None:
            config = EventConfig()
        config.enabled = False if config.enabled else True
        toggle_text = "On" if config.enabled else "Off"
        event_configs[event_name] = config
        await self.edit_event(ctx.guild, event_configs)

        await ctx.send(f'{event_name} is now {toggle_text}!!!')

        # Return the modified event configs
        return event_configs

    async def clear_log_channel(self, ctx: commands.Context, event_name: str, event_configs: GuildLoggingConfig) -> GuildLoggingConfig:
        # Clear the log channel, commit changes to the DB, and alert the user.
        config: EventConfig = event_configs[event_name]
        if config is None:
            config = EventConfig()
        config.log_channel_id = None
        event_configs[event_name] = config
        await self.edit_event(ctx.guild, event_configs)

        await ctx.send(f'**{event_name}** events will now be logged to the **Default Log Channel!**')

        # Return the modified event configs
        return event_configs

    async def set_log_channel(self, ctx: commands.Context, new_log_channel: discord.TextChannel, event_name: str, event_configs: GuildLoggingConfig) -> GuildLoggingConfig:
        # Clear the log channel, commit changes to the DB, and alert the user.
        config: EventConfig = event_configs[event_name]
        if config is None:
            config = EventConfig()
        config.log_channel_id = new_log_channel.id
        event_configs[event_name] = config
        await self.edit_event(ctx.guild, event_configs)

        await ctx.send(f'**{event_name}** events will now be logged to the **<#{new_log_channel.id}>**')

        # Return the modified event configs
        return event_configs

    async def edit_event(self, guild: discord.Guild, new_configs: GuildLoggingConfig):
        await db.set_server_log_configs(self.bot.db_pool, guild.id, new_configs)
    # endregion


def setup(bot):
    bot.add_cog(Configuration(bot))
