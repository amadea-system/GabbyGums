'''

'''

import time
import json
import os
import logging
import traceback
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Union
from datetime import timedelta

import psutil
import asyncpg
import aiohttp
import discord
from discord.ext import commands
from discord.utils import oauth_url

import db
import embeds
import utils
import GuildConfigs
from imgUtils.avatarChangedImgProcessor import get_avatar_changed_image
from bot import GGBot

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

client = GGBot(command_prefix="g!",
               max_messages=100000,
               # description="A simple logging bot that ignores PluralKit proxies.\n",
               owner_id=389590659335716867,
               case_insensitive=True)
client.remove_command("help")  # Remove the built in help command so we can make the about section look nicer.


async def is_channel_ignored(pool: asyncpg.pool.Pool, guild_id: int, channel_id: int) -> bool:
    _ignored_channels = await db.get_ignored_channels(pool, int(guild_id))
    if int(channel_id) in _ignored_channels:
        return True  # TODO: Optimise this
    return False


async def is_user_ignored(pool: asyncpg.pool.Pool, guild_id: int, user_id: int) -> bool:
    _ignored_users = await db.get_ignored_users(pool, int(guild_id))
    if int(user_id) in _ignored_users:
        return True  # This is a message from a user the guild does not wish to log. Do not log the event.
    return False


async def is_category_ignored(pool: asyncpg.pool.Pool, guild_id: int, category: Optional[discord.CategoryChannel]) -> bool:
    if category is not None:  # If channel is not in a category, don't bother querying DB
        _ignored_categories = await db.get_ignored_categories(pool, int(guild_id))
        if category.id in _ignored_categories:
            return True
    return False


async def get_event_or_guild_logging_channel(pool: asyncpg.pool.Pool, guild_id: int, event_type: Optional[str] = None) -> Optional[discord.TextChannel]:
    if event_type is not None:
        log_configs = await db.get_server_log_configs(pool, guild_id)
        event_configs = log_configs[event_type]
        if event_configs is not None:
            if event_configs.enabled is False:
                return None  # Logs for this type are disabled. Exit now.
            if event_configs.log_channel_id is not None:
                return await get_channel_safe(event_configs.log_channel_id)  # return event specific log channel

    # No valid event specific configs exist. Attempt to use default log channel.
    _log_channel_id = await db.get_log_channel(pool, guild_id)
    if _log_channel_id is not None:
        return await get_channel_safe(_log_channel_id)

    # No valid event configs or global configs found. Only option is to silently fail
    return None


async def get_channel_safe(channel_id: int) -> Optional[discord.TextChannel]:
    channel = client.get_channel(channel_id)
    if channel is None:
        logging.info("bot.get_channel failed. Querying API...")
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            return None
    return channel


@client.event
async def on_ready():
    logging.info('Connected using discord.py version {}!'.format(discord.__version__))
    logging.info('Username: {0.name}, ID: {0.id}'.format(client.user))
    logging.info("Connected to {} servers.".format(len(client.guilds)))
    logging.info('------')

    activity = discord.Game("{}help".format(client.command_prefix))
    await client.change_presence(status=discord.Status.online, activity=activity)

    # ensure the invite cache is upto date on connection.
    logging.info("Refreshing Invite Cache.")
    for guild in client.guilds:
        await update_invite_cache(guild)


# ----- Help & About Commands ----- #
@client.command(name="Help", hidden=True)
async def _help(ctx, *args):

    if 'error_log_channel' not in config:
        return
    error_log_channel = client.get_channel(config['error_log_channel'])
    await error_log_channel.send("help called by <@{}> - {}#{}".format(ctx.author.id, ctx.author.name, ctx.author.discriminator))
    print("help called by <@{}> - {}#{}".format(ctx.author.id, ctx.author.name, ctx.author.discriminator))
    if args:
        await ctx.send_help(*args)
    else:
        await ctx.send(embed=embeds.about_message())
        await ctx.send_help()


@client.command(name="About", hidden=True)
async def _about(ctx):
    await ctx.send(embed=embeds.about_message())


# ----- Logging Channel Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="log_channel", brief="Sets/unsets/shows the channel currently assigned for logging.",
              description="Sets/unsets/shows the channel currently assigned for logging."
                          "\n Use `set` in the channel you want to designate for logging.",
              usage='<command> [channel]')
async def logging_channel(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(logging_channel)


@logging_channel.command(name="set", brief="Sets which channel the bot will log to.",
                         description="Sets which channel the bot will log to.")
async def set_logging_channel(ctx: commands.Context, channel: discord.TextChannel):
    bot: GGBot = ctx.bot
    await db.update_log_channel(bot.db_pool, ctx.guild.id, channel.id)
    await ctx.send("Logging channel set to <#{}>".format(channel.id))


@logging_channel.command(name="unset", brief="Unsets the log channel", description="Unsets the log channel")
async def unset_logging_channel(ctx: commands.Context):
    bot: GGBot = ctx.bot
    await db.update_log_channel(bot.db_pool, ctx.guild.id, log_channel_id=None)
    await ctx.send("Logging channel has been cleared. "
                   "Gabby Gums will no longer be able to log events unless a new logging channel is set")


@logging_channel.command(name="show", brief="Shows what channel is currently configured for logging",
                         description="Shows what channel is currently configured for logging")
async def show_logging_channel(ctx: commands.Context):
    bot: GGBot = ctx.bot
    _log_channel = await db.get_log_channel(bot.db_pool, ctx.guild.id)
    if _log_channel is not None:
        await ctx.send("Logging channel is currently set to <#{}>".format(_log_channel))
    else:
        await ctx.send("No channel is configured. Please use `g!log_ch set` in the channel you wish to use for logging.")


# ----- Ignore User Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="ignore_user", brief="Sets which users/bots will be ignored by Gabby Gums",
              description="Sets which users/bots will be ignored by Gabby Gums",
              usage='<command> [Member]')
async def ignore_user(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(ignore_user)


@ignore_user.command(name="list", brief="Lists which users are currently ignored.")
async def _list(ctx: commands.Context):
    await ctx.send("The following users are being ignored by Gabby Gums:")
    bot: GGBot = ctx.bot
    _ignored_users = await db.get_ignored_users(bot.db_pool, ctx.guild.id)
    for member_id in _ignored_users:
        await ctx.send("<@{}>".format(member_id))


@ignore_user.command(name="add", brief="Add a new member to be ignored")
async def add(ctx: commands.Context, member: discord.Member):
    bot: GGBot = ctx.bot
    await db.add_ignored_user(bot.db_pool, ctx.guild.id, member.id)
    await ctx.send("<@{}> - {}#{} has been ignored.".format(member.id, member.name, member.discriminator))


@ignore_user.command(name="remove", brief="Stop ignoring a member")
async def remove(ctx: commands.Context, member: discord.Member):
    bot: GGBot = ctx.bot
    await db.remove_ignored_user(bot.db_pool, ctx.guild.id, member.id)
    await ctx.send("<@{}> - {}#{} is no longer being ignored.".format(member.id, member.name, member.discriminator))


# ----- Ignore Channel Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="ignore_channel", brief="Sets which channels will be ignored by Gabby Gums",
              description="Sets which channels will be ignored by Gabby Gums",
              usage='<command> [channel]')
