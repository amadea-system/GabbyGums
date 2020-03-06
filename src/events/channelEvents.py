"""
Cog for the on_guild_channel_create, on_guild_channel_delete, and on_guild_channel_update events.
Logs from these event include:
    When a new channel is created in a guild (on_guild_channel_create)
    When a channel is deleted from a guild (on_guild_channel_delete)
    When a channel in a guild is modified. Name, permissions, etc. (on_guild_channel_update)

Part of the Gabby Gums Discord Logger.
"""

# import asyncio
import string
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Union, Optional  # , Dict, List, Tuple, NamedTuple

import discord
from discord.ext import commands

from miscUtils import split_text

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)

# Formatting for now and before text in embeds.
now_txt = "Now:\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{PUNCTUATION SPACE}\N{HAIR SPACE}"
before_txt = "Before:\N{NO-BREAK SPACE}\N{SIX-PER-EM SPACE}"

# Type aliases
GuildChannel = Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel]


class ChannelEvents(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

    async def check_if_ignored(self, channel: GuildChannel) -> bool:
        """Checks to see if the channel and/or category is ignored. Returns True if it is."""
        if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.VoiceChannel):
            if await self.bot.is_channel_ignored(channel.guild.id, channel.id):
                return True

            if await self.bot.is_category_ignored(channel.guild.id, channel.category):
                return True

        if isinstance(channel, discord.CategoryChannel):
            if await self.bot.is_category_ignored(channel.guild.id, channel):
                return True

        return False

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: GuildChannel):
        """Handles the 'on_guild_channel_create' event."""
        event_type = "channel_create"

        log_ch = await self.bot.get_event_or_guild_logging_channel(channel.guild.id, event_type)
        if log_ch is not None:
            category = channel if isinstance(channel, discord.CategoryChannel) else channel.category
            ignored = await self.check_if_ignored(category)  # Only check Category ,Channel is new so it can't be ignored.
            if not ignored:
                embed = await self.get_channel_create_embed(channel)

                # await log_ch.send(embed=embed)
                await self.bot.send_log(log_ch, event_type, embed=embed)


    async def get_channel_create_embed(self, channel: GuildChannel) -> discord.Embed:
        """Constructs the embed for the 'on_guild_channel_create' event."""
        _type = description = field_value = None  # Keep MyPy happy
        if isinstance(channel, discord.TextChannel):
            # log.info(f"New Text channel created! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Text Channel"
            if channel.category is not None:
                description = f"A new text channel was created in {channel.category}."
            else:
                description = f"A new text channel was created."

        if isinstance(channel, discord.VoiceChannel):
            # log.info(f"New Voice channel created! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Voice Channel"
            if channel.category is not None:
                description = f"A new voice channel was created in {channel.category}."
            else:
                description = f"A new voice channel was created."

        if isinstance(channel, discord.CategoryChannel):
            # log.info(f"New Category created! {channel.name}, Pos: {channel.position}")
            _type = "Category"
            description = f"A new category was created."

        embed = discord.Embed(title=f"{_type} Created",
                              description=description,
                              timestamp=datetime.utcnow(), color=discord.Color.blue())

        embed.set_footer(text=f"Channel ID: {channel.id}")
        embed.add_field(name=f"New {_type}:", value=f"<#{channel.id}>  -  #{channel.name}", inline=False)
        if channel.category is not None:
            embed.add_field(name="In Category:", value=channel.category, inline=False)
        # embed.add_field(name="Location:", value= , inline=False)  #await self.find_nearby_channel(channel)
        return embed

    # async def find_nearby_channel(self, channel: GuildChannel):
    #     await asyncio.sleep(1)
    #     guild: discord.Guild = channel.guild
    #     if isinstance(channel, discord.TextChannel):
    #         if channel.position == 0:
    #             return "Top Most Text Channel"
    #         else:
    #             channels = guild.text_channels
    #             log.info(f"Channels: {channels}")
    #             log.info(f"New ch pos: {channel.position}")
    #             log.info(f"Channels len: {len(channels)}")
    #             index = channel.position - 1
    #             log.info(f"index: {index}")
    #             below_ch = channels[index]
    #             log.info(f"Below ch pos: {below_ch.position}")
    #
    #             below_ch = guild.text_channels[channel.position-1]
    #             return f"Below <#{below_ch.id}>"
    #
    #     if isinstance(channel, discord.VoiceChannel):
    #         if channel.position == 0:
    #             return "Top Most Voice Channel"
    #         else:
    #             below_ch = guild.voice_channels[channel.position-1]
    #             return f"Below: <#{below_ch.id}>"
    #
    #     if isinstance(channel, discord.CategoryChannel):
    #         if channel.position == 0:
    #             return "Top Most Category"
    #         else:
    #             below_ch = guild.categories[channel.position-1]
    #             return f"Below: {below_ch.name}"


    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: GuildChannel):
        """Handles the 'on_guild_channel_delete' event."""
        event_type = "channel_delete"

        log_ch = await self.bot.get_event_or_guild_logging_channel(channel.guild.id, event_type)
        if log_ch is not None:
            ignored = await self.check_if_ignored(channel)
            if not ignored:
                embed = await self.get_channel_delete_embed(channel)
                # await log_ch.send(embed=embed)
                await self.bot.send_log(log_ch, event_type, embed=embed)


    @classmethod
    async def get_channel_delete_embed(cls, channel: GuildChannel) -> discord.Embed:
        """Constructs the embed for the 'on_guild_channel_delete' event."""

        _type = description = None  # Keep MyPy happy
        if isinstance(channel, discord.TextChannel):
            # log.info(f"Text channel deleted! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Text Channel"
            if channel.category is not None:
                description = f"A text channel was deleted from {channel.category}."
            else:
                description = f"A text channel was deleted."
        if isinstance(channel, discord.VoiceChannel):
            # log.info(f"Voice channel deleted! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Voice Channel"
            if channel.category is not None:
                description = f"A voice channel was deleted from {channel.category}."
            else:
                description = f"A voice channel was deleted."
        if isinstance(channel, discord.CategoryChannel):
            # log.info(f"Category deleted! {channel.name}, Pos: {channel.position}")
            _type = "Category"
            description = f"A category was deleted."

        embed = discord.Embed(title=f"{_type} Deleted",
                              description=description,
                              timestamp=datetime.utcnow(), color=discord.Color.dark_blue())

        embed.set_footer(text=f"Channel ID: {channel.id}")
        embed.add_field(name=f"Deleted {_type}", value=f"#{channel.name}  -  ID: {channel.id}", inline=False)

        if channel.category is not None:
            embed.add_field(name="From Category:", value=channel.category, inline=False)
        # embed.add_field(name="Former Location:", value=await cls.find_former_channel_location(channel), inline=False)
        return embed


    # @staticmethod
    # async def find_former_channel_location(channel: GuildChannel):
    #     guild: discord.Guild = channel.guild
    #     if isinstance(channel, discord.TextChannel):
    #         if channel.position == 0:
    #             return "Top Most Text Channel"
    #         else:
    #             channels = guild.text_channels
    #             log.info(f"Channels: {channels}")
    #             log.info(f"Deleted ch pos: {channel.position}")
    #
    #             below_ch = channels[channel.position]
    #             log.info(f"Below ch pos: {below_ch.position}")
    #             return f"Below <#{below_ch.id}>"
    #
    #     if isinstance(channel, discord.VoiceChannel):
    #         if channel.position == 0:
    #             return "Top Most Voice Channel"
    #         else:
    #             below_ch = guild.voice_channels[channel.position]
    #             return f"Below: <#{below_ch.id}>"
    #
    #     if isinstance(channel, discord.CategoryChannel):
    #         if channel.position == 0:
    #             return "Top Most Category"
    #         else:
    #             below_ch = guild.categories[channel.position]
    #             return f"Below: {below_ch.name}"


    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: GuildChannel, after: GuildChannel):
        """Handles the 'on_guild_channel_update' event."""
        event_type = "channel_update"

        # log.info(f"{event_type} fired!")
        if before.position == after.position:  # Filter out position change spam

            log_ch = await self.bot.get_event_or_guild_logging_channel(before.guild.id, event_type)

            if log_ch is not None:
                ignored = await self.check_if_ignored(after)
                if not ignored:
                    if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
                        embed = self.get_text_ch_update_embed(before, after)
                        if embed is not None:
                            # await log_ch.send(embed=embed)
                            await self.bot.send_log(log_ch, event_type, embed=embed)

                    if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
                        embed = self.get_voice_ch_update_embed(before, after)
                        if embed is not None:
                            # await log_ch.send(embed=embed)
                            await self.bot.send_log(log_ch, event_type, embed=embed)

                    if isinstance(before, discord.CategoryChannel) and isinstance(after, discord.CategoryChannel):
                        embed = self.get_category_ch_update_embed(before, after)
                        if embed is not None:
                            # await log_ch.send(embed=embed)
                            await self.bot.send_log(log_ch, event_type, embed=embed)


    @classmethod
    def get_text_ch_update_embed(cls, before: discord.TextChannel, after: discord.TextChannel) -> Optional[discord.Embed]:
        """Constructs the embed for the 'on_guild_channel_update' event for text channels."""
        # log.info(f"Text channel Updated! {after.name} in {after.category}, Pos: {after.position}")
        embed = discord.Embed(title="Text Channel Updated",
                              description=f"Update info for: <#{after.id}>",
                              timestamp=datetime.utcnow(), color=discord.Color.blurple())

        embed.set_footer(text=f"Channel ID: {after.id}")

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{before_txt}**{before.name}**\n{now_txt}**{after.name}**")

        if before.category != after.category:
            embed.add_field(name="Category Changed",
                            value=f"{before_txt}**{before.category}**\n{now_txt}**{after.category}**")

        if before.topic != after.topic:
            if not (before.topic is None and after.topic == ""):
                embed.add_field(name="Topic Changed:",
                                value=f"{before_txt}**{before.topic}**\n{now_txt}**{after.topic}**")

        if before.slowmode_delay != after.slowmode_delay:
            before_delay = f"{before.slowmode_delay} Sec" if before.slowmode_delay > 0 else "Disabled"
            after_delay = f"{after.slowmode_delay} Sec" if after.slowmode_delay > 0 else "Disabled"

            embed.add_field(name="Slowmode Delay Changed:",
                            value=f"{before_txt}**{before_delay}**\n{now_txt}**{after_delay}**")

        if before.is_nsfw() != after.is_nsfw():
            before_nsfw = "Yes" if before.is_nsfw() else "No"
            after_nsfw = "Yes" if after.is_nsfw() else "No"

            embed.add_field(name="NSFW Status Changed:",
                            value=f"{before_txt}**{before_nsfw}**\n{now_txt}**{after_nsfw}**")

        # if before.changed_roles != after.changed_roles:
        #     embed.add_field(name="changed_roles Changed:", value=f"{now_txt}{after.changed_roles}\n{before_txt}{before.changed_roles}")

        if before.overwrites != after.overwrites:
            embed = cls.determine_changed_overrides(embed, before, after)

        return embed if len(embed.fields) > 0 else None


    @classmethod
    def get_voice_ch_update_embed(cls, before: discord.VoiceChannel, after: discord.VoiceChannel) -> Optional[discord.Embed]:
        """Constructs the embed for the 'on_guild_channel_update' event for voice channels."""
        embed = discord.Embed(title="Voice Channel Updated",
                              description=f"Update info for: <#{after.id}>",
                              timestamp=datetime.utcnow(), color=discord.Color.blurple())

        embed.set_footer(text=f"Channel ID: {after.id}")

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{before_txt}**{before.name}**\n{now_txt}**{after.name}**")

        if before.category != after.category:
            embed.add_field(name="Category Changed",
                            value=f"{before_txt}**{before.category}**\n{now_txt}**{after.category}**")

        if before.bitrate != after.bitrate:
            embed.add_field(name="Audio Bitrate Changed:",
                            value=f"{before_txt}**{before.bitrate // 1000} kbps**\n{now_txt}**{after.bitrate // 1000} kbps**")

        if before.user_limit != after.user_limit:
            embed.add_field(name="User Limit Changed:",
                            value=f"{before_txt}**{before.user_limit}**\n{now_txt}**{after.user_limit}**")

        if before.overwrites != after.overwrites:
            embed = cls.determine_changed_overrides(embed, before, after)

        return embed if len(embed.fields) > 0 else None


    @classmethod
    def get_category_ch_update_embed(cls, before: discord.CategoryChannel, after: discord.CategoryChannel) -> Optional[discord.Embed]:
        """Constructs the embed for the 'on_guild_channel_update' event for categories."""
        embed = discord.Embed(title="Category Updated",
                              description=f"Update info for category <#{after.id}>",
                              timestamp=datetime.utcnow(), color=discord.Color.blurple())

        embed.set_footer(text=f"Category ID: {after.id}")

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{before_txt}**{before.name}**\n{now_txt}**{after.name}**")

        if before.is_nsfw() != after.is_nsfw():
            before_nsfw = "Yes" if before.is_nsfw() else "No"
            after_nsfw = "Yes" if after.is_nsfw() else "No"
            embed.add_field(name="NSFW Status Changed:",
                            value=f"{before_txt}**{before_nsfw}**\n{now_txt}**{after_nsfw}**")

        if before.overwrites != after.overwrites:
            embed = cls.determine_changed_overrides(embed, before, after)

        return embed if len(embed.fields) > 0 else None


    @classmethod
    def determine_changed_overrides(cls, embed: discord.Embed, before: GuildChannel, after: GuildChannel) -> discord.Embed:
        """Determines which overwrites (if any) have changed, and adds fields to an embed as necessary to reflect those changes."""
        change_msgs = []
        for key, before_overwrites in before.overwrites.items():  # Iterate through the before overwrites
            after_overwrites = after.overwrites[key] if key in after.overwrites else None  # Get the corresponding new overwrite.
            if before_overwrites != after_overwrites:  # If they have changed

                _type = f"Role" if isinstance(key, discord.Role) else f"Member"  # Record if it's a role or member having the permissions changed.
                prefix = "@" if key.name != "@everyone" else ""
                header = f"{_type} Permission Overwrites for {prefix}{key.name}:\n"  # Write out the appropriate embed header.
                if after_overwrites is not None:
                    after_set = set(after_overwrites)
                    before_set = set(before_overwrites)

                    # Get the items that are unique from the after overwrites
                    changes = after_set.difference(before_set)

                    # Start constructing the messages
                    changes_msg = []
                    for new in changes:
                        old = discord.utils.find(lambda old_set: old_set[0] == new[0], before_set)
                        perm_name = string.capwords(f"{new[0]}".replace('_', ' '))  # Capitalize the permission names and replace underlines with spaces.
                        perm_name = "Send TTS Messages" if perm_name == "Send Tts Messages" else perm_name  # Mak sure that we capitalize the TTS acronym properly.
                        if new[1] is None:
                            perm_status = "Inherit"
                            perm_status_emoji = "<:Inherit:681237607312654345>"
                        else:  # <:greenCircle:681235935911870508>
                            perm_status = "Allow" if new[1] is True else "Deny"
                            perm_status_emoji = "🟢" if new[1] is True else "❌"

                        if old[1] is None:
                            old_perm_status_emoji = "<:Inherit:681237607312654345>"
                        else:
                            old_perm_status_emoji = "🟢" if old[1] is True else "❌"

                        changes_msg.append(f"**{old_perm_status_emoji} ➔ {perm_status_emoji} {perm_name}** is now set to **{perm_status}**")

                    body = "\n".join(changes_msg)
                else:
                    body = f"Permission Overwrites Removed"

                change_msgs.append((header, body))

        if len(change_msgs) > 0:
            for change in change_msgs:
                # embed.add_field(name=change[0], value=change[1], inline=False)
                split_msgs = split_text(change[1], max_size=1000)
                for i, msg in enumerate(split_msgs):
                    header = change[0] if i == 0 else "\N{Zero Width Space}"#f"{change[0]} Cont."
                    embed.add_field(name=header, value=msg, inline=False)
        return embed


def setup(bot):
    bot.add_cog(ChannelEvents(bot))
