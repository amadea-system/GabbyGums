"""
Cog containing various GG configuration commands.
Commands include:
    Events

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Type, Any

import discord
from discord.ext import commands
import eCommands

import db
from miscUtils import prettify_permission_name, check_permissions
from uiElements import StringReactPage, BoolPage
from GuildConfigs import GuildLoggingConfig, EventConfig, GuildConfigDocs
from utils.moreColors import gabby_gums_dark_green

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)
guild_config_docs = GuildConfigDocs()

VoiceOrTextChannel = Union[discord.TextChannel, discord.VoiceChannel]

# region Embed Getters
async def get_event_configuration_embed(ctx: commands.Context, event_configs: GuildLoggingConfig, final: bool = False) -> discord.Embed:

    embed = discord.Embed(title="Current Event Configurations") if not final else discord.Embed(title="Event Configurations")

    guild_logging_channel = await ctx.bot.get_event_or_guild_logging_channel(ctx.guild.id)

    if guild_logging_channel is not None:
        default_msg = f"Logging to the default log channel: <#{guild_logging_channel.id}>"
    else:
        default_msg = "Event can not be logged. No **Dedicated Log Channel** OR **Default Log Channel** has been configured."

    for event_type in event_configs.available_event_types():
        event_description = f"**{event_type}**\n⁃ _{guild_config_docs[event_type].brief}_"

        event = event_configs[event_type]
        if event is None or (event.log_channel_id is None and event.enabled):
            event_status = f"⁃ {default_msg}"
        elif not event.enabled:
            event_status = f"⁃ Event Currently Disabled"
        else:
            event_status = f"⁃ Logging to <#{event.log_channel_id}>"

        embed.add_field(name="\N{ZERO WIDTH SPACE}", value=f"{event_description}\n{event_status}")

    if not final:
        embed.add_field(name="\N{Zero Width Space}", value=f"\N{Zero Width Space}\n**Enter an event type to edit its settings or click the 🛑 to exit the event configuration menu system**", inline=False)
    else:
        embed.add_field(name="\N{Zero Width Space}",
                        value=f"\N{Zero Width Space}\n**Event Configuration Finished!\n"
                        f"If you need to configure additional events, please use the `{ctx.bot.command_prefix}events` command again.**",
                        inline=False)

    return embed


def get_edit_event_embed(event_type_name: str, event_configs: GuildLoggingConfig, error_message) -> discord.Embed:
    configs: EventConfig = event_configs[event_type_name]
    if configs is None:
        # If there is no config stored in the DB yet, generate a default config to start from.
        configs = EventConfig()

    enable_text = "Yes" if configs.enabled else "No"
    on_off_toggle_text = "Off" if configs.enabled else "On"
    log_channel = f"<#{configs.log_channel_id}>" if configs.log_channel_id else "Default Log Channel"
    msg = f"_{guild_config_docs[event_type_name].full}_\n\nEnabled: **{enable_text}**\n" \
        f"Current Log Channel: **{log_channel}**\n\n\n" \
        f"**Click** the 🔀 to turn this event **{on_off_toggle_text}**.\n" \
        f"**Enter** a **new log channel** to change which channel this event will log to.\n" \
        f"**Enter** `clear` to set the logging channel back to the **default log channel**.\n" \
        f"**Click** the <:backbtn:677188923310735361> to go back to list of all event configurations.\n" \
        f"**Click** the 🛑 to exit the Event Configuration Menu System."

    embed = discord.Embed(title=f"Current {event_type_name} Configuration:", description=msg)

    if error_message is not None:
        embed.add_field(name="\N{ZERO WIDTH SPACE}\n\N{WARNING SIGN} Error \N{WARNING SIGN}", value=error_message)
    return embed
# endregion


class Configuration(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot
        self.default_req_perms = {'read_messages': True, 'send_messages': True, 'embed_links': True}  # Permissions that EVERY channel requires.

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


    # region Event Configuration Menu System


    @commands.has_permissions(manage_messages=True)
    @commands.max_concurrency(1, per=commands.BucketType.member, wait=False)
    @commands.guild_only()
    @commands.command(name="events", aliases=['event', 'configure_events', "setup_events", "config_event"],
                      brief="Allows for setting per event log channels and/or disabling specific events from being logged.",
                      description="Allows for setting per event log channels and/or disabling specific events from being logged.")
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
            await self.finished_embed(ctx, event_configs)
            return

        edit_buttons = [('🔀', 'toggle'), ('<:backbtn:679032730243301397>', 'back')]  # ('🔙', 'back')]  # , ('🛑', 'stop')]

        error_msg = None
        while True:

            embed = get_edit_event_embed(event_type_rsp.response, event_configs, error_msg)
            edit_page = StringReactPage(embed=embed, buttons=edit_buttons, allowable_responses=[])
            edit_rsp = await edit_page.run(ctx)

            if edit_rsp is None:
                await self.finished_embed(ctx, event_configs)
                return

            edit_rsp_str = edit_rsp.response.lower().strip()
            if edit_rsp_str == 'stop':
                await self.finished_embed(ctx, event_configs)
                return

            elif edit_rsp_str == 'back':
                await self.config_event_menu(ctx)
                return

            elif edit_rsp_str == 'toggle':
                event_configs = await self.toggle_event(ctx, event_type_rsp.response, event_configs)
                error_msg = None

            elif edit_rsp_str == 'clear':
                event_configs = await self.clear_log_channel(ctx, event_type_rsp.response, event_configs)
                error_msg = None

            else:
                # Try to get a Valid Channel. If successful, set the log channel, commit changes to the DB, and alert the user.
                try:
                    log_chan = await commands.TextChannelConverter().convert(ctx, edit_rsp_str)
                    event_configs, error_msg = await self.set_log_channel(ctx, log_chan, event_type_rsp.response, event_configs)
                except commands.BadArgument:
                    await ctx.send('Invalid channel!')

    @staticmethod
    async def finished_embed(ctx: commands.Context, event_configs: GuildLoggingConfig):
        # Send a final static embed showing the now configured events.
        final_embed = await get_event_configuration_embed(ctx, event_configs, final=True)
        await ctx.send(embed=final_embed)


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

    async def set_log_channel(self, ctx: commands.Context, new_log_channel: discord.TextChannel, event_name: str, event_configs: GuildLoggingConfig) -> Tuple[GuildLoggingConfig, Optional[str]]:
        # Clear the log channel, commit changes to the DB, and alert the user.
        config: EventConfig = event_configs[event_name]
        if config is None:
            config = EventConfig()

        event_perms = guild_config_docs[event_name].permissions
        ch_perms: discord.Permissions = ctx.guild.me.permissions_in(new_log_channel)

        missing_perms_msg = ""
        for perm, value in ch_perms:
            if (perm in self.default_req_perms or perm in event_perms) and not value:
                if perm == "view_audit_log" or perm == "manage_channels":
                    missing_perms_msg += f"**{prettify_permission_name(perm)}** (Server Permission)\n"
                else:
                    missing_perms_msg += f"**{prettify_permission_name(perm)}**\n"

        if not missing_perms_msg:

            config.log_channel_id = new_log_channel.id
            event_configs[event_name] = config
            await self.edit_event(ctx.guild, event_configs)

            await ctx.send(f'**{event_name}** events will now be logged to the **<#{new_log_channel.id}>**')
            error_msg = None
        else:

            error_msg = f"Could not set the log channel to <#{new_log_channel.id}>.\n" \
                        f"Gabby Gums is missing the following critical permissions in <#{new_log_channel.id}> which would prevent log messages from being sent:\n"
            error_msg += missing_perms_msg
            error_msg += "\nPlease fix the permissions and try again or choose a different channel."

        # Return the modified event configs
        return event_configs, error_msg

    async def edit_event(self, guild: discord.Guild, new_configs: GuildLoggingConfig):
        await db.set_server_log_configs(self.bot.db_pool, guild.id, new_configs)
    # endregion

    # region Log Channel Command
    # ----- Logging Channel Commands ----- #
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.group(name="log_channel", aliases=["log_ch"], brief="Sets/unsets/shows the default logging channel.",
                     description="Sets/unsets/shows the default logging channel.",  # , usage='<command> [channel]'
                     examples=["set #logs", "set 123456789123456789", 'show', 'unset']
                     )
    async def logging_channel(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.logging_channel)


    @logging_channel.command(name="set", brief="Sets the default logging channel.",
                             description="Sets the default logging channel.",
                             examples=["#logs", "123456789123456789"])
    async def set_logging_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        ch_perm: discord.Permissions = channel.guild.me.permissions_in(channel)
        if ch_perm.send_messages and ch_perm.embed_links and ch_perm.read_messages:
            await db.update_log_channel(self.bot.db_pool, ctx.guild.id, channel.id)
            await ctx.send("Default Log channel set to <#{}>".format(channel.id))
        else:
            msg = f"Can not set the Default Log Channel to <#{channel.id}>.\n" \
                  f"Gabby Gums is missing the following critical permissions in <#{channel.id}> which would prevent log messages from being sent:\n"
            if not ch_perm.send_messages:
                msg += "**Send Messages Permission**\n"
            if not ch_perm.read_messages:
                msg += "**Read Messages Permission**\n"
            if not ch_perm.embed_links:
                msg += "**Embed Links Permission**\n"
            msg += "\nPlease fix the permissions and try again or choose a different channel."
            await ctx.send(msg)


    @logging_channel.command(name="unset", brief="Unsets the default log channel", description="Unsets the default log channel")
    async def unset_logging_channel(self, ctx: commands.Context):

        await db.update_log_channel(self.bot.db_pool, ctx.guild.id, log_channel_id=None)
        await ctx.send("The Default Log channel has been cleared. "
                       "Gabby Gums will no longer be able to log events which do not have a specific log channel set unless a new default log channel is set.")


    @logging_channel.command(name="show", brief="Shows the default logging channel",
                             description="Shows what channel is currently configured as the default logging channel")
    async def show_logging_channel(self, ctx: commands.Context):

        _log_channel = await db.get_log_channel(self.bot.db_pool, ctx.guild.id)
        if _log_channel is not None:
            await ctx.send("The Default Log Channel is currently set to <#{}>".format(_log_channel))
        else:
            await ctx.send(
                "No Default Log Channel is configured. You can use `g!log_channel set` to set a new Default Log Channel.")
    # endregion

    # region Reset Command

    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.command(name="reset",
                      brief="Resets all settings and stored data for your server.",
                      description="Resets all settings and stored data for your server. **Caution, this can not be undone!**")
    async def reset_server_info(self, ctx: commands.Context):

        conf_embed = discord.Embed(title="**Are You Sure?**",
                                   description="This will **completely** wipe all data relating to this server from the Gabby Gums Database.\n"
                                               "This includes information on banned Plural Kit system accounts, all cached messages (in the database), "
                                               "and all configured settings such as Log channels, enabled/disabled events, ignored users/channels/categories.\n\n"
                                               "This action **can not** be undone and you will have to reset up Gabby Gums from the beginning.\n\n"
                                               "Click the ✅ to continue\nclick the ❌ to cancel.",
                                   color=gabby_gums_dark_green())
        conf_page = BoolPage(embed=conf_embed)

        confirmation = await conf_page.run(ctx)

        if confirmation is None:
            await ctx.send("❌ Command Timed Out! Settings have **not** been reset.")

        elif confirmation is False:
            await ctx.send("❌ Command Canceled. Settings have **not** been reset.")

        elif confirmation is True:
            await db.remove_server(self.bot.db_pool, ctx.guild.id)
            await db.add_server(self.bot.db_pool, ctx.guild.id, ctx.guild.name)
            await ctx.send("✅ **ALL settings have now been reset!**\nTo continue using Gabby Gums, please begin re-setting up the bot.")

    # endregion

    # region Ignore/Redirect User Commands
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.group(name="user_overrides", aliases=["ignore_user"],
                     brief="Ignore or Redirect logs from specific users",
                     description="Allows you to configure Gabby Gums to ignore or redirect logs for specific users.",
                     usage='<command> [Member] [Channel]',
                     examples=["list", "redirect @Hibiki #Hibiki-logs", "ignore @Hibiki"])
    async def user_overrides(self, ctx: commands.Context):
        """This command allows you to have Gabby Gums ignore events from users and/or redirect the logs for those events to different log channels.
        For example, you could use this to have gabby gums ignore a bot that's filling up your logs with spam or perhaps redirect the logs of moderators or users on probation.

        Please be aware that these settings override the event configurations and Channel Overrides.
        So if for instance were to have all the delete logs going to a channel called #delete-logs and you set up a user override for a user named Bob to redirect their logs to #bob-log, all of logs regarding Bob, including their deleted messages would go to #bob-log (of course everyone else's logs would go to where ever they normally would have)."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.user_overrides)


    @user_overrides.command(name="list", brief="Lists users that are ignored or being redirected")
    async def u_list(self, ctx: commands.Context):
        embed = discord.Embed(title="Ignored & Redirected Users", color=gabby_gums_dark_green())
        msg = ["The following users are being ignored or redirected to alternative log channels by Gabby Gums:"]
        _ignored_users = await db.get_users_overrides(self.bot.db_pool, ctx.guild.id)
        for ignored_user in _ignored_users:
            if ignored_user['log_ch'] is not None:
                msg.append(f"Events from <@{ignored_user['user_id']}> are being redirected to <#{ignored_user['log_ch']}>.")
            else:
                msg.append(f"Events from <@{ignored_user['user_id']}> are being ignored.")
        embed.description = "\n".join(msg)
        await ctx.send(embed=embed)


    @user_overrides.command(name="ignore", brief="Make Gabby Gums ignore a member")
    async def u_ignore(self, ctx: commands.Context, member: discord.Member):

        await db.add_user_override(self.bot.db_pool, ctx.guild.id, member.id, None)
        embed = discord.Embed(color=gabby_gums_dark_green(),
                              description=f"Events from <@{member.id}> will now be ignored.")
        await ctx.send(embed=embed)


    @user_overrides.command(name="redirect", brief="Make a specific users logs be redirected to a specific log channel")
    async def u_redirect(self, ctx: commands.Context, member: discord.Member, channel: discord.TextChannel):

        missing_perms = check_permissions(channel)
        if len(missing_perms) > 0:
            msg = [f"Could not set the log channel to <#{channel.id}>.",
                   f"Gabby Gums is missing the following critical permissions in <#{channel.id}> which would prevent log messages from being sent:"]
            for perm in missing_perms:
                msg.append(f"**{prettify_permission_name(perm)}**")
            msg.append("\nPlease fix the permissions and try again or choose a different channel.")

        else:
            await db.add_user_override(self.bot.db_pool, ctx.guild.id, member.id, channel.id)
            msg = [f"Events from <@{member.id}> have been redirected to <#{channel.id}>.\n",
                   f"Please note, that if this user was previously ignored, that will no longer be the case."]

        embed = discord.Embed(color=gabby_gums_dark_green(),
                              description="\n".join(msg))

        await ctx.send(embed=embed)


    @user_overrides.command(name="remove", brief="Stop ignoring or redirecting a member")
    async def u_remove(self, ctx: commands.Context, member: discord.Member):
        await db.remove_user_override(self.bot.db_pool, ctx.guild.id, member.id)

        embed = discord.Embed(color=gabby_gums_dark_green(),
                              description=f"Events from <@{member.id}> will no longer be ignored or redirected.\n")
        await ctx.send(embed=embed)

    # endregion

    # region Ignore/Redirect Channel Commands
    # ----- Ignore Channel Commands ----- #
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @eCommands.group(name="channel_override", aliases=["channel_overrides", "ch_or", "ignore_channel"],
                     brief="Ignore or Redirect logs from specific channels",
                     description="Allows you to configure Gabby Gums to ignore or redirect logs for specific channels.",
                     usage='<Command> [Channel] [Log Channel]',
                     examples=["list", "redirect #vents #Serious-logs", "ignore #bots"])
    async def channel_overide(self, ctx: commands.Context):
        """This command allows you to have Gabby Gums ignore events that originate in channels and/or redirect the logs for those events to different log channels.
            For example, you could use this to have gabby gums ignore a noisy bot channel or perhaps redirect the logs of a serious channel to a safer log channel.
            """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.channel_overide)


    @channel_overide.command(name="list", brief="Lists channels that are ignored or being redirected")
    async def ch_list(self, ctx: commands.Context):

        channel_overrides = await db.get_channel_overrides(self.bot.db_pool, ctx.guild.id)
        if len(channel_overrides) > 0:
            msg = ["The following channels are being ignored or having their events redirected to alternative log channels by Gabby Gums:"]
            for ch_override in channel_overrides:
                if ch_override['log_ch'] is not None:
                    msg.append(f"Events from <#{ch_override['channel_id']}> are being redirected to <#{ch_override['log_ch']}>.")
                else:
                    msg.append(f"Events from <#{ch_override['channel_id']}> are being ignored.")
        else:
            msg = ["No channels are being ignored or having their events redirected."]

        embed = discord.Embed(title="Ignored & Redirected Channels", description="\n".join(msg), color=gabby_gums_dark_green())
        await ctx.send(embed=embed)


    @channel_overide.command(name="ignore", brief="Make Gabby Gums ignore a channel")
    async def ch_ignore(self, ctx: commands.Context, channel: VoiceOrTextChannel):

        await db.add_channel_override(self.bot.db_pool, ctx.guild.id, channel.id, None)
        embed = discord.Embed(color=gabby_gums_dark_green(),
                              description=f"Events that occur in <#{channel.id}> will now be ignored.")
        await ctx.send(embed=embed)


    @channel_overide.command(name="redirect", brief="Make a specific channels logs be redirected to a specific log channel")
    async def ch_redirect(self, ctx: commands.Context, channel: VoiceOrTextChannel, log_channel: discord.TextChannel):

        missing_perms = check_permissions(log_channel)
        if len(missing_perms) > 0:
            msg = [f"Could not set the log channel to <#{log_channel.id}>.",
                   f"Gabby Gums is missing the following critical permissions in <#{log_channel.id}> which would prevent log messages from being sent:"]
            for perm in missing_perms:
                msg.append(f"**{prettify_permission_name(perm)}**")
            msg.append("\nPlease fix the permissions and try again or choose a different channel.")

        else:
            await db.add_channel_override(self.bot.db_pool, ctx.guild.id, channel.id, log_channel.id)
            msg = [f"Events that occur in <#{channel.id}> have been redirected to <#{log_channel.id}>.\n",
                   f"Please note, that if this channel was previously ignored, that will no longer be the case."]

        embed = discord.Embed(color=gabby_gums_dark_green(),
                              description="\n".join(msg))
        await ctx.send(embed=embed)


    @channel_overide.command(name="remove", brief="Stop ignoring or redirecting a channel")
    async def ch_remove(self, ctx: commands.Context, channel: VoiceOrTextChannel):
        await db.remove_channel_override(self.bot.db_pool, ctx.guild.id, channel.id)

        embed = discord.Embed(color=gabby_gums_dark_green(),
                              description=f"Events that occur in <#{channel.id}> will no longer be ignored or redirected.\n")
        await ctx.send(embed=embed)

    # endregion


def setup(bot):
    bot.add_cog(Configuration(bot))
