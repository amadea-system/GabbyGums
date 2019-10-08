'''

'''


import discord
from discord.ext import commands
from discord.utils import oauth_url
import aiohttp
import time
from typing import Optional, List
import json
import os
import logging
import traceback
import embeds
import psutil
import asyncpg
import asyncio

import db


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

client = commands.Bot(command_prefix="g!",
                      max_messages=100000,
                      # description="A simple logging bot that ignores PluralKit proxies.\n",
                      owner_id=389590659335716867,
                      case_insensitive=True)
client.remove_command("help")  # Remove the built in help command so we can make the about section look nicer.


async def is_channel_ignored(pool: asyncpg.pool.Pool, guild_id: int, channel_id: int) -> bool:
    _ignored_channels = await db.get_ignored_channels(pool, guild_id)
    if channel_id in _ignored_channels:
        return True  # TODO: Optimise this
    return False


async def is_user_ignored(pool, guild_id: int, user_id: int) -> bool:
    _ignored_users = await db.get_ignored_users(pool, guild_id)
    if user_id in _ignored_users:
        return True# This is a message from a user the guild does not wish to log. Do not log the event.
    return False


async def get_guild_logging_channel(guild_id: int) -> Optional[discord.TextChannel]:

    _log_channel_id = await db.get_log_channel(pool, guild_id)
    if _log_channel_id is not None:
        log_channel = client.get_channel(_log_channel_id)
        if log_channel is None:
            print("get_log_ch failed. WHY?????")
            log_channel = await client.fetch_channel(_log_channel_id)
        return log_channel
    return None


async def get_channel_safe(channel_id: int) -> discord.TextChannel:
    channel = client.get_channel(channel_id)
    if channel is None:
        print("get ch failed. WHY?????")
        channel = await client.fetch_channel(channel_id)
    return channel