async def ignore_channel(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(ignore_channel)


@ignore_channel.command(name="list", brief="Lists which channels are currently ignored.")
async def _list(ctx: commands.Context):
    bot: GGBot = ctx.bot
    _ignored_channels = await db.get_ignored_channels(bot.db_pool, ctx.guild.id)
    if len(_ignored_channels) > 0:
        await ctx.send("The following channels are being ignored by Gabby Gums:")
        for channel_id in _ignored_channels:
            await ctx.send("<#{}>".format(channel_id))
    else:
        await ctx.send("No channels are being ignored by Gabby Gums.")


@ignore_channel.command(name="add", brief="Add a new channel to be ignored")
async def add(ctx: commands.Context, channel: discord.TextChannel):
    bot: GGBot = ctx.bot
    await db.add_ignored_channel(bot.db_pool, ctx.guild.id, channel.id)
    await ctx.send("<#{}> has been ignored.".format(channel.id))


@ignore_channel.command(name="remove", brief="Stop ignoring a channel")
async def remove(ctx: commands.Context, channel: discord.TextChannel):
    bot: GGBot = ctx.bot
    await db.remove_ignored_channel(bot.db_pool, ctx.guild.id, channel.id)
    await ctx.send("<#{}> is no longer being ignored.".format(channel.id))


# ----- Ignore Category Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="ignore_category", brief="Sets which categories will be ignored by Gabby Gums",
              description="Sets which categories will be ignored by Gabby Gums. "
                          "When using subcommands that require including the category (add/remove) it is suggested to use the id of the category. "
                          "If you choose to use the name instead, be aware that despite Discord showing all categories to be uppercase, "
                          "this is not true behind the scenes. "
                          "As such you must be sure to match the capitalism to be the same as when you created it.",
              usage='<command> [category]')
async def ignore_category(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(ignore_category)


@ignore_category.command(name="list", brief="Lists which categories are currently ignored.")
async def list_categories(ctx: commands.Context):
    bot: GGBot = ctx.bot
    _ignored_categories = await db.get_ignored_categories(bot.db_pool, ctx.guild.id)
    if len(_ignored_categories) > 0:
        await ctx.send("The following categories are being ignored by Gabby Gums:")
        for category_id in _ignored_categories:
            await ctx.send("<#{}>".format(category_id))
    else:
        await ctx.send("No categories are being ignored by Gabby Gums.")


@ignore_category.command(name="add", brief="Add a new category to be ignored")
async def add_category(ctx: commands.Context, *, category: discord.CategoryChannel):
    bot: GGBot = ctx.bot
    await db.add_ignored_category(bot.db_pool, ctx.guild.id, category.id)
    await ctx.send("<#{}> has been ignored.".format(category.id))


@ignore_category.command(name="remove", brief="Stop ignoring a category")
async def remove_category(ctx: commands.Context, *, category: discord.CategoryChannel):
    bot: GGBot = ctx.bot
    await db.remove_ignored_category(bot.db_pool, ctx.guild.id, category.id)
    await ctx.send("<#{}> is no longer being ignored.".format(category.id))


# ----- Event Management Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="config_event", brief="Allows for setting per event log channels and/or disabling specific events from being logged.",
              description="Allows for setting per event log channels and/or disabling specific events from being logged.",
              usage='<command> [channel]')
async def config_event(ctx: commands.Context):
    if ctx.invoked_subcommand is None:

        help_msg = "This command allows for setting per event log channels and/or disabling specific events from being logged.\n" \
                   "The following event types are configurable:```{}```\n" \
                   "To set a specific logging channel for a specific event type use the following command structure:\n```{command_prefix}config_event channel [event type] [channel mention or id]```\n" \
                   "For example:```{command_prefix}config_event channel member_join #join-logs``` would set all log messages of people joining to the channel #join-logs.\n\n" \
                   "To clear a specific logging channel for a specific event type use the following command structure:\n```{command_prefix}config_event channel [event type]```\n" \
                   "For example:```{command_prefix}config_event channel member_join``` would set all log messages of people joining back to the default log channel.\n\n" \
                   "To enable / disable a specific event type use the following command structure:\n```{command_prefix}config_event enabled [event type] [True or False]```\n" \
                   "For example:```{command_prefix}config_event enabled message_edit False``` would disable all log messages of edited messages.\n".format(", ".join(GuildConfigs.GuildLoggingConfig().available_event_types()), command_prefix=client.command_prefix)

        await ctx.send(help_msg)


@config_event.command(name="channel")
async def _channel(ctx: commands.Context, event_type: str, channel: Optional[discord.TextChannel] = None):
    bot: GGBot = ctx.bot
    event_types = GuildConfigs.GuildLoggingConfig().available_event_types()
    event_type = event_type.lower()
    if event_type not in event_types:
        await ctx.send("{} is not a valid event type!\n The following event types are configurable:``` {}```".format(event_type, ", ".join(event_types)))
        return
    else:
        guild_event_configs = await db.get_server_log_configs(bot.db_pool, ctx.guild.id)
        channel_id = channel.id if channel is not None else None
        if guild_event_configs[event_type] is not None:
            guild_event_configs[event_type].log_channel_id = channel_id
        else:
            guild_event_configs[event_type] = GuildConfigs.EventConfig(log_channel_id=channel_id)
        await db.set_server_log_configs(bot.db_pool, ctx.guild.id, guild_event_configs)
        if channel is not None:
            await ctx.send("{} messages will now be logged to #{}".format(event_type, channel.name))
        else:  # TODO: Add the default log channels name to the following message.
            await ctx.send("{} messages will now be logged to the default log channel.".format(event_type))


@config_event.command(name="enabled")
async def enabled(ctx: commands.Context, event_type: str, is_enabled: bool):
    bot: GGBot = ctx.bot
    event_types = GuildConfigs.GuildLoggingConfig().available_event_types()
    event_type = event_type.lower()
    if event_type not in event_types:
        await ctx.send("{} is not a valid event type!\nThe following event types are configurable:``` {}```".format(
            event_type, ", ".join(event_types)))
        return
    else:
        guild_event_configs = await db.get_server_log_configs(bot.db_pool, ctx.guild.id)
        if guild_event_configs[event_type] is not None:
            guild_event_configs[event_type].enabled = is_enabled
        else:
            guild_event_configs[event_type] = GuildConfigs.EventConfig(enabled=is_enabled)
        await db.set_server_log_configs(bot.db_pool, ctx.guild.id, guild_event_configs)
        if is_enabled is True:
            await ctx.send("{} messages will now be logged.".format(event_type))
        else:
            await ctx.send("{} messages will no longer be logged.".format(event_type))


