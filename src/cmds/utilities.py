"""
Cog containing various utility commands.
Commands include:
    cogtest
    bot_invite
    ping
    stats
    verify_perm

Part of the Gabby Gums Discord Logger.
"""

import os
import time
import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import psutil
import discord
from discord.ext import commands

import db
# from embeds import member_nick_update

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class Utilities(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.is_owner()
    @commands.guild_only()
    @commands.command(brief="Owner only test command")
    async def cogtest(self, ctx: commands.Context):
        assert 1 == 0


    @commands.command(name='bot_invite',
                      brief='Get an invite for Gabby Gums.',
                      description='Get an invite for Gabby Gums.')
    async def invite_link(self, ctx: commands.Context):
        # Todo: Calculate permissions instead of hardcoding and use discord.utils.oauth_url
        invite = "https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions={}".format(self.bot.user.id,
                                                                                                        380096)
        await ctx.send("Here's a link to invite Gabby Gums to your server:")
        await ctx.send(invite)


    @commands.guild_only()
    @commands.command(name='ping', aliases=['pong'],
                      brief='Shows the current bot latency.',
                      description='Shows the current bot latency.')
    async def ping_command(self, ctx: commands.Context):

        db_start = time.perf_counter()
        await db.get_log_channel(self.bot.db_pool, ctx.guild.id)  # Get the log to test DB speed
        db_end = time.perf_counter()

        embed = discord.Embed(title="Pinging...", description=" \n ", color=0x00b7fa)
        start = time.perf_counter()
        # Gets the timestamp when the command was used

        msg = await ctx.send(embed=embed)
        # Sends a message to the user in the channel the message with the command was received.
        # Notifies the user that pinging has started
        new_embed = discord.Embed(title="Pong!",
                                  description="Round trip messaging time: **{:.2f} ms**. \nAPI latency: **{:.2f} ms**.\nDatabase latency: **{:.2f} ms**".
                                  format((time.perf_counter() - start) * 1000, self.bot.latency * 1000,
                                         (db_end - db_start) * 1000), color=0x00b7fa)
        await msg.edit(embed=new_embed)


    @commands.command(name='stats', aliases=['stat', 'top'],
                      brief='Shows stats such as CPU, memory usage, disk space usage.',
                      description='Shows various stats such as CPU, memory usage, disk space usage, and more.')
    async def stats_command(self, ctx: commands.Context):

        def folder_size(path='.'):
            total = 0
            for entry in os.scandir(path):
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += folder_size(entry.path)
            return total

        pid = os.getpid()
        py = psutil.Process(pid)
        memory_use = py.memory_info()[0] / 1024 / 1024
        disk_usage = psutil.disk_usage("/")
        disk_space_free = disk_usage.free / 1024 / 1024
        disk_space_used = disk_usage.used / 1024 / 1024
        disk_space_percent_used = disk_usage.percent
        image_cache_du_used = folder_size("./image_cache/") / 1024 / 1024
        num_of_files_in_cache = sum([len(files) for r, d, files in os.walk("./image_cache/")])

        num_of_db_cached_messages = await db.get_number_of_rows_in_messages(self.bot.db_pool)
        try:
            # noinspection PyUnresolvedReferences
            load_average = os.getloadavg()
        except AttributeError:  # Get load avg is not available on windows
            load_average = [-1, -1, -1]

        embed = discord.Embed(title="CPU and memory usage:",
                              description="CPU: **{}%** \nLoad average: **{:.2f}, {:.2f}, {:.2f}**\nMemory: **{:.2f} MB**"
                                          "\nDisk space: **{:.2f} MB Free**, **{:.2f} MB Used**, **{}% Used**\nDisk space used by image cache: **{:.2f} MB Used** with **{} files** \nCached messages in DB: **{}**\nCached messages in memory: **{}**\n# of guilds: **{}**".
                              format(psutil.cpu_percent(), load_average[0], load_average[1], load_average[2],
                                     memory_use,
                                     disk_space_free, disk_space_used, disk_space_percent_used, image_cache_du_used,
                                     num_of_files_in_cache, num_of_db_cached_messages, len(self.bot.cached_messages),
                                     len(self.bot.guilds)), color=0x00b7fa)

        await ctx.send(embed=embed)


    @commands.command(name="verify_perm", aliases=["verify_permissions", "permissions", "perm", "permissions_check", "perm_check"],
                      brief="Checks for any permissions or configuration problems.",
                      description="Checks for any possible permission or configuration problems that could interfere with the operations of Gabby Gums",
                      )
    async def verify_permissions(self, ctx: commands.Context, guild_id: Optional[str] = None):
        # TODO: Restrict usage

        if guild_id is not None:
            guild: discord.Guild = self.bot.get_guild(int(guild_id.strip()))
        else:
            guild: discord.Guild = ctx.guild

        if guild is None:
            if guild_id is None:
                await ctx.send("A Guild ID is required in DMs")
            else:
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

                if (permissions.view_audit_log is False) or (permissions.embed_links is False) or \
                        (permissions.read_message_history is False) or (permissions.external_emojis is False) or \
                        permissions.attach_files is False or permissions.add_reactions is False:
                    errors_found = True
                    perms['non-crit'].append(f"<#{channel.id}>")
                    # TODO: Actually List out the missing not-critical permissions.

        if len(perms['read']) > 0:
            read_msg = "ERROR!! The following channels do not have the **Read Messages** permission. " \
                       "Gabby Gums will be unable to log any events that happen in these channels:\n"
            read_msg = read_msg + "\n".join(perms['read'])
            embed.add_field(name="Read Messages Permissions Problems", value=f"{read_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        if len(perms['send']) > 0:
            send_msg = "ERROR!! The following channels do not have the **Send Messages** permission. " \
                       "Gabby Gums will be unable to respond to any commands that are executed in these channels " \
                       "and will be unable to use any of them as a logging channel:\n"
            send_msg = send_msg + "\n".join(perms['send'])
            embed.add_field(name="Send Messages Permissions Problems", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        if not perms['manage_guild']:
            embed.add_field(name="Manage Server Permissions Problems",
                            value="Gabby Gums is missing the Manage Server permission. Invite code tracking will not be functional.",
                            inline=True)

        if len(perms['non-crit']) > 0:
            noncrit_msg = "Warning! The following channels are missing a **Non-Critical** permission. " \
                          "Gabby Gums will be continue to work as normal for now, " \
                          "but may be unable to utilize a future feature:\n"

            noncrit_msg = noncrit_msg + "\n".join(perms['non-crit'])
            embed.add_field(name="Non-Critical Permissions Problems", value=f"{noncrit_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        # List the default log channel
        guild_logging_channel = await self.bot.get_event_or_guild_logging_channel(guild.id)
        if guild_logging_channel is not None:
            embed.add_field(name="Default Log Channel ",
                            value="<#{}>\n\N{ZERO WIDTH NON-JOINER}".format(guild_logging_channel.id), inline=True)
            default_log_channel = f"<#{guild_logging_channel.id}>"
        else:
            embed.add_field(name="Default Log Channel ", value="**NONE**\n(This is not recommended. Please setup a default logging channel)\n\N{ZERO WIDTH NON-JOINER}", inline=True)
            default_log_channel = "**NONE**"

        # List event specific logging configs
        event_config_msg_fragments = []
        event_configs = await db.get_server_log_configs(self.bot.db_pool, guild.id)
        for event_type in event_configs.available_event_types():
            event = event_configs[event_type]
            if event is None or event.log_channel_id is None:
                event_config_msg_fragments.append(f"__{event_type}:__\nLogging to {default_log_channel}")
            elif not event.enabled:
                event_config_msg_fragments.append(f"__{event_type}:__\nLogging Disabled")
            else:
                event_config_msg_fragments.append(f"__{event_type}:__\nLogging to <#{event.log_channel_id}>")

        event_config_msg = "\n".join(event_config_msg_fragments)
        embed.add_field(name="Event Configurations", value=f"{event_config_msg}\n\N{ZERO WIDTH NON-JOINER}",
                        inline=True)

        # List all users being ignored
        ignored_users_msg_fragments = []
        ignored_users_ids = await db.get_ignored_users(self.bot.db_pool, guild.id)
        if len(ignored_users_ids) > 0:
            for user_id in ignored_users_ids:
                ignored_users_msg_fragments.append(f"<@!{user_id}>")
            ignored_users_msg = "\n".join(ignored_users_msg_fragments)
            embed.add_field(name="Users Currently Being Ignored ",
                            value=f"{ignored_users_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=True)

        # List all channels being ignored
        channels_msg = ""
        _ignored_channels_ids = await db.get_ignored_channels(self.bot.db_pool, guild.id)
        if len(_ignored_channels_ids) > 0:
            for channel_id in _ignored_channels_ids:
                ignored_channel = await self.bot.get_channel_safe(channel_id)
                if ignored_channel is not None:
                    channels_msg = channels_msg + "<#{}>\n".format(ignored_channel.id)
                else:
                    channels_msg = channels_msg + "Deleted channel w/ ID: {}\n".format(channel_id)
            embed.add_field(name="Channels Currently Being Ignored ", value=f"{channels_msg}\N{ZERO WIDTH NON-JOINER}",
                            inline=True)
        else:
            embed.add_field(name="Channels Currently Being Ignored ", value="**NONE**\n\N{ZERO WIDTH NON-JOINER}",
                            inline=True)

        # List all categories being ignored
        _ignored_categories = await db.get_ignored_categories(self.bot.db_pool, guild.id)
        if len(_ignored_categories) > 0:
            categories_id_msg_fragments = [f"<#{category_id}>  *(ID: {category_id})*" for category_id in
                                           _ignored_categories]
            categories_msg = "\n".join(categories_id_msg_fragments)
            embed.add_field(name="All channels under the following categories are currently being ignored ",
                            value=f"{categories_msg}\n\N{ZERO WIDTH NON-JOINER}", inline=True)
        else:
            embed.add_field(name="All channels under the following categories are currently being ignored ",
                            value="**NONE**\n\N{ZERO WIDTH NON-JOINER}", inline=True)

        # Set the appropriate embed description
        if errors_found:
            embed.description = "Uh oh! Problems were found!"
        else:
            embed.description = "No problems found!"

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Utilities(bot))