@client.event
async def on_ready():
    logging.info('Connected!')
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
async def logging_channel(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(logging_channel)


@logging_channel.command(name="set", brief="Sets which channel the bot will log to.",
                         description="Sets which channel the bot will log to.")
async def set_logging_channel(ctx, channel: discord.TextChannel):
    await db.update_log_channel(pool, ctx.guild.id, channel.id)
    await ctx.send("Logging channel set to <#{}>".format(channel.id))


@logging_channel.command(name="unset", brief="Unsets the log channel", description="Unsets the log channel")
async def unset_logging_channel(ctx):
    await db.update_log_channel(pool, ctx.guild.id, log_channel_id=None)
    await ctx.send("Logging channel has been cleared. "
                   "Gabby Gums will no longer be able to log events unless a new logging channel is set")


@logging_channel.command(name="show", brief="Shows what channel is currently configured for logging",
                         description="Shows what channel is currently configured for logging")
async def show_logging_channel(ctx):
    _log_channel = await db.get_log_channel(pool, ctx.guild.id)
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
async def ignore_user(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(ignore_user)


@ignore_user.command(name="list", brief="Lists which users are currently ignored.")
async def _list(ctx):
    await ctx.send("The following users are being ignored by Gabby Gums:")
    # TODO: Utilize db.get_ignored_users
    _ignored_users = await db.get_ignored_users(pool, ctx.guild.id)
    for member_id in _ignored_users:
        await ctx.send("<@{}>".format(member_id))


@ignore_user.command(name="add", brief="Add a new member to be ignored")
async def add(ctx, member: discord.Member):
    await db.add_ignored_user(pool, ctx.guild.id, member.id)
    await ctx.send("<@{}> - {}#{} has been ignored.".format(member.id, member.name, member.discriminator))


@ignore_user.command(name="remove", brief="Stop ignoring a member")
async def remove(ctx, member: discord.Member):
    await db.remove_ignored_user(pool, ctx.guild.id, member.id)
    await ctx.send("<@{}> - {}#{} is no longer being ignored.".format(member.id, member.name, member.discriminator))


# ----- Ignore Channel Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="ignore_channel", brief="Sets which channels will be ignored by Gabby Gums",
              description="Sets which channels will be ignored by Gabby Gums",
              usage='<command> [channel]')
async def ignore_channel(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send_help(ignore_channel)


@ignore_channel.command(name="list", brief="Lists which channels are currently ignored.")
async def _list(ctx):
    _ignored_channels = await db.get_ignored_channels(pool, ctx.guild.id)
    if len(_ignored_channels) > 0:
        await ctx.send("The following channels are being ignored by Gabby Gums:")
        for channel_id in _ignored_channels:
            await ctx.send("<#{}>".format(channel_id))
    else:
        await ctx.send("No channels are being ignored by Gabby Gums.")


@ignore_channel.command(name="add", brief="Add a new channel to be ignored")
async def add(ctx, channel: discord.TextChannel):
    await db.add_ignored_channel(pool, ctx.guild.id, channel.id)
    await ctx.send("<#{}> has been ignored.".format(channel.id))


@ignore_channel.command(name="remove", brief="Stop ignoring a channel")
async def remove(ctx, channel: discord.TextChannel):
    await db.remove_ignored_channel(pool, ctx.guild.id, channel.id)
    await ctx.send("<#{}> is no longer being ignored.".format(channel.id))


# ----- Data management commands ----- #


@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="reset",
              brief="**Completely resets** all configuration and stored data for your server. **Caution, this can not be undone!**")
async def reset_server_info(ctx):
    # TODO: Add warning and confirmation
    await db.remove_server(pool, ctx.guild.id)
    await db.add_server(pool, ctx.guild.id, ctx.guild.name)
    await ctx.send("**ALL Settings have been reset!**")


# ----- Invite Commands ----- #
@commands.has_permissions(manage_messages=True)
@commands.guild_only()
@client.group(name="invites",
              brief="Allows for naming invites for easier identification and listing details about them.",
              description="Allows for naming invites for easier identification and listing details about them.",
              usage='<command> [Invite ID]')
async def invite_manage(ctx):
    if not ctx.guild.me.guild_permissions.manage_guild:
        await ctx.send("⚠ Gabby gums needs the **Manage Server** permission for invite tracking.")
        return
    else:
        if ctx.invoked_subcommand is None:
            await ctx.send_help(invite_manage)


@invite_manage.command(name="list", brief="Lists the invites in the server and if they have a defined name.")
async def _list_invites(ctx):
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
async def _name_invite(ctx, invite_id: discord.Invite, nickname: str = None):
    if ctx.guild.me.guild_permissions.manage_guild:
        await update_invite_cache(ctx.guild)  # refresh the invite cache.
        await db.update_invite_name(pool, ctx.guild.id, invite_id.id, invite_name=nickname)
        await ctx.send("{} has been given the nickname: {}".format(invite_id.id, nickname))


@invite_manage.command(name="unname", brief="Removes the name from an invite.")
async def _unname_invite(ctx, invite_id: discord.Invite):
    if ctx.guild.me.guild_permissions.manage_guild:
        await update_invite_cache(ctx.guild)  # refresh the invite cache.
        await db.update_invite_name(pool, ctx.guild.id, invite_id.id)
        await ctx.send("{} no longer has a nickname.".format(invite_id.id))


# ----- Misc Commands ----- #
@client.command(name='bot_invite',
                brief='Get an invite for Gabby Gums.',
                description='get an invite for Gabby Gums.')
async def invite_link_command(ctx):
    # Todo: Calculate permissions instead of hardcoding and use discord.utils.oauth_url
    invite = "https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions={}".format(client.user.id, 380096)
    await ctx.send("Here's a link to invite Gabby Gums to your server:")
    await ctx.send(invite)


@client.command(name='ping',
                brief='Shows the current bot latency.',
                description='Shows the current bot latency.')
async def ping_command(ctx):

    db_start = time.perf_counter()
    await db.get_log_channel(pool, ctx.guild.id)  # Get the log to test DB speed
    db_end = time.perf_counter()

    embed = discord.Embed(title="Pinging...", description=" \n ", color=0x00b7fa)
    start = time.perf_counter()
    # Gets the timestamp when the command was used

    msg = await ctx.send(embed=embed)
    # Sends a message to the user in the channel the message with the command was received.
    # Notifies the user that pinging has started
    new_embed = discord.Embed(title="Pong!",
                              description="Round trip messaging time: **{:.2f} ms**. \n API latency: **{:.2f} ms**.\n Database latency: **{:.2f} ms**".
                             format((time.perf_counter() - start)*1000, client.latency*1000, (db_end - db_start)*1000), color=0x00b7fa)
    await msg.edit(embed=new_embed)


@client.command(name='top',
                brief='Shows CPU and memory usage.',
                description='Shows CPU and memory usage.')
async def top_command(ctx):

    pid = os.getpid()
    py = psutil.Process(pid)
    memory_use = py.memory_info()[0] / 1024 / 1024

    try:
        load_average = os.getloadavg()
    except AttributeError:  # Get load avg is not available on windows
        load_average = [-1, -1, -1]

    embed = discord.Embed(title="CPU and memory usage:",
                          description="CPU: **{}%** \nLoad average: **{:.2f}, {:.2f}, {:.2f}**\n Memory: **{:.2f} MB**"
                                      "\n Cached messages: **{}**\n Guilds in: **{}**".
                          format(psutil.cpu_percent(), load_average[0], load_average[1], load_average[2],
                                 memory_use, len(client.cached_messages), len(client.guilds)), color=0x00b7fa)

    await ctx.send(embed=embed)


@client.command(name="verify_perm",
                brief="Checks for any possible permission or configuration problems that could interfere with the operations of Gabby Gums",
                description="Checks for any possible permission or configuration problems that could interfere with the operations of Gabby Gums",
                )
async def verify_permissions(ctx, guild_id: Optional[str] = None):
    # TODO: Restrict usage
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
                perms['read'].append(channel.name)

            if permissions.send_messages is False:
                errors_found = True
                perms['send'].append(channel.name)
                #TODO: Check if this channel is currently set as a logging channel or if anything is set as a log channel.

            if (permissions.view_audit_log is False) or (permissions.embed_links is False) or\
                    (permissions.read_message_history is False) or (permissions.external_emojis is False) or \
                    permissions.attach_files is False or permissions.add_reactions is False:
                errors_found = True
                perms['non-crit'].append(channel.name)
                #TODO: Actually List out the missing not-critical permisions.

    if len(perms['read']) > 0:
        read_msg = "ERROR!! The following channels do not have the **Read Messages** permission. " \
                   "Gabby Gums will be unable to log any events that happen in these channels:\n\n"
        read_msg = read_msg + "\n".join(perms['read'])
        embed.add_field(name="Read Messages Permissions Problems", value=read_msg, inline=True)

    if len(perms['send']) > 0:
        send_msg = "ERROR!! The following channels do not have the **Send Messages** permission. " \
                   "Gabby Gums will be unable to respond to any commands that are executed in these channels " \
                   "and will be unable to use any of them as a logging channel:\n\n"
        send_msg = send_msg + "\n".join(perms['send'])
        embed.add_field(name="Send Messages Permissions Problems", value=send_msg, inline=True)

    if not perms['manage_guild']:
        embed.add_field(name="Manage Server Permissions Problems",
                        value="Gabby Gums is missing the Manage Server permission. Invite code tracking will not be functional.",
                        inline=True)

    if len(perms['non-crit']) > 0:
        noncrit_msg = "Warning! The following channels are missing a **Non-Critical** permission. " \
                   "Gabby Gums will be continue to work as normal for now, " \
                   "but may be unable to utilize a future feature:\n\n"

        noncrit_msg = noncrit_msg + "\n".join(perms['non-crit'])
        embed.add_field(name="Non-Critical Permissions Problems", value=noncrit_msg, inline=True)

    guild_logging_channel = await get_guild_logging_channel(guild.id)
    if guild_logging_channel is not None:
        embed.add_field(name="Currently Configured Log Channel ", value="#{}".format(guild_logging_channel.name), inline=True)
    else:
        embed.add_field(name="Currently Configured Log Channel ", value="**NONE**", inline=True)

    channels_msg = ""
    _ignored_channels = await db.get_ignored_channels(pool, guild.id)
    if len(_ignored_channels) > 0:
        for channel_id in _ignored_channels:
            ignored_channel = await get_channel_safe(channel_id)
            channels_msg = channels_msg + "#{}\n".format(ignored_channel.name)
        embed.add_field(name="Channels Currently Being Ignored ", value=channels_msg, inline=True)
    else:
        embed.add_field(name="Channels Currently Being Ignored ", value="**NONE**", inline=True)

    if errors_found:
        embed.description = "Uh oh! Problems were found!"
    else:
        embed.description = "No problems found!"

    await ctx.send(embed=embed)


# ----- Debugging Channel Commands ----- #
@commands.is_owner()
@client.command(name="dump")
async def dump(ctx, table: str):
    await ctx.send("DB Dump for {}".format(table))
    table_msg = "```python\n"
    rows = await db.fetch_full_table(pool, table)

    for row in rows:
        table_msg = table_msg + str(row) + "\n"
    table_msg = table_msg + "```"
    await ctx.send(table_msg[0:2000] if len(table_msg) > 2000 else table_msg)


@commands.is_owner()
@client.command(name="test")
async def test_cmd(ctx):
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
    #Todo: Add more

    traceback_message = "```python\n{}```".format(traceback.format_exc())
    traceback_message = (traceback_message[:1993] + ' ...```') if len(traceback_message) > 2000 else traceback_message
    await error_log_channel.send(content=traceback_message, embed=embed)


@client.event
async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent):

    if payload.guild_id is None:
        return  # We are in a DM, Don't log the message

    log_channel = await get_guild_logging_channel(payload.guild_id)
    if log_channel is None:
        # Silently fail if no log channel is configured.
        return

    if payload.cached_message is not None:
        msg = payload.cached_message.content
        author = payload.cached_message.author
        channel = payload.cached_message.channel

        if client.user.id == author.id:
            return  # This is a Gabby Gums message. Do not log the event.

        if await is_user_ignored(pool, payload.guild_id, author.id):
            return

        if await is_channel_ignored(pool, payload.guild_id, payload.channel_id):
            return

        # Ensure message was not proxied by PluralKit.
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.pluralkit.me/msg/{}'.format(payload.cached_message.id)) as r:
                if r.status == 200:
                    return  # Message was proxied by PluralKit. Return instead of logging message

        # Needed for embeds with out text. Consider locally cacheing images so we can post those to the log.
        if msg == "":
            msg = "None"
        embed = embeds.deleted_message(message_content=msg, author=author, channel=channel)
        await log_channel.send(embed=embed)

    else:
        message_id = payload.message_id
        channel_id = payload.channel_id

        if await is_channel_ignored(pool, payload.guild_id, payload.channel_id):
            return

        embed = embeds.unknown_deleted_message(channel_id, message_id)
        await log_channel.send(embed=embed)