# ----- Data management commands ----- #


@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="reset",
              brief="**Completely resets** all configuration and stored data for your server. **Caution, this can not be undone!**")
async def reset_server_info(ctx: commands.Context):
    # TODO: Add warning and confirmation
    bot: GGBot = ctx.bot
    await db.remove_server(bot.db_pool, ctx.guild.id)
    await db.add_server(bot.db_pool, ctx.guild.id, ctx.guild.name)
    await ctx.send("**ALL Settings have been reset!**")


# ----- Invite Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="invites",
              brief="Allows for naming invites for easier identification and listing details about them.",
              description="Allows for naming invites for easier identification and listing details about them.",
              usage='<command> [Invite ID]')
async def invite_manage(ctx: commands.Context):
    if not ctx.guild.me.guild_permissions.manage_guild:
        await ctx.send("⚠ Gabby gums needs the **Manage Server** permission for invite tracking.")
        return
    else:
        if ctx.invoked_subcommand is None:
            await ctx.send_help(invite_manage)


@invite_manage.command(name="list", brief="Lists the invites in the server and if they have a defined name.")
async def _list_invites(ctx: commands.Context):
    if ctx.guild.me.guild_permissions.manage_guild:
        await update_invite_cache(ctx.guild)  # refresh the invite cache.
        invites: db.StoredInvites = await get_stored_invites(ctx.guild.id)
        embed = discord.Embed(title="Current Invites", color=0x9932CC)

        embed_count = 0
        for invite in invites.invites:
            embed.add_field(name=invite.invite_id,
                            value="Uses: {}\n Nickname: {}".format(invite.uses, invite.invite_name))
            embed_count += 1
            if embed_count == 25:
                await ctx.send(embed=embed)
                embed = discord.Embed(title="Current Invites Cont.", color=0x9932CC)

        if embed_count % 25 != 0:
            await ctx.send(embed=embed)


@invite_manage.command(name="name", brief="Lets you give an invite a nickname so it can be easier to identify.",
                       usage='invites name [Invite ID] [Invite Nickname]')
async def _name_invite(ctx: commands.Context, invite_id: discord.Invite, nickname: str = None):
    bot: GGBot = ctx.bot
    if ctx.guild.me.guild_permissions.manage_guild:
        await update_invite_cache(ctx.guild)  # refresh the invite cache.
        await db.update_invite_name(bot.db_pool, ctx.guild.id, invite_id.id, invite_name=nickname)
        await ctx.send("{} has been given the nickname: {}".format(invite_id.id, nickname))


@invite_manage.command(name="unname", brief="Removes the name from an invite.")
async def _unname_invite(ctx: commands.Context, invite_id: discord.Invite):
    bot: GGBot = ctx.bot
    if ctx.guild.me.guild_permissions.manage_guild:
        await update_invite_cache(ctx.guild)  # refresh the invite cache.
        await db.update_invite_name(bot.db_pool, ctx.guild.id, invite_id.id)
        await ctx.send("{} no longer has a nickname.".format(invite_id.id))


# ----- Misc Commands ----- #
@client.command(name='bot_invite',
                brief='Get an invite for Gabby Gums.',
                description='get an invite for Gabby Gums.')
async def invite_link_command(ctx: commands.Context):
    # Todo: Calculate permissions instead of hardcoding and use discord.utils.oauth_url
    invite = "https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions={}".format(client.user.id, 380096)
    await ctx.send("Here's a link to invite Gabby Gums to your server:")
    await ctx.send(invite)


@client.command(name='ping',
                brief='Shows the current bot latency.',
                description='Shows the current bot latency.')
async def ping_command(ctx: commands.Context):

    bot: GGBot = ctx.bot
    db_start = time.perf_counter()
    await db.get_log_channel(bot.db_pool, ctx.guild.id)  # Get the log to test DB speed
    db_end = time.perf_counter()

    embed = discord.Embed(title="Pinging...", description=" \n ", color=0x00b7fa)
    start = time.perf_counter()
    # Gets the timestamp when the command was used

    msg = await ctx.send(embed=embed)
    # Sends a message to the user in the channel the message with the command was received.
    # Notifies the user that pinging has started
    new_embed = discord.Embed(title="Pong!",
                              description="Round trip messaging time: **{:.2f} ms**. \nAPI latency: **{:.2f} ms**.\nDatabase latency: **{:.2f} ms**".
                             format((time.perf_counter() - start)*1000, client.latency*1000, (db_end - db_start)*1000), color=0x00b7fa)
    await msg.edit(embed=new_embed)


@client.command(name='stats',
                brief='Shows various stats such as CPU, memory usage, disk space usage, and more.',
                description='Shows various stats such as CPU, memory usage, disk space usage, and more.')
async def top_command(ctx: commands.Context):

    def folder_size(path='.'):
        total = 0
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += folder_size(entry.path)
        return total

    bot: GGBot = ctx.bot

    pid = os.getpid()
    py = psutil.Process(pid)
    memory_use = py.memory_info()[0] / 1024 / 1024
    disk_usage = psutil.disk_usage("/")
    disk_space_free = disk_usage.free / 1024 / 1024
    disk_space_used = disk_usage.used / 1024 / 1024
    disk_space_percent_used = disk_usage.percent
    image_cache_du_used = folder_size("./image_cache/") / 1024 / 1024
    num_of_files_in_cache = sum([len(files) for r, d, files in os.walk("./image_cache/")])

    num_of_db_cached_messages = await db.get_number_of_rows_in_messages(bot.db_pool)
    try:
        load_average = os.getloadavg()
    except AttributeError:  # Get load avg is not available on windows
        load_average = [-1, -1, -1]

    embed = discord.Embed(title="CPU and memory usage:",
                          description="CPU: **{}%** \nLoad average: **{:.2f}, {:.2f}, {:.2f}**\nMemory: **{:.2f} MB**"
                                      "\nDisk space: **{:.2f} MB Free**, **{:.2f} MB Used**, **{}% Used**\nDisk space used by image cache: **{:.2f} MB Used** with **{} files** \nCached messages in DB: **{}**\nCached messages in memory: **{}**\n# of guilds: **{}**".
                          format(psutil.cpu_percent(), load_average[0], load_average[1], load_average[2], memory_use,
                                 disk_space_free, disk_space_used, disk_space_percent_used, image_cache_du_used, num_of_files_in_cache, num_of_db_cached_messages, len(client.cached_messages), len(client.guilds)), color=0x00b7fa)

    await ctx.send(embed=embed)


