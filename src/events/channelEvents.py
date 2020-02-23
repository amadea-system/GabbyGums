"""
Cog for the on_guild_channel_create, on_guild_channel_delete, and on_guild_channel_updateevent.
Logs from these event include:
    Nickname changes in a guild (guild_member_nickname)

Part of the Gabby Gums Discord Logger.
"""

import string
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)

# Formatting for now and before text in embeds.
now_txt = "Now:\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{NO-BREAK SPACE}\N{PUNCTUATION SPACE}\N{HAIR SPACE}"
before_txt = "Before:\N{NO-BREAK SPACE}\N{SIX-PER-EM SPACE}"


class ChannelEvents(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Handles the 'on on_guild_channel_create' event."""
        event_type = "channel_create"
        log_ch = await self.bot.get_event_or_guild_logging_channel(channel.guild.id, event_type)
        if log_ch is not None:

            embed = self.get_channel_create_embed(channel)
            await log_ch.send(embed=embed)


    def get_channel_create_embed(self, channel: discord.abc.GuildChannel) -> discord.Embed:

        _type = description = field_value = None  # Keep MyPy happy
        if isinstance(channel, discord.TextChannel):
            log.info(f"New Text channel created! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Text Channel"
            if channel.category is not None:
                description = f"A new text channel was created in {channel.category}."
            else:
                description = f"A new text channel was created."
            field_value = f"<#{channel.id}>\n(#{channel.name})"
        elif isinstance(channel, discord.VoiceChannel):
            log.info(f"New Voice channel created! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Voice Channel"
            if channel.category is not None:
                description = f"A new voice channel was created in {channel.category}."
            else:
                description = f"A new voice channel was created."
            field_value = f"#{channel.name}\n(ID: {channel.id})"
        if isinstance(channel, discord.CategoryChannel):
            log.info(f"New Category created! {channel.name}, Pos: {channel.position}")
            _type = "Category"
            description = f"A new category was created."
            field_value = f"#{channel.name}\n(ID: {channel.id})"

        embed = discord.Embed(title=f"{_type} Created",
                              description=description,
                              timestamp=datetime.utcnow(), color=discord.Color.blue())

        embed.set_footer(text="\N{ZERO WIDTH SPACE}")
        embed.add_field(name=f"New {_type}:", value=field_value)
        return embed


    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel, ):
        """Handles the 'on on_guild_channel_delete' event."""
        event_type = "channel_delete"

        log.info(f"{event_type} fired!")

        log_ch = await self.bot.get_event_or_guild_logging_channel(channel.guild.id, event_type)
        if log_ch is not None:
            embed = self.get_channel_delete_embed(channel)
            await log_ch.send(embed=embed)


    def get_channel_delete_embed(self, channel: discord.abc.GuildChannel) -> discord.Embed:

        _type = description = None  # Keep MyPy happy
        if isinstance(channel, discord.TextChannel):
            log.info(f"Text channel deleted! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Text Channel"
            if channel.category is not None:
                description = f"A text channel was deleted from {channel.category}."
            else:
                description = f"A text channel was deleted."
        elif isinstance(channel, discord.VoiceChannel):
            log.info(f"Voice channel deleted! {channel.name} in {channel.category}, Pos: {channel.position}")
            _type = "Voice Channel"
            if channel.category is not None:
                description = f"A voice channel was deleted from {channel.category}."
            else:
                description = f"A voice channel was deleted."
        if isinstance(channel, discord.CategoryChannel):
            log.info(f"Category deleted! {channel.name}, Pos: {channel.position}")
            _type = "Category"
            description = f"A category was deleted."

        embed = discord.Embed(title=f"{_type} Deleted",
                              description=description,
                              timestamp=datetime.utcnow(), color=discord.Color.dark_blue())
        embed.set_footer(text="\N{ZERO WIDTH SPACE}")

        embed.add_field(name=f"Deleted {_type}", value=f"#{channel.name}\n(ID: {channel.id})")
        return embed


    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Handles the 'on on_guild_channel_update' event."""
        event_type = "channel_update"

        # log.info(f"{event_type} fired!")
        if before.position == after.position:  # Filter out position change spam
            log_ch = await self.bot.get_event_or_guild_logging_channel(before.guild.id, event_type)

            if log_ch is not None:
                if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
                    embed = self.get_text_ch_update_embed(before, after)
                    if embed is not None:
                        await log_ch.send(embed=embed)

                elif isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
                    embed = self.get_voice_ch_update_embed(before, after)
                    if embed is not None:
                        await log_ch.send(embed=embed)

                if isinstance(before, discord.CategoryChannel) and isinstance(after, discord.CategoryChannel):
                    embed = self.get_categoty_ch_update_embed(before, after)
                    if embed is not None:
                        await log_ch.send(embed=embed)


    def get_text_ch_update_embed(self, before: discord.TextChannel, after: discord.TextChannel):
        log.info(f"Text channel Updated! {after.name} in {after.category}, Pos: {after.position}")
        embed = discord.Embed(title="Text Channel Updated",
                              description=f"Update info for: <#{after.id}>",
                              timestamp=datetime.utcnow(), color=discord.Color.blurple())

        embed.set_footer(text=f"Channel ID: {after.id}")
        # now = "Now: \N{zero width space} \N{zero width space}  \N{zero width space} "
        # bef = "Before: "

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{now_txt}**{after.name}**\n{before_txt}**{before.name}**")

        if before.category != after.category:
            embed.add_field(name="Category Changed",
                            value=f"{now_txt}**{after.category}**\n{before_txt}**{before.category}**")

        if before.topic != after.topic:
            if before.topic is None and after.topic == "":
                pass
                # log.info("Avoided "" None topic bug.")
            else:
                embed.add_field(name="Topic Changed:", value=f"{now_txt}**{after.topic}**\n{before_txt}**{before.topic}**")

        if before.slowmode_delay != after.slowmode_delay:
            before_delay = f"{before.slowmode_delay} Sec" if before.slowmode_delay > 0 else "Disabled"
            after_delay = f"{after.slowmode_delay} Sec" if after.slowmode_delay > 0 else "Disabled"
            embed.add_field(name="Slowmode Delay Changed:", value=f"{now_txt}**{after_delay}**\n{before_txt}**{before_delay}**")

        if before.is_nsfw() != after.is_nsfw():
            before_nsfw = "Yes" if before.is_nsfw() else "No"
            after_nsfw = "Yes" if after.is_nsfw() else "No"
            embed.add_field(name="NSFW Status Changed:", value=f"{now_txt}**{after_nsfw}**\n{before_txt}**{before_nsfw}**")

        # if before.changed_roles != after.changed_roles:
        #     embed.add_field(name="changed_roles Changed:", value=f"{now_txt}{after.changed_roles}\n{before_txt}{before.changed_roles}")
        #
        if before.overwrites != after.overwrites:
            embed = self.determine_changed_overrides(embed, before, after)

            # embed.add_field(name="overwrites Changed:", value=f"{now_txt}{after.overwrites}\n{before_txt}{before.overwrites}")


        return embed if len(embed.fields) > 0 else None


    def get_voice_ch_update_embed(self, before: discord.VoiceChannel, after: discord.VoiceChannel):
        log.info(f"Voice channel Updated! {after.name} in {after.category}, Pos: {after.position}")
        embed = discord.Embed(title="Voice Channel Updated",
                              description=f"Update info for: <#{after.id}>",
                              timestamp=datetime.utcnow(), color=discord.Color.blurple())

        embed.set_footer(text=f"Channel ID: {after.id}")

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{now_txt}**{after.name}**\n{before_txt}**{before.name}**")

        if before.category != after.category:
            embed.add_field(name="Category Changed",
                            value=f"{now_txt}**{after.category}**\n{before_txt}**{before.category}**")

        if before.bitrate != after.bitrate:
            embed.add_field(name="Audio Bitrate Changed:", value=f"{now_txt}**{after.bitrate//1000} kbps**\n{before_txt}**{before.bitrate//1000} kbps**")

        if before.user_limit != after.user_limit:
            embed.add_field(name="User Limit Changed:", value=f"{now_txt}**{after.user_limit}**\n{before_txt}**{before.user_limit}**")

        if before.overwrites != after.overwrites:
            embed = self.determine_changed_overrides(embed, before, after)

        return embed if len(embed.fields) > 0 else None


    def get_categoty_ch_update_embed(self, before: discord.CategoryChannel, after: discord.CategoryChannel):
        log.info(f"Category Updated! {after.name}, Pos: {after.position}")
        embed = discord.Embed(title="Category Updated",
                              description=f"Update info for: <#{after.id}>",
                              timestamp=datetime.utcnow(), color=discord.Color.blurple())

        embed.set_footer(text=f"Category ID: {after.id}")

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{now_txt}**{after.name}**\n{before_txt}**{before.name}**")

        if before.is_nsfw() != after.is_nsfw():
            before_nsfw = "Yes" if before.is_nsfw() else "No"
            after_nsfw = "Yes" if after.is_nsfw() else "No"
            embed.add_field(name="NSFW Status Changed:", value=f"{now_txt}**{after_nsfw}**\n{before_txt}**{before_nsfw}**")

        if before.overwrites != after.overwrites:
            embed = self.determine_changed_overrides(embed, before, after)

        return embed if len(embed.fields) > 0 else None


    def determine_changed_overrides(self, embed, before, after):
        change_msgs = []
        for key, before_overwrites in before.overwrites.items():  # Iterate through the before overwrites
            after_overwrites = after.overwrites[key] if key in after.overwrites else None  # Get the corresponding new overwrite.
            if before_overwrites != after_overwrites:  # If they have changed
                log.info(f"{key.name}: are NOT equal")
                _type = f"Role" if isinstance(key, discord.Role) else f"Member"  # Record if it's a role or member having the permissions changed.
                header = f"{_type} Permission Overwrites for {key.name}:\n"  # Write out the appropriate embed header.
                if after_overwrites is not None:
                    after_set = set(after_overwrites)
                    before_set = set(before_overwrites)

                    # Get the items that are unique from the after overwrites
                    changes = after_set.difference(before_set)

                    # Start constructing the messages
                    changes_msg = []
                    for i in changes:
                        perm_name = string.capwords(f"{i[0]}".replace('_', ' '))  # Capitalize the permission names and replace underlines with spaces.
                        perm_name = "Send TTS Messages" if perm_name == "Send Tts Messages" else perm_name  # Mak sure that we capitalize the TTS acronym properly.
                        if i[1] is None:
                            perm_status = "Inherit"
                            perm_status_emoji = "<:Inherit:681237607312654345>"
                        else:  # <:greenCircle:681235935911870508>
                            perm_status = "Allow" if i[1] is True else "Deny"
                            perm_status_emoji = "🟢" if i[1] is True else "❌"

                        changes_msg.append(f"**{perm_status_emoji} {perm_name}** is now set to **{perm_status}**")

                    body = "\n".join(changes_msg)
                else:
                    body = f"Permission Overwrites Removed"

                change_msgs.append((header, body))
                logging.warning(header + body)


        if len(change_msgs) > 0:
            # embed.add_field(name="__Channel Permission Overrides Changed:__", value=f"\N{zero width space}",
            #                 inline=False)
            for change in change_msgs:
                embed.add_field(name=change[0], value=change[1], inline=False)
        return embed



def setup(bot):
    bot.add_cog(ChannelEvents(bot))