@client.event
async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent):

    if 'content' in payload.data:
        if "guild_id" not in payload.data:
            return  # We are in a DM, Don't log the message

        after_msg = payload.data['content']
        guild_id = int(payload.data["guild_id"])
        message_id = payload.message_id

        if payload.cached_message is not None:
            before_msg = payload.cached_message.content
            author = payload.cached_message.author
            author_id = author.id
            channel_id = payload.cached_message.channel.id
        else:
            before_msg = None
            author_id = payload.data['author']['id']
            channel_id = payload.data["channel_id"]
            author = None

        if client.user.id == author_id:
            # This is a Gabby Gums message. Do not log the event.
            return

        if await is_user_ignored(pool, guild_id, author_id):
            return

        if await is_channel_ignored(pool, guild_id, channel_id):
            return

        if author is None:
            await client.wait_until_ready()
            # TODO: Consider removing to prevent potential API call
            author = client.get_user(author_id)
            if author is None:
                print("get_user failed")
                author = await client.fetch_user(author_id)

        embed = embeds.edited_message(author_id, author.name, author.discriminator, channel_id, before_msg, after_msg, message_id, guild_id)

        log_channel = await get_guild_logging_channel(guild_id)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            return

        # try:
        await log_channel.send(embed=embed)


async def get_stored_invites(guild_id: int) -> db.StoredInvites:
    stored_invites = await db.get_invites(pool, guild_id)
    return stored_invites