@client.command(name="verify_perm",
                brief="Checks for any possible permission or configuration problems that could interfere with the operations of Gabby Gums",
                description="Checks for any possible permission or configuration problems that could interfere with the operations of Gabby Gums",
                )
async def verify_permissions(ctx: commands.Context, guild_id: Optional[str] = None):
    # TODO: Restrict usage

    bot: GGBot = ctx.bot

    if guild_id is not None:
        guild: discord.Guild = client.get_guild(int(guild_id.strip()))
    else:
        guild: discord.Guild = ctx.guild

    if guild is None:
        await ctx.send("{} is an invalid guild ID".format(guild_id))
        return

    # ToDO: check for send permissions for ctx and log error if unavailable.
    embed = discord.Embed(title="Debug for {}".format(guild.name), color=0x61cd72)

    perms = {'read': [], 'send': [], 'non-crit': [], 'manage_guild': True}
    errors_found = False

    if not guild.me.guild_permissions.manage_guild:
        errors_found = True
        perms['manage_guild'] = False

    for channel in guild.channels:
        channel: discord.TextChannel
        permissions: discord.Permissions = channel.guild.me.permissions_in(channel)

        if channel.type == discord.ChannelType.text:
            if permissions.read_messages is False:
                errors_found = True
                perms['read'].append(f"<#{channel.id}>")

            if permissions.send_messages is False:
                errors_found = True
                perms['send'].append(f"<#{channel.id}>")
                # TODO: Check if this channel is currently set as a logging channel or if anything is set as a log channel.

            if (permissions.view_audit_log is False) or (permissions.embed_links is False) or\
                    (permissions.read_message_history is False) or (permissions.external_emojis is False) or \
                    permissions.attach_files is False or permissions.add_reactions is False:
                errors_found = True
                perms['non-crit'].append(f"<#{channel.id}>")
                # TODO: Actually List out the missing not-critical permissions.

    if len(perms['read']) > 0:
        read_msg = "ERROR!! The following channels do not have the **Read Messages** permission. " \
                   "Gabby Gums will be unable to log any events that happen in these channels:\n"
        read_msg = read_msg + "\n".join(perms['read'])
        embed.add_field(name="Read Messages Permissions Problems", value=f"{read_msg}\n\N{ZERO WIDTH NON-JOINER}", inline=False)

    if len(perms['send']) > 0:
        send_msg = "ERROR!! The following channels do not have the **Send Messages** permission. " \
                   "Gabby Gums will be unable to respond to any commands that are executed in these channels " \
                   "and will be unable to use any of them as a logging channel:\n"
        send_msg = send_msg + "\n".join(perms['send'])
        embed.add_field(name="Send Messages Permissions Problems", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}", inline=False)

    if not perms['manage_guild']:
        embed.add_field(name="Manage Server Permissions Problems",
                        value="Gabby Gums is missing the Manage Server permission. Invite code tracking will not be functional.",
                        inline=True)

    if len(perms['non-crit']) > 0:
        noncrit_msg = "Warning! The following channels are missing a **Non-Critical** permission. " \
                   "Gabby Gums will be continue to work as normal for now, " \
                   "but may be unable to utilize a future feature:\n"

        noncrit_msg = noncrit_msg + "\n".join(perms['non-crit'])
        embed.add_field(name="Non-Critical Permissions Problems", value=f"{noncrit_msg}\n\N{ZERO WIDTH NON-JOINER}", inline=False)

    # List the default log channel
    guild_logging_channel = await get_event_or_guild_logging_channel(bot.db_pool, guild.id)
    if guild_logging_channel is not None:
        embed.add_field(name="Default Log Channel ", value="<#{}>\n\N{ZERO WIDTH NON-JOINER}".format(guild_logging_channel.id), inline=True)
        default_log_channel = f"<#{guild_logging_channel.id}>"
    else:
        embed.add_field(name="Default Log Channel ", value="**NONE**\n\N{ZERO WIDTH NON-JOINER}", inline=True)
        default_log_channel = "**NONE**"

    # List event specific logging configs
    event_config_msg_fragments = []
    event_configs = await db.get_server_log_configs(bot.db_pool, guild.id)
    for event_type in event_configs.available_event_types():
        event = event_configs[event_type]
        if event is None or event.log_channel_id is None:
            event_config_msg_fragments.append(f"__{event_type}:__\nLogging to {default_log_channel}")
        elif not event.enabled:
            event_config_msg_fragments.append(f"__{event_type}:__\nLogging Disabled")
        else:
            event_config_msg_fragments.append(f"__{event_type}:__\nLogging to <#{event.log_channel_id}>")

    event_config_msg = "\n".join(event_config_msg_fragments)
    embed.add_field(name="Event Configurations", value=f"{event_config_msg}\n\N{ZERO WIDTH NON-JOINER}", inline=True)

    # List all users being ignored
    ignored_users_msg_fragments = []
    ignored_users_ids = await db.get_ignored_users(bot.db_pool, guild.id)
    if len(ignored_users_ids) > 0:
        for user_id in ignored_users_ids:
            ignored_users_msg_fragments.append(f"<@!{user_id}>")
        ignored_users_msg = "\n".join(ignored_users_msg_fragments)
        embed.add_field(name="Users Currently Being Ignored ", value=f"{ignored_users_msg}\n\N{ZERO WIDTH NON-JOINER}",
                        inline=True)

    # List all channels being ignored
    channels_msg = ""
    _ignored_channels_ids = await db.get_ignored_channels(bot.db_pool, guild.id)
    if len(_ignored_channels_ids) > 0:
        for channel_id in _ignored_channels_ids:
            ignored_channel = await get_channel_safe(channel_id)
            if ignored_channel is not None:
                channels_msg = channels_msg + "<#{}>\n".format(ignored_channel.id)
            else:
                channels_msg = channels_msg + "Deleted channel w/ ID: {}\n".format(channel_id)
        embed.add_field(name="Channels Currently Being Ignored ", value=f"{channels_msg}\N{ZERO WIDTH NON-JOINER}", inline=True)
    else:
        embed.add_field(name="Channels Currently Being Ignored ", value="**NONE**\n\N{ZERO WIDTH NON-JOINER}", inline=True)

    # List all categories being ignored
    _ignored_categories = await db.get_ignored_categories(bot.db_pool, guild.id)
    if len(_ignored_categories) > 0:
        categories_id_msg_fragments = [f"<#{category_id}>  *(ID: {category_id})*" for category_id in _ignored_categories]
        categories_msg = "\n".join(categories_id_msg_fragments)
        embed.add_field(name="All channels under the following categories are currently being ignored ", value=f"{categories_msg}\n\N{ZERO WIDTH NON-JOINER}", inline=True)
    else:
        embed.add_field(name="All channels under the following categories are currently being ignored ", value="**NONE**\n\N{ZERO WIDTH NON-JOINER}", inline=True)

    # Set the appropriate embed description
    if errors_found:
        embed.description = "Uh oh! Problems were found!"
    else:
        embed.description = "No problems found!"

    await ctx.send(embed=embed)


