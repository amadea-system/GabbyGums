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
from utils.paginator import FieldPages
# from embeds import member_nick_update

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class Utilities(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

    @commands.is_owner()
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.default)
    @commands.guild_only()
    @commands.command(brief="Owner only test command")
    async def cogtest(self, ctx: commands.Context):
        assert 1 == 0

    # region Invite Command
    @commands.group(name='invite',
                    aliases=['bot_invite'],
                    brief='Get an invite for Gabby Gums.',
                    description='Get an invite for Gabby Gums.')
    async def invite_link(self, ctx: commands.Context):
        # invite = "https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions={}".format(self.bot.user.id, 380096)  # Missing Manage Server
        if ctx.invoked_subcommand is None:
            perm = discord.Permissions(
                manage_guild=True,      # Required for invite tracking and management.
                add_reactions=True,     # Required for the reaction based menu system.
                view_audit_log=True,    # Required for determining who kicked/banned/unbanned a user
                read_messages=True,     # Required to log deleted & edited messages and to see commands being used.
                # manage_messages=True, # Required for the reaction based menu system. (Needed so we can remove the reactions from menus after a user clicks on a react & when the menu times out.) (New)
                embed_links=True,       # Required for the log messages and the configuration of the bot.
                attach_files=True,      # Required for logging deleted images. FUTURE FEATURE.
                read_message_history=True,  # Required for the reaction based menu system. (Can not react to a message that has reactions by other users with out this permission.)
                external_emojis=True,   # Required for the reaction based menu system as some of the reactions are custom reactions.
                send_messages=True,     # Required for the log messages and the configuration of the bot.
                manage_channels=True    # Required for invite events and improved accuracy of invite tracking.
            )

            link = discord.utils.oauth_url(self.bot.user.id, permissions=perm)
            await ctx.send(f"Here's a link to invite Gabby Gums to your server:\n{link}\n\n"
                           f"If you would like to see a breakdown of why Gabby Gums needs the requested permissions to operate properly, you can use the command `{ctx.bot.command_prefix}invite explain`")

    @invite_link.command(name='explain', brief="Explains why Gabby Gums needs the permissions requested.")
    async def invite_link_explain(self, ctx: commands.Context):
        embed = discord.Embed(title="Breakdown Of Requested Permissions",
                              description="Here is a breakdown of all the permissions Gabby Gums asks for and why.\n"
                                          "If you have any additional questions regarding these permissions, feel free to stop by our support server: https://discord.gg/3Ugade9\n",
                              color=discord.Color.from_rgb(80, 135, 135))

        embed.add_field(name="Manage Guild (Optional, Required for Invite Tracking)",
                        value="The Manage Guild permission is needed for seeing the invites that exist on your server and how many times they have been used.\n"
                              "This information is required for determining which invite a user used when they join your server.",
                        inline=False)

        embed.add_field(name="Manage Channels (Optional, Strongly recommended for Invite Tracking)",
                        value="The Manage Channels permission is needed to log the *Invite Create* and *Invite Delete* events.\n"
                              "Additionally, it __greatly__ helps with determining which invite a joining user used and is **strongly** recommended if you intend on using invite tracking.",
                        inline=False)

        embed.add_field(name="View Audit Log (Optional, Required for determining who did what and kick events.)",
                        value="The View Audit Log permission is needed to determine if a user left or was kicked.\n"
                              "It is also needed to determine who preformed an action that is being logged (e.g. Who Banned or Unbanned a user.)",
                        inline=False)

        embed.add_field(name="Attach Files (Optional, Required for Archive command and Bulk Delete Event)",
                        value="The Attach Files permission is needed to attach the archive files generated from the *Bulk Delete* event and the *Archive* command.",
                        inline=False)

        embed.add_field(name="Read Messages (Required)",
                        value="The Read Messages permission is required so that Gabby Gums can do pretty much anything at all.",
                        inline=False)

        embed.add_field(name="Embed Links (Required)",
                        value="The Embed Links permission is required to send Embeds (Like the one this explination is in).\n"
                              "Without it, no logs can be sent and most commands will not be operational.",
                        inline=False)

        embed.add_field(name="Send Messages (Required)",
                        value="The Send Messages permission is required to send any logs and to respond to any commands.\n",
                        inline=False)

        embed.add_field(name="Use External Emojis (Required)",
                        value="The Use External Emojis permission is required as some logs and configuration menus use external emojis in them.",
                        inline=False)

        embed.add_field(name="Add Reactions (Required)",
                        value="The Add Reactions permission is required for the reaction based menu system that some commands of use.",
                        inline=False)

        embed.add_field(name="Read Message History (Mostly Required)",
                        value="The Read Message History permission is required for the reaction based menu system in some cases.\n"
                              "Additionally, it is also needed for the *Archive* command to function.",
                        inline=False)
        await ctx.send(embed=embed)
    # endregion


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
        try:
            image_cache_du_used = folder_size("./image_cache/") / 1024 / 1024
            num_of_files_in_cache = sum([len(files) for r, d, files in os.walk("./image_cache/")])
        except FileNotFoundError as e:
            image_cache_du_used = -1
            num_of_files_in_cache = -1

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

    # region Verbose Permissions Verification Command
    @commands.command(name="verbose_perm",
                      brief="Shows all posible permission problems.",
                      description="Shows all posible permission problems.",
                      hidden=True
                      )
    async def verify_permissions_verbose(self, ctx: commands.Context, guild_id: Optional[str] = None):
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

        perms = {'read': [], 'send': [], 'non-crit': [], 'manage_guild': True, 'audit_log': True,
                 'embed_links': [], 'external_emojis': [], 'add_reactions': [], "read_msg_history": [], 'attach_files': []}
        errors_found = False

        if not guild.me.guild_permissions.manage_guild:
            errors_found = True
            perms['manage_guild'] = False

        if not guild.me.guild_permissions.view_audit_log:
            errors_found = True
            perms['audit_log'] = False

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

                if permissions.embed_links is False:  # Needed to actually send the embed messages
                    errors_found = True
                    perms['embed_links'].append(f"<#{channel.id}>")

                # if permissions.read_message_history is False:  # Needed for the archive command
                #     errors_found = True
                #     perms["read_msg_history"].append(f"<#{channel.id}>")

                if permissions.external_emojis is False:  # Needed for Channel Update logs and some commands
                    errors_found = True
                    perms["external_emojis"].append(f"<#{channel.id}>")

                if permissions.attach_files is False:  # Needed for Bulk Delete logs andthe archive command
                    errors_found = True
                    perms["attach_files"].append(f"<#{channel.id}>")

                # if permissions.add_reactions is False:  # Needed for some commands
                #     errors_found = True
                #     perms["add_reactions"].append(f"<#{channel.id}>")

        if len(perms['read']) > 0:
            read_msg = "ERROR!! The following channels do not have the **Read Messages** permission.\n" \
                       "Gabby Gums will be unable to log any events that happen in these channels:\n"
            read_msg = read_msg + "\n".join(perms['read'])
            embed.add_field(name="Read Messages Permissions Problems", value=f"{read_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        if len(perms['send']) > 0:
            send_msg = "ERROR!! The following channels do not have the **Send Messages** permission.\n" \
                       "Gabby Gums will be unable to respond to any commands that are executed in these channels " \
                       "and will be unable to use any of them as a logging channel:\n"
            send_msg = send_msg + "\n".join(perms['send'])
            embed.add_field(name="Send Messages Permissions Problems", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        if len(perms['embed_links']) > 0:
            send_msg = "ERROR!! The following channels do not have the **Embed Links** permission.\n" \
                       "Without this permission, Gabby Gums will be unable to respond to most commands that are executed in these channels " \
                       "and will be unable to use any of them as a logging channel:\n"
            send_msg = send_msg + "\n".join(perms['embed_links'])
            embed.add_field(name="Missing Embed Links Permission", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)


        if len(perms['external_emojis']) > 0:
            send_msg = "ERROR!! The following channels do not have the **Use External Emojis** permission.\n" \
                       "Without this permission, Most menu based commands will not be functional in these channels" \
                       " and will be unable to use any of them as a logging channel for some log events:\n"
            send_msg = send_msg + "\n".join(perms['external_emojis'])
            embed.add_field(name="Missing Use External Emojis Permission", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        # Shoule we add in read msg hist and add reactions?

        # if len(perms['add_reactions']) > 0:
        #     send_msg = "ERROR!! The following channels do not have the **Add Reactions** permission.\n" \
        #                "Without this permission, Most menu based commands will not be functional in these channels:\n"
        #     send_msg = send_msg + "\n".join(perms['add_reactions'])
        #     embed.add_field(name="Missing Add Reactions Permission", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
        #                     inline=False)

        if len(perms['add_reactions']) > 0:
            send_msg = "ERROR!! The following channels do not have the **Add Reactions** permission.\n" \
                       "Without this permission, Most menu based commands will not be functional in these channels:\n"
            send_msg = send_msg + "\n".join(perms['add_reactions'])
            embed.add_field(name="Missing Add Reactions Permission", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        if len(perms['attach_files']) > 0:
            send_msg = "ERROR!! The following channels do not have the **Attach Files** permission.\n" \
                       "Without this permission, Bulk Message Deletes will not be able to be logged to the following channels:\n"
            send_msg = send_msg + "\n".join(perms['attach_files'])
            embed.add_field(name="Missing Attach Files Permission", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=False)

        if not perms['manage_guild']:
            embed.add_field(name="Manage Server Permissions Problems",
                            value="Gabby Gums is missing the Manage Server permission. Invite code tracking will not be functional.",
                            inline=True)

        if not perms['audit_log']:
            embed.add_field(name="Missing View Audit Log Permissions",
                            value="Gabby Gums is missing the View Audit Log permission. This will prevent Gabby Gums from logging kick events and determining who did the following events: Member Ban & Unban, Channel Create, Channel Delete, Channel Update.",
                            inline=True)


        # if len(perms['non-crit']) > 0:
        #     noncrit_msg = "Warning! The following channels are missing a **Non-Critical** permission. " \
        #                   "Gabby Gums will be continue to work as normal for now, " \
        #                   "but may be unable to utilize a future feature:\n"
        #
        #     noncrit_msg = noncrit_msg + "\n".join(perms['non-crit'])
        #     embed.add_field(name="Non-Critical Permissions Problems", value=f"{noncrit_msg}\n\N{ZERO WIDTH NON-JOINER}",
        #                     inline=False)

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
        ignored_users_ids = await db.get_users_overrides(self.bot.db_pool, guild.id)
        if len(ignored_users_ids) > 0:
            for user_id in ignored_users_ids:
                ignored_users_msg_fragments.append(f"<@!{user_id}>")
            ignored_users_msg = "\n".join(ignored_users_msg_fragments)
            embed.add_field(name="Users Currently Being Ignored ",
                            value=f"{ignored_users_msg}\n\N{ZERO WIDTH NON-JOINER}",
                            inline=True)

        # List all channels being ignored
        channels_msg = ""
        _ignored_channels_ids = await db.get_channel_overrides(self.bot.db_pool, guild.id)
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
    # endregion

    # region Permissions Verification Command
    @commands.command(name="permissions",
                      aliases=["verify_permissions", "perm", "permissions_check", "perm_check", "verify_perm"],
                      brief="Checks for any permissions or configuration problems.",
                      description="Checks for any possible permission or configuration problems that could interfere with the operations of Gabby Gums",
                      )
    async def verify_permissions(self, ctx: commands.Context, guild_id: Optional[str] = None):

        # Current number of fields:  Perm: 8/25, Conf: 5/25

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
        perm_embed = discord.Embed(title="Permissions Debug for {}".format(guild.name), color=0x61cd72)

        perms = {'read': [], 'send': [], 'non-crit': [], 'embed_links': [], 'external_emojis': [],
                 'add_reactions': [], "read_msg_history": [], 'attach_files': [],
                 'manage_guild': True, 'audit_log': True, 'manage_channels': True}

        errors_found = False

        guild_logging_channel = await self.bot.get_event_or_guild_logging_channel(guild.id)
        event_configs = await db.get_server_log_configs(self.bot.db_pool, guild.id)

        msg_del_ch = await self.bot.get_event_or_guild_logging_channel(guild.id, 'message_delete')
        ch_update_ch = await self.bot.get_event_or_guild_logging_channel(guild.id, 'channel_update')
        # invite_create_ch = await self.bot.get_event_or_guild_logging_channel(guild.id, 'invite_create')
        # invite_delete_ch = await self.bot.get_event_or_guild_logging_channel(guild.id, 'invite_delete')

        if not guild.me.guild_permissions.manage_guild:
            errors_found = True
            perms['manage_guild'] = False

        if not guild.me.guild_permissions.view_audit_log:
            errors_found = True
            perms['audit_log'] = False

        if not guild.me.guild_permissions.manage_channels:
            errors_found = True
            perms['manage_channels'] = False

        for channel in guild.channels:
            channel: discord.TextChannel
            permissions: discord.Permissions = channel.guild.me.permissions_in(channel)

            if channel.type == discord.ChannelType.text:
                if permissions.read_messages is False:
                    errors_found = True
                    perms['read'].append(f"<#{channel.id}>")

                if permissions.send_messages is False:
                    if channel.id == guild_logging_channel.id or event_configs.contains_channel(channel.id):
                        errors_found = True
                        perms['send'].append(f"<#{channel.id}>")

                if permissions.embed_links is False:  # Needed to actually send the embed messages
                    if channel.id == guild_logging_channel.id or event_configs.contains_channel(channel.id):
                        errors_found = True
                        perms['embed_links'].append(f"<#{channel.id}>")

                if permissions.external_emojis is False:  # Needed for Channel Update logs and some commands
                    if ch_update_ch is not None and channel.id == ch_update_ch.id:
                        errors_found = True
                        perms["external_emojis"].append(f"<#{channel.id}>")

                if permissions.attach_files is False:  # Needed for Bulk Delete logs and the archive command
                    if msg_del_ch is not None and channel.id == msg_del_ch.id:
                        errors_found = True
                        perms["attach_files"].append(f"<#{channel.id}>")

        if len(perms['send']) > 0:
            send_msg = "\N{Warning Sign} CRITICAL ERROR!! The following channels are configured as logging channels but are missing the **Send Messages** permission.\n" \
                       "As such, no logs will be able to be sent in the following log channels:\n"
            send_msg = send_msg + "\n".join(perms['send'])
            perm_embed.add_field(name="Missing Send Messages Permissions in Logging Channels", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)

        if len(perms['embed_links']) > 0:
            send_msg = "\N{Warning Sign} CRITICAL ERROR!! The following channels are configured as logging channels but are missing the **Embed Links** permission.\n" \
                       "As such, no logs will be able to be sent in the following log channels:\n"
            send_msg = send_msg + "\n".join(perms['embed_links'])
            perm_embed.add_field(name="Missing Embed Links Permission in Logging Channels", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)

        if len(perms['external_emojis']) > 0:
            send_msg = "\N{Warning Sign} CRITICAL ERROR!! The channel configured for the **channel_update** event is missing the **Use External Emojis** permission.\n" \
                       "Without this permission, some log times may not be able to be logged in the following log channels:\n"
            send_msg = send_msg + "\n".join(perms['external_emojis'])
            perm_embed.add_field(name="Missing Use External Emojis Permission in Logging Channels",
                                 value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)

        if len(perms['attach_files']) > 0:
            send_msg = "\N{Warning Sign} CRITICAL ERROR!! The channel configured for the **message_delete** event is missing the **Attach Files** permission.\n" \
                       "As such, Bulk Message Deletes will not be able to be logged:\n"
            send_msg = send_msg + "\n".join(perms['attach_files'])
            perm_embed.add_field(name="Missing Attach Files Permission", value=f"{send_msg}\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)

        if not perms['manage_guild']:
            perm_embed.add_field(name="Manage Server Permissions Problems",
                                 value="Gabby Gums is missing the **Manage Server** permission. Invite code tracking will not be functional.",
                                 inline=False)

        if not perms['manage_channels']:
            perm_embed.add_field(name="Manage Channels Permissions Problems",
                                 value="Gabby Gums is missing the **Manage Channels** permission.\nGabby Gums will have a much harder time determining which invite was used by users joining this server.\n"
                                  "Additionally, this will prevent Gabby Gums from logging the Invite Create and Invite Delete events.",
                                 inline=False)

        if not perms['audit_log']:
            perm_embed.add_field(name="Missing View Audit Log Permissions",
                                 value="Gabby Gums is missing the **View Audit Log** permission. This will prevent Gabby Gums from logging kick events and determining who did the following events: Member Ban & Unban, Channel Create, Channel Delete, Channel Update.",
                                 inline=False)

        if len(perms['read']) > 0:
            read_msg = "ERROR!! The following channels do not have the **Read Messages** permission.\n" \
                       "Gabby Gums will be unable to log any events that happen in these channels:\n"
            read_msg = read_msg + "\n".join(perms['read'])
            perm_embed.add_field(name="Read Messages Permissions Problems", value=f"{read_msg}\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)

        # Set the appropriate embed description
        if errors_found:
            perm_embed.description = "Uh oh! Problems were found!"
        else:
            perm_embed.description = "No problems found!"

        # -- Now create another embed that lists out the current guild configs -- #
        conf_embed = discord.Embed(title=f"Configuration Debug for {guild.name}", color=0x61cd72)
        # List the default log channel

        if guild_logging_channel is not None:
            conf_embed.add_field(name="Default Log Channel ",
                                 value="<#{}>\n\N{ZERO WIDTH NON-JOINER}".format(guild_logging_channel.id), inline=True)
            default_log_channel = f"<#{guild_logging_channel.id}>"
        else:
            conf_embed.add_field(name="Default Log Channel ",
                                 value="**NONE**\n(This is not recommended. Please setup a default logging channel)\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=True)
            default_log_channel = "**NONE**"

        # List event specific logging configs
        event_config_msg_fragments = []
        for event_type in event_configs.available_event_types():
            event = event_configs[event_type]
            if event is None or event.log_channel_id is None:
                event_config_msg_fragments.append(f"__{event_type}:__\nLogging to {default_log_channel}")
            elif not event.enabled:
                event_config_msg_fragments.append(f"__{event_type}:__\nLogging Disabled")
            else:
                event_config_msg_fragments.append(f"__{event_type}:__\nLogging to <#{event.log_channel_id}>")

        event_config_msg = "\n".join(event_config_msg_fragments)
        conf_embed.add_field(name="Event Configurations", value=f"{event_config_msg}\n\N{ZERO WIDTH NON-JOINER}",
                             inline=True)

        # List all users being ignored
        ignored_users_msg_fragments = []
        ignored_users = await db.get_users_overrides(self.bot.db_pool, guild.id)
        if len(ignored_users) > 0:
            for ignored_user in ignored_users:
                if ignored_user['log_ch'] is not None:
                    ignored_users_msg_fragments.append(f"Redirect <@{ignored_user['user_id']}> -> <#{ignored_user['log_ch']}>")
                else:
                    ignored_users_msg_fragments.append(f"Ignored: <@{ignored_user['user_id']}>")

            ignored_users_msg = "\n".join(ignored_users_msg_fragments)
            conf_embed.add_field(name="Users Currently Being Ignored or Redirected",
                                 value=f"{ignored_users_msg}\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)

        # List all channels being ignored
        channels_msg = []
        channel_overrides = await db.get_channel_overrides(self.bot.db_pool, guild.id)
        if len(channel_overrides) > 0:
            for ch_override in channel_overrides:
                ignored_channel = await self.bot.get_channel_safe(ch_override['channel_id'])
                if ignored_channel is not None:
                    if ch_override['log_ch'] is not None:
                        channels_msg.append(f"Redirect <#{ch_override['channel_id']}> -> <#{ch_override['log_ch']}>")
                    else:
                        channels_msg.append(f"Ignored: <#{ch_override['channel_id']}>")

                else:
                    channels_msg.append("Deleted channel w/ ID: {}\n".format(ch_override['channel_id']))
            channels_msg = '\n'.join(channels_msg)
            conf_embed.add_field(name="Channels Currently Being Ignored or Redirected", value=f"{channels_msg}\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)
        else:
            conf_embed.add_field(name="Channels Currently Being Ignored or Redirected", value="**NONE**\n\N{ZERO WIDTH NON-JOINER}",
                                 inline=False)

        # List all categories being ignored
        _ignored_categories = await db.get_ignored_categories(self.bot.db_pool, guild.id)
        if len(_ignored_categories) > 0:
            categories_id_msg_fragments = [f"<#{category_id}>  *(ID: {category_id})*" for category_id in
                                           _ignored_categories]
            categories_msg = "\n".join(categories_id_msg_fragments)
            conf_embed.add_field(name="All channels under the following categories are currently being ignored ",
                                 value=f"{categories_msg}\n\N{ZERO WIDTH NON-JOINER}", inline=False)
        else:
            conf_embed.add_field(name="All channels under the following categories are currently being ignored ",
                                 value="**NONE**\n\N{ZERO WIDTH NON-JOINER}", inline=False)

        # conf_embed.description = "\N{ZERO WIDTH NON-JOINER}\n\N{ZERO WIDTH NON-JOINER}"

        await ctx.send(embed=perm_embed)
        await ctx.send(embed=conf_embed)
    # endregion

    # region DB Performance Statistics Command
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.default)
    @commands.command(aliases=["db_stats", "db_performance"],
                      brief="Shows various time stats for the database.",)
    async def db_perf(self, ctx: commands.Context):

        embed_entries = []
        stats = db.db_perf.stats()

        for key, value in stats.items():
            # Don't bother showing stats for one offs
            if key != 'create_tables' and key != 'migrate_to_latest':
                header = f"{key}"

                msg_list = []
                for sub_key, sub_value in value.items():
                    if sub_key == "calls":
                        msg_list.append(f"{sub_key}: {sub_value:.0f}")
                    else:
                        msg_list.append(f"{sub_key}: {sub_value:.2f}")

                if len(msg_list) > 0:
                    msg = "\n".join(msg_list)
                    embed_entries.append((header, msg))

        page = FieldPages(ctx, entries=embed_entries, per_page=15)
        page.embed.title = f"DB Statistics:"
        await page.paginate()
    # endregion

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):

        if 'error_log_channel' not in self.bot.config:
            return
        error_log_channel = self.bot.get_channel(self.bot.config['error_log_channel'])

        if isinstance(error, commands.CommandOnCooldown):
            # DDOS Protection. Send alerts in the error log if we are potentially being DDOSed with resource intensive commands.
            # Only in this cog atm as these are the high risk items.
            await error_log_channel.send(f"⚠ Excessive use of {ctx.command.module}.{ctx.command.name} by <@{ctx.author}> ({ctx.author.id}) in {ctx.guild} ⚠ ")
            return


def setup(bot):
    bot.add_cog(Utilities(bot))