async def update_invite_cache(guild: discord.Guild, invites: Optional[List[discord.Invite]] = None,
                              stored_invites: Optional[db.StoredInvites] = None):
    try:
        if not guild.me.guild_permissions.manage_guild:
            return

        if invites is None:
            invites: List[discord.Invite] = await guild.invites()

        for invite in invites:
            await db.store_invite(pool, guild.id, invite.id, invite.uses)

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
            await db.remove_invite(pool, guild_id, stored_invite.invite_id)


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
    log_msg = "UNABLE TO DETERMINE INVITE USED.\n Stored invites: {}, Current invites: {} \n" \
              "Server: {}, Member: {}".format(stored_invites, current_invites, repr(member.guild), repr(member))
    logging.info(log_msg)

    if 'error_log_channel' not in config:
        await update_invite_cache(member.guild, invites=current_invites)
        return None
    error_log_channel = client.get_channel(config['error_log_channel'])
    await error_log_channel.send(log_msg)

    await update_invite_cache(member.guild, invites=current_invites)
    return None


@client.event
async def on_member_join(member: discord.Member):

    if member.guild.me.guild_permissions.manage_guild:
        invite_used = await find_used_invite(member)
        if invite_used is not None:
            logging.info(
                "New user joined with link {} that has {} uses.".format(invite_used.invite_id, invite_used.uses))
        embed = embeds.member_join(member, invite_used)
    else:
        embed = embeds.member_join(member, None, manage_guild=False)

    log_channel = await get_guild_logging_channel(member.guild.id)
    if log_channel is None:
        # Silently fail if no log channel is configured.
        return

    await log_channel.send(embed=embed)