# ----- Debugging Channel Commands ----- #
@commands.is_owner()
@client.command(name="dump")
async def dump(ctx: commands.Context, table: str):
    bot: GGBot = ctx.bot
    await ctx.send("DB Dump for {}".format(table))
    table_msg = "```python\n"
    rows = await db.fetch_full_table(bot.db_pool, table)

    for row in rows:
        table_msg = table_msg + str(row) + "\n"
    table_msg = table_msg + "```"
    await ctx.send(table_msg[len(table_msg)-2000:len(table_msg)] if len(table_msg) > 2000 else table_msg)


@commands.is_owner()
@client.command(name="messages")
async def past_messages(ctx: commands.Context, hours: int, max: int = 15):
    # This command is limited only to servers that we are Admin/Owner of for privacy reasons.
    bot: GGBot = ctx.bot
    rows = await db.get_cached_messages_older_than(bot.db_pool, hours)
    rows = rows[len(rows)-max:len(rows)] if len(rows) > max else rows
    await ctx.send("Dumping the last {} records over the last {} hours".format(len(rows), hours))
    for row in rows:
        log_msg = f"mid: {row['message_id']}, sid: {row['server_id']}, uid: {row['user_id']}, " \
                  f"ts: {row['ts'].strftime('%b %d, %Y, %I:%M:%S %p UTC')} webhookun: {row['webhook_author_name']}, " \
                  f"system_pkid: {row['system_pkid']}, member_pkid: {row['member_pkid']}, " \
                  f"PK Account: <@{row['pk_system_account_id']}> message: \n**{row['content']}**"

        logging.info(log_msg)
        await utils.send_long_msg(ctx, log_msg)
        await asyncio.sleep(1)


@commands.is_owner()
@client.command(name="test")
async def test_cmd(ctx: commands.Context):
    pass


# ---- Command Error Handling ----- #
@client.event
async def on_command_error(ctx, error):
    if type(error) == discord.ext.commands.NoPrivateMessage:
        await ctx.send("⚠ This command can not be used in DMs!!!")
        return
    elif type(error) == discord.ext.commands.CommandNotFound:
        await ctx.send("⚠ Invalid Command!!!")
        return
    elif type(error) == discord.ext.commands.MissingPermissions:
        await ctx.send("⚠ You need the **Manage Messages** permission to use this command".format(error.missing_perms))
        return
    elif type(error) == discord.ext.commands.MissingRequiredArgument:
        await ctx.send("⚠ {}".format(error))
    elif type(error) == discord.ext.commands.BadArgument:
        await ctx.send("⚠ {}".format(error))
    else:
        await ctx.send("⚠ {}".format(error))
        raise error


# ----- Discord Events ----- #
@client.event
async def on_message(message: discord.Message):

    if message.author.id != client.user.id:  # Don't log our own messages.

        message_contents = message.content if message.content != '' else None

        # TODO: Use Path Objects instead of strings for paths.
        attachments = None
        if len(message.attachments) > 0 and message.guild.id in config['restricted_features']:
            attachments = []
            for attachment in message.attachments:
                # logging.info("ID: {}, Filename: {}, Height: {}, width: {}, Size: {}, Proxy URL: {}, URL: {}"
                #              .format(attachment.id, attachment.filename, attachment.height, attachment.width, attachment.size, attachment.proxy_url, attachment.url))

                attachment_filename = "{}_{}".format(attachment.id, attachment.filename)
                logging.info("Saving Attachment from {}".format(message.guild.id))
                try:
                    await attachment.save("./image_cache/{}/{}".format(message.guild.id, attachment_filename))
                except FileNotFoundError as e:
                    # If the directory(s) do not exist, create them and then re-save
                    Path("./image_cache/{}".format(message.guild.id)).mkdir(parents=True, exist_ok=True)
                    await attachment.save("./image_cache/{}/{}".format(message.guild.id, attachment_filename))
                attachments.append(attachment_filename)

        if message_contents is not None or attachments is not None:
            webhook_author_name = message.author.display_name if message.webhook_id is not None else None
            await db.cache_message(client.db_pool, message.guild.id, message.id, message.author.id, message_content=message_contents,
                                   attachments=attachments, webhook_author_name=webhook_author_name)

    await client.process_commands(message)


@client.event
async def on_error(event_name, *args):
    logging.exception("Exception from event {}".format(event_name))

    if 'error_log_channel' not in config:
        return
    error_log_channel = client.get_channel(config['error_log_channel'])

    embed = None
    # Determine if we can get more info, otherwise post without embed
    if args and type(args[0]) == discord.Message:
        message: discord.Message = args[0]
        embeds.exception_w_message(message)
    elif args and type(args[0]) == discord.RawMessageUpdateEvent:
        logging.error("After Content:{}.".format(args[0].data['content']))
        if args[0].cached_message is not None:
            logging.error("Before Content:{}.".format(args[0].cached_message.content))
    # Todo: Add more

    traceback_message = "```python\n{}```".format(traceback.format_exc())
    traceback_message = (traceback_message[:1993] + ' ...```') if len(traceback_message) > 2000 else traceback_message
    await error_log_channel.send(content=traceback_message, embed=embed)


