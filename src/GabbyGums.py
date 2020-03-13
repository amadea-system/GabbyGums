'''

'''

import json
import logging
import traceback
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Dict, Union

import psutil
import asyncpg
import aiohttp
import discord
from discord.ext import commands

import db
import embeds
import miscUtils


from bot import GGBot

if TYPE_CHECKING:
    from events.memberJoinLeave import MemberJoinLeave

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

client = GGBot(command_prefix="g!",
               max_messages=100000,
               # description="A simple logging bot that ignores PluralKit proxies.\n",
               owner_id=389590659335716867,
               case_insensitive=True)


async def is_channel_ignored(pool: asyncpg.pool.Pool, guild_id: int, channel_id: int) -> bool:
    _ignored_channels = await db.get_ignored_channels(pool, int(guild_id))
    if int(channel_id) in _ignored_channels:
        return True  # TODO: Optimise this
    return False


async def is_category_ignored(pool: asyncpg.pool.Pool, guild_id: int, category: Optional[discord.CategoryChannel]) -> bool:
    if category is not None:  # If channel is not in a category, don't bother querying DB
        _ignored_categories = await db.get_ignored_categories(pool, int(guild_id))
        if category.id in _ignored_categories:
            return True
    return False


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