@client.event
async def on_member_remove(member: discord.Member):

    embed = embeds.member_leave(member)
    log_channel = await get_guild_logging_channel(member.guild.id)
    if log_channel is None:
        # Silently fail if no log channel is configured.
        return
    await log_channel.send(embed=embed)


@client.event
async def on_user_update(before, after):
    #username, Discriminator
    # print("User_update")
    # print(after)
    pass


@client.event
async def on_member_update(before: discord.Member, after: discord.Member):
    #nickname

    if before.nick != after.nick:
        print("<@{}> ({}#{}) changed their name from {} to {}".format(after.id, after.name, after.discriminator, before.nick, after.nick))

        log_channel = await get_guild_logging_channel(after.guild.id)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            return

        embed = embeds.member_nick_update(before, after)
        await log_channel.send(embed=embed)


@client.event
async def on_guild_join(guild: discord.Guild):
    # Todo: Move DB creation to a command.
    #  Having it here is fragile as a user could add the bot and on_guild_join may not ever fire if the bot is down at the time.
    # create an entry for the server in the database
    await db.add_server(pool, guild.id, guild.name)

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
        await db.remove_server(pool, guild.id)
        return
    error_log_channel = client.get_channel(config['error_log_channel'])
    await error_log_channel.send(log_msg)
    await db.remove_server(pool, guild.id)


@client.event
async def on_guild_unavailable(guild: discord.Guild):
    log_msg = "{} ({}) is unavailable.".format(guild.name, guild.id)
    logging.warning(log_msg)

    if 'error_log_channel' not in config:
        await db.remove_server(pool, guild.id)
        return
    error_log_channel = client.get_channel(config['error_log_channel'])
    await error_log_channel.send(log_msg)


if __name__ == '__main__':

    with open('config.json') as json_data_file:
        config = json.load(json_data_file)

    pool = asyncio.get_event_loop().run_until_complete(db.create_db_pool(config['db_uri']))
    asyncio.get_event_loop().run_until_complete(db.create_tables(pool))

    client.command_prefix = config['bot_prefix']
    client.run(config['token'])

    logging.info("cleaning Up and shutting down")