@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):
    event_type = "message_delete"

    # Exit function to ensure message is removed from the cache.
    async def cleanup_message_cache():
        if db_cached_message is not None:
            await db.delete_cached_message(client.db_pool, payload.guild_id, db_cached_message.message_id)

    if payload.guild_id is None:
        return  # We are in a DM, Don't log the message

    # Get the cached msg from the DB (if possible). Will be None if msg does not exist in DB
    db_cached_message = await db.get_cached_message(client.db_pool, payload.guild_id, payload.message_id)

    # Check if the channel we are in is ignored. If it is, bail
    if await is_channel_ignored(client.db_pool, payload.guild_id, payload.channel_id):
        await cleanup_message_cache()
        return

    # Check if the category we are in is ignored. If it is, bail
    channel: discord.TextChannel = await get_channel_safe(payload.channel_id)
    if await is_category_ignored(client.db_pool, payload.guild_id, channel.category):
        await cleanup_message_cache()
        return

    channel_id = payload.channel_id

    # Check to see if we got results from the memory or DB cache.
    if payload.cached_message is not None or db_cached_message is not None:
        cache_exists = True
        # Pull the message content and author from the Memory/DB Cache. Favor the Memory cache over the DB Cache.
        msg = payload.cached_message.content if payload.cached_message is not None else db_cached_message.content
        author = payload.cached_message.author if payload.cached_message is not None else client.get_user(db_cached_message.user_id)

        # Check if the message is from Gabby Gums or an ignored user. If it is, bail.
        if author is not None and (client.user.id == author.id or await is_user_ignored(client.db_pool, payload.guild_id, author.id)):
            await cleanup_message_cache()
            return
    else:
        # Message was not in either cache. Set msg and author to None.
        cache_exists = False
        msg = None
        author = None

    # Check with PK API Last to reduce PK server load.
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.pluralkit.me/msg/{}'.format(payload.message_id)) as r:
                if r.status == 200:  # We received a valid response from the PK API. The message is probably a pre-proxied message.
                    # TODO: Remove logging once bugs are worked out.
                    logging.info(f"Message {payload.message_id} is still on the PK api. updating caches and aborting logging.")
                    # Convert the JSON response to a dict, Cache the details of the proxied message, and then bail.
                    pk_response = await r.json()
                    if verify_message_is_preproxy_message(payload.message_id, pk_response):
                        # We have confirmed that the message is a pre-proxied message.
                        await cache_pk_message_details(payload.guild_id, pk_response)
                        await cleanup_message_cache()
                        return  # Message was a pre-proxied message deleted by PluralKit. Return instead of logging message.

    except aiohttp.ClientError as e:
        logging.warning(
            "Could not connect to PK server with out errors. Assuming message should be logged.\n{}".format(e))

    # Get the servers logging channel.
    log_channel = await get_event_or_guild_logging_channel(client.db_pool, payload.guild_id, event_type)
    if log_channel is None:
        # Silently fail if no log channel is configured.
        await cleanup_message_cache()
        return

    # Handle any attachments
    attachments = []
    if db_cached_message is not None and db_cached_message.attachments is not None:
        for attachment_name in db_cached_message.attachments:
            spoil = True if "SPOILER" in attachment_name else False
            if spoil is False:
                # channel = await get_channel_safe(payload.channel_id)
                if channel.is_nsfw():
                    spoil = True  # Make ANY image from an NSFW board spoiled to keep log channels SFW.
            try:
                # max file sizee 8000000
                new_attach = discord.File("./image_cache/{}/{}".format(db_cached_message.server_id, attachment_name),
                                          filename=attachment_name, spoiler=spoil)
                attachments.append(new_attach)
            except FileNotFoundError:
                pass  # The file may have been too old and has since been deleted.

    if msg == "":
        msg = "None"

    if db_cached_message is not None and db_cached_message.pk_system_account_id is not None:
        pk_system_owner = client.get_user(db_cached_message.pk_system_account_id)
    else:
        pk_system_owner = None

    embed = embeds.deleted_message(message_content=msg, author=author, channel_id=channel_id,
                                   message_id=payload.message_id, webhook_info=db_cached_message,
                                   pk_system_owner=pk_system_owner, cached=cache_exists)

    await log_channel.send(embed=embed)
    if len(attachments) > 0:
        await log_channel.send(content="Deleted Attachments:", files=attachments)

    await cleanup_message_cache()


def verify_message_is_preproxy_message(message_id: int, pk_response: Dict) -> bool:
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



async def cache_pk_message_details(guild_id: int, pk_response: Dict):

    error_msg = []
    error_header = '[cache_pk_message_details]: '
    if 'id' in pk_response:  # Message ID (Discord Snowflake) of the proxied message
        message_id = int(pk_response['id'])
    else:
        # If we can not pull the message ID there is no point in continuing.
        msg = "'WARNING! 'id' not in PK msg API Data. Aborting JSON Decode!"
        error_msg.append(msg)
        logging.warning(msg)
        await utils.send_error_msg_to_log(client, error_msg, header=f"{error_header}!ERROR!")
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
    logging.info(f"Updating msg: {message_id} with Sender ID: {sender_discord_id}, System ID: {system_pk_id}, Member ID: {member_pk_id}")
    await db.update_cached_message_pk_details(client.db_pool, guild_id, message_id, system_pk_id, member_pk_id, sender_discord_id)

    if len(error_msg) > 0:
        await utils.send_error_msg_to_log(client, error_msg, header=error_header)


@client.event
async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):
    event_type = "message_edit"

    if 'content' in payload.data and payload.data['content'] != '':  # Makes sure there is a message content
        if "guild_id" not in payload.data:
            return  # We are in a DM, Don't log the message

        db_cached_message = await db.get_cached_message(client.db_pool, payload.data['guild_id'], payload.message_id)

        after_msg = payload.data['content']
        guild_id = int(payload.data["guild_id"])
        message_id = payload.message_id

        if payload.cached_message is not None:
            before_msg = payload.cached_message.content
            author = payload.cached_message.author
            author_id = author.id
            channel_id = payload.cached_message.channel.id
        else:
            before_msg = db_cached_message.content if db_cached_message is not None else None
            author_id = payload.data['author']['id']
            channel_id = payload.data["channel_id"]
            author = None

        if client.user.id == author_id:
            # This is a Gabby Gums message. Do not log the event.
            return

        if after_msg == before_msg:
            # The message content has not changed. This is a pin/unpin, embed edit (which would be from a bot or discord)
            return

        if await is_user_ignored(client.db_pool, guild_id, author_id):
            return

        if await is_channel_ignored(client.db_pool, guild_id, channel_id):
            return

        channel: discord.TextChannel = await get_channel_safe(channel_id)
        if await is_category_ignored(client.db_pool, guild_id, channel.category):
            return

        if author is None:
            await client.wait_until_ready()
            # TODO: Consider removing to prevent potential API call
            author = client.get_user(author_id)
            if author is None:
                print("get_user failed")
                author = await client.fetch_user(author_id)

        embed = embeds.edited_message(author_id, author.name, author.discriminator, channel_id, before_msg, after_msg, message_id, guild_id)

        log_channel = await get_event_or_guild_logging_channel(client.db_pool, guild_id, event_type)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            return

        # try:
        await log_channel.send(embed=embed)

        if db_cached_message is not None:
            await db.update_cached_message(client.db_pool, payload.data['guild_id'], payload.message_id, after_msg)


async def get_stored_invites(guild_id: int) -> db.StoredInvites:
    stored_invites = await db.get_invites(client.db_pool, guild_id)
    return stored_invites


async def update_invite_cache(guild: discord.Guild, invites: Optional[List[discord.Invite]] = None,
                              stored_invites: Optional[db.StoredInvites] = None):
    try:
        if not guild.me.guild_permissions.manage_guild:
            return

        if invites is None:
            invites: List[discord.Invite] = await guild.invites()

        for invite in invites:
            await db.store_invite(client.db_pool, guild.id, invite.id, invite.uses)

        if stored_invites is None:
            stored_invites = await get_stored_invites(guild.id)

        await remove_invalid_invites(guild.id, invites, stored_invites)
    except discord.Forbidden as e:
        logging.exception("update_invite_cache error: {}".format(e))

        if 'error_log_channel' not in config:
            return
        error_log_channel = client.get_channel(config['error_log_channel'])
        await error_log_channel.send(e)


