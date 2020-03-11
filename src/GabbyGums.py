'''

'''

import time
import json
import os
import logging
import traceback
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Dict, Union
from datetime import timedelta

import psutil
import asyncpg
import aiohttp
import discord
from discord.ext import commands
from discord.utils import oauth_url

import db
import embeds
import miscUtils
import GuildConfigs
from imgUtils.avatarChangedImgProcessor import get_avatar_changed_image
from bot import GGBot

if TYPE_CHECKING:
    from events.memberJoinLeave import MemberJoinLeave

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

client = GGBot(command_prefix="g!",
               max_messages=100000,
               # description="A simple logging bot that ignores PluralKit proxies.\n",
               owner_id=389590659335716867,
               case_insensitive=True)
# client.remove_command("help")  # Remove the built in help command so we can make the about section look nicer.


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

    # ensure the invite cache is upto date on connection.
    logging.warning("Gabby Gums is fully loaded.")


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








@commands.is_owner()
@client.command(name="test")
async def test_cmd(ctx: commands.Context):
    pass


# ---- Command Error Handling ----- #
@client.event
async def on_command_error(ctx, error):

    # https://gist.github.com/EvieePy/7822af90858ef65012ea500bcecf1612
    # This prevents any commands with local handlers being handled here in on_command_error.
    if hasattr(ctx.command, 'on_error'):
        return

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
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send("⚠ {}".format(error))
    else:
        await ctx.send("⚠ {}".format(error))
        raise error


# ----- Discord Events ----- #
@client.event
async def on_message(message: discord.Message):

    if message.author.id != client.user.id and message.guild is not None:  # Don't log our own messages or DM messages.

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
                    attachments.append(attachment_filename)
                except FileNotFoundError as e:
                    # If the directory(s) do not exist, create them and then re-save
                    Path("./image_cache/{}".format(message.guild.id)).mkdir(parents=True, exist_ok=True)
                    await attachment.save("./image_cache/{}/{}".format(message.guild.id, attachment_filename))
                    attachments.append(attachment_filename)
                except Exception as e:
                    await miscUtils.log_error_msg(client, e)

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

    # await log_channel.send(embed=embed)
    await client.send_log(log_channel, event_type, embed=embed)
    if len(attachments) > 0:
        await log_channel.send(content="Deleted Attachments:", files=attachments)  # Not going to bother using the safe log sender here yet.

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
        await miscUtils.log_error_msg(client, error_msg, header=f"{error_header}!ERROR!")
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
        await miscUtils.log_error_msg(client, error_msg, header=error_header)


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
        # await log_channel.send(embed=embed)
        await client.send_log(log_channel, event_type, embed=embed)

        if db_cached_message is not None:
            await db.update_cached_message(client.db_pool, payload.data['guild_id'], payload.message_id, after_msg)


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
                # await log_channel.send(embed=embed)
                await client.send_log(log_channel, event_type_name, embed=embed)


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
                    # await log_channel.send(file=avatar_changed_img, embed=embed)
                    await client.send_log(log_channel, event_type_avatar, embed=embed, file=avatar_changed_img)


@client.event
async def on_guild_join(guild: discord.Guild):
    # Todo: Move DB creation to a command.
    #  Having it here is fragile as a user could add the bot and on_guild_join may not ever fire if the bot is down at the time.
    # create an entry for the server in the database
    await db.add_server(client.db_pool, guild.id, guild.name)
    invites: 'MemberJoinLeave' = client.get_cog('MemberJoinLeave')
    await invites.update_invite_cache(guild)

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
    client.hmac_key = bytes(config['hmac_key'], encoding='utf-8')

    client.load_cogs()
    client.run(config['token'])

    logging.info("cleaning Up and shutting down")