async def remove_invalid_invites(guild_id: int, current_invites: List[discord.Invite], stored_invites: Optional[db.StoredInvites]):

    def search_for_invite(_current_invites: List[discord.Invite], invite_id):
        for invite in _current_invites:
            if invite.id == invite_id:
                return invite
        return None

    for stored_invite in stored_invites.invites:
        current_invite = search_for_invite(current_invites, stored_invite.invite_id)
        if current_invite is None:
            await db.remove_invite(client.db_pool, guild_id, stored_invite.invite_id)


async def find_used_invite(member: discord.Member) -> Optional[db.StoredInvite]:

    stored_invites: db.StoredInvites = await get_stored_invites(member.guild.id)
    current_invites: List[discord.Invite] = await member.guild.invites()

    if member.bot:
        # The member is a bot. An oauth invite was used.
        await update_invite_cache(member.guild, invites=current_invites)
        return None

    new_invites: List[discord.Invite] = []  # This is where we will store newly created invites.
    # invite_used: Optional[db.StoredInvite] = None
    for current_invite in current_invites:
        stored_invite = stored_invites.find_invite(current_invite.id)
        if stored_invite is None:
            new_invites.append(current_invite)  # This is a new Invite. store it so we have it in case we need it
        else:
            if current_invite.uses > stored_invite.uses:
                # We have a matched invite!
                stored_invite.uses = current_invite.uses  # Correct the count of the stored invite.
                stored_invite.actual_invite = current_invite
                await update_invite_cache(member.guild, invites=current_invites)
                return stored_invite  # Todo: FIX! This works, unless we somehow missed the last user join.
            else:
                pass  # not the used invite. look at the next invite.
    # We scanned through all the current invites and was unable to find a match from the cache. Look through new invites

    for new_invite in new_invites:
        if new_invite.uses > 0:
            # Todo: FIX! This works, unless we somehow missed the last user join.
            invite_used = db.StoredInvite(server_id=new_invite.guild.id, invite_id=new_invite.id,
                                          uses=new_invite.uses, invite_name="New Invite!", actual_invite=new_invite)
            await update_invite_cache(member.guild, invites=current_invites)
            return invite_used

    # Somehow we STILL haven't found the invite that was used... I don't think we should ever get here, unless I forgot something...
    # We should never get here, so log it very verbosly in case we do so I can avoid it in the future.
    current_invite_debug_msg = "invites=["
    for invite in current_invites:
        debug_msg = "Invite(code={code}, uses={uses}, max_uses={max_uses}, max_age={max_age}, revoked={revoked}," \
              " created_at={created_at}, inviter={inviter}, guild={guild})".format(code=invite.code, uses=invite.uses,
                                                                                   max_uses=invite.max_uses,
                                                                                   max_age=invite.max_age,
                                                                                   revoked=invite.revoked,
                                                                                   created_at=invite.created_at,
                                                                                   inviter=invite.inviter,
                                                                                   guild=invite.guild)
        current_invite_debug_msg = current_invite_debug_msg + debug_msg
    current_invite_debug_msg = current_invite_debug_msg + "]"

    log_msg = "UNABLE TO DETERMINE INVITE USED.\n Stored invites: {}, Current invites: {} \n" \
              "Server: {}, Member: {}".format(stored_invites, current_invite_debug_msg, repr(member.guild), repr(member))
    logging.info(log_msg)

    if 'error_log_channel' in config:
        error_log_channel = client.get_channel(config['error_log_channel'])
        await error_log_channel.send("UNABLE TO DETERMINE INVITE USED.")
        await utils.send_long_msg(error_log_channel, "Stored invites: {}".format(stored_invites), code_block=True)
        await utils.send_long_msg(error_log_channel, "Current invites: {}".format(current_invite_debug_msg), code_block=True)
        await utils.send_long_msg(error_log_channel, "Server: {}".format(repr(member.guild)), code_block=True)
        await utils.send_long_msg(error_log_channel, "Member who joined: {}".format(repr(member)), code_block=True)

    await update_invite_cache(member.guild, invites=current_invites)
    return None


@client.event
async def on_member_join(member: discord.Member):
    event_type = "member_join"

    if member.guild.me.guild_permissions.manage_guild:
        invite_used = await find_used_invite(member)
        if invite_used is not None:
            logging.info(
                "New user joined with link {} that has {} uses.".format(invite_used.invite_id, invite_used.uses))
        embed = embeds.member_join(member, invite_used)
    else:
        embed = embeds.member_join(member, None, manage_guild=False)

    log_channel = await get_event_or_guild_logging_channel(client.db_pool, member.guild.id, event_type)
    if log_channel is None:
        # Silently fail if no log channel is configured.
        return

    await log_channel.send(embed=embed)


@client.event
async def on_member_remove(member: discord.Member):
    event_type = "member_leave"

    log_channel = await get_event_or_guild_logging_channel(client.db_pool, member.guild.id, event_type)
    if log_channel is None:
        # Silently fail if no log channel is configured.
        return
    # We have a log channel. Start pulling audit logs and doing stuff

    guild: discord.Guild = member.guild
    try:
        audit_log_entries = await utils.get_audit_logs(guild, discord.AuditLogAction.kick, member, timedelta(seconds=30))
        if len(audit_log_entries) > 0:
            # Assume the latest entry is the correct entry.
            # Todo: Maybe Look at the time data and reject if it's too old? Kinda redundent though since we already filter them all out...
            audit_log = audit_log_entries[0]
            # reason = f" because: {audit_log.reason}" if audit_log.reason else ". No Reason was given"
            logging.info(f"Got Audit log entries")
            # return
        else:
            logging.info(f"No audit log entries present")
            audit_log = None

    except utils.MissingAuditLogPermissions:
        # log.info(f"{member.name} left.")
        # log.info(f"Gabby Gums needs the View Audit Log permission to display who kicked the member.")
        logging.info("Need more perms")
        audit_log = None

    if audit_log is not None:
        embed = embeds.member_kick(member, audit_log)
    else:
        embed = embeds.member_leave(member)

    await log_channel.send(embed=embed)


@client.event
async def on_member_ban(guild: discord.Guild, user: Union[discord.User, discord.Member]):
    """ User can be either a User (if they were hackbanned) Or a Member () If they were in the guild when banned"""
    await log_member_ban_or_unban(guild, user, "ban")


@client.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    await log_member_ban_or_unban(guild, user, "unban")


async def log_member_ban_or_unban(guild: discord.Guild, user: Union[discord.User, discord.Member], ban_or_unban: str):
    """ If ban, use "ban". if unban, use "unban" """
    logging.info(f"User {ban_or_unban} Guild: {guild}, User: {user}")
    await asyncio.sleep(0.5)
    if ban_or_unban.lower() == "ban":
        audit_action = discord.AuditLogAction.ban
        embed_fn = embeds.member_ban
        event_type = "member_ban"
    elif ban_or_unban.lower() == "unban":
        audit_action = discord.AuditLogAction.unban
        embed_fn = embeds.member_unban
        event_type = "member_unban"
    else:
        raise ValueError("ban_or_unban must be 'ban' or 'unban' ")

    log_channel = await get_event_or_guild_logging_channel(client.db_pool, guild.id, event_type)
    if log_channel is None:
        # Silently fail if no log channel is configured.
        return
    # We have a log channel. Start pulling audit logs and doing stuff

    try:
        audit_log_entries = await utils.get_audit_logs(guild, audit_action, user, timedelta(seconds=30))
        if len(audit_log_entries) > 0:
            # Assume the latest entry is the correct entry.
            # Todo: Maybe Look at the time data and reject if it's too old? Kinda redundent though since we already filter them all out...
            audit_log = audit_log_entries[0]
            logging.info("Got logs")
        else:
            audit_log = None
            logging.info("Got NO logs")

    except utils.MissingAuditLogPermissions:
        audit_log = None
        logging.info("need perms")
        # log.info(f"Gabby Gums needs the View Audit Log permission to display who {action_verbage} members.")

    embed = embed_fn(user, audit_log)
    await log_channel.send(embed=embed)


# For debugging purposes only.
@commands.is_owner()
@client.command(name="pfp")
async def pfp_test_cmd(ctx: commands.Context, after: discord.Member):

    event_type_avatar = "user_avatar_update"
    before: discord.Member = ctx.author
    # noinspection PyTypeChecker
    await avatar_changed_update(before, after)


# For debugging purposes only.
@commands.is_owner()
@client.command(name="pfp-all")
async def pfp_all_test_cmd(ctx: commands.Context, maximum_number: int = 10):
    from random import SystemRandom as sRandom
    random = sRandom()
    members: List[discord.Member] = list(client.get_all_members())
    await ctx.send(f"Generating {maximum_number} avatar changed embeds out of {len(members)} total members.")
    some_members = random.choices(members, k=maximum_number)
    for member in some_members:
        # noinspection PyTypeChecker
        await avatar_changed_update(member, member)
    await ctx.send(f"Done sending test embeds.")


@client.event
async def on_user_update(before: discord.User, after: discord.User):
    # username, Discriminator

    if before.avatar != after.avatar:
        # Get a list of guilds the user is currently in.
        await avatar_changed_update(before, after)

    if before.name != after.name or before.discriminator != after.discriminator:
        await username_changed_update(before, after)


async def username_changed_update(before: discord.User, after: discord.User):
    event_type_name = "username_change"
    # Username and/or discriminator changed
    embed = embeds.user_name_update(before, after)

    guilds = [guild for guild in client.guilds if before in guild.members]
    if len(guilds) > 0:
        for guild in guilds:
            log_channel = await get_event_or_guild_logging_channel(client.db_pool, guild.id, event_type_name)
            if log_channel is not None:
                await log_channel.send(embed=embed)


async def avatar_changed_update(before: discord.User, after: discord.User):
    """Sends the appropriate logs on a User Avatar Changed Event"""
    event_type_avatar = "member_avatar_change"

    guilds = [guild for guild in client.guilds if before in guild.members]
    if len(guilds) > 0:
        # get the pfp changed embed image and convert it to a discord.File
        avatar_changed_file_name = "avatarChanged.png"

        avatar_info = {"before name": before.name, "before id": before.id, "before pfp": before.avatar_url_as(format="png"),
                       "after name": after.name, "after id": after.id, "after pfp": after.avatar_url_as(format="png")
                       }  # For Debugging

        with await get_avatar_changed_image(client, before, after, avatar_info) as avatar_changed_bytes:
            # create the embed
            embed = embeds.user_avatar_update(before, after, avatar_changed_file_name)

            # loop through all the guilds the member is in and send the embed and image
            for guild in guilds:
                log_channel = await get_event_or_guild_logging_channel(client.db_pool, guild.id, event_type_avatar)
                if log_channel is not None:
                    # The File Object needs to be recreated for every post, and the buffer needs to be rewound to the beginning
                    # TODO: Handle case where avatar_changed_bytes could be None.
                    avatar_changed_bytes.seek(0)
                    avatar_changed_img = discord.File(filename=avatar_changed_file_name, fp=avatar_changed_bytes)
                    # Send the embed and file
                    await log_channel.send(file=avatar_changed_img, embed=embed)


@client.event
async def on_guild_join(guild: discord.Guild):
    # Todo: Move DB creation to a command.
    #  Having it here is fragile as a user could add the bot and on_guild_join may not ever fire if the bot is down at the time.
    # create an entry for the server in the database
    await db.add_server(client.db_pool, guild.id, guild.name)

    await update_invite_cache(guild)

    # Log it for support and DB debugging purposes
    log_msg = "Gabby Gums joined **{} ({})**, owned by:** {} - {}#{} ({})**".format(guild.name, guild.id, guild.owner.display_name, guild.owner.name, guild.owner.discriminator, guild.owner.id)
    logging.info(log_msg)

    if 'error_log_channel' not in config:
        return
    error_log_channel = client.get_channel(config['error_log_channel'])
    await error_log_channel.send(log_msg)


@client.event
async def on_guild_remove(guild: discord.Guild):
    # Todo: Find a less fragile way to do this, or a back up. Maybe a DB clean up that runs every day/week?
    log_msg = "Gabby Gums has left {} ({}). Removing guild from database!".format(guild.name, guild.id)
    logging.warning(log_msg)

    if 'error_log_channel' not in config:
        await db.remove_server(client.db_pool, guild.id)
        return
    error_log_channel = client.get_channel(config['error_log_channel'])
    await error_log_channel.send(log_msg)
    await db.remove_server(client.db_pool, guild.id)


@client.event
async def on_guild_unavailable(guild: discord.Guild):
    log_msg = "{} ({}) is unavailable.".format(guild.name, guild.id)
    logging.warning(log_msg)

    if 'error_log_channel' not in config:
        return

    error_log_channel = client.get_channel(config['error_log_channel'])
    await error_log_channel.send(log_msg)


if __name__ == '__main__':

    with open('config.json') as json_data_file:
        config = json.load(json_data_file)

    db_pool: asyncpg.pool.Pool = asyncio.get_event_loop().run_until_complete(db.create_db_pool(config['db_uri']))
    asyncio.get_event_loop().run_until_complete(db.create_tables(db_pool))

    client.config = config
    client.db_pool = db_pool
    client.command_prefix = config['bot_prefix']

    client.load_cogs()
    client.run(config['token'])

    logging.info("cleaning Up and shutting down")
