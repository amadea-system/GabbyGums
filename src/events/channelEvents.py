"""
Cog for the on_guild_channel_create, on_guild_channel_delete, and on_guild_channel_updateevent.
Logs from these event include:
    Nickname changes in a guild (guild_member_nickname)

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class ChannelEvents(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel,):
        """Handles the 'on on_guild_channel_create' event."""
        event_type = "channel_create"

        if isinstance(channel, discord.TextChannel):
            log.info(f"New Text channel created! {channel.name} in {channel.category}, Pos: {channel.position}")
        elif isinstance(channel, discord.VoiceChannel):
            log.info(f"New Voice channel created! {channel.name} in {channel.category}, Pos: {channel.position}")
        if isinstance(channel, discord.CategoryChannel):
            log.info(f"New Categoty created! {channel.name}, Pos: {channel.position}")


    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel, ):
        """Handles the 'on on_guild_channel_delete' event."""
        event_type = "channel_delete"

        if isinstance(channel, discord.TextChannel):
            log.info(f"Text channel deleted! {channel.name} in {channel.category}, Pos: {channel.position}")
        elif isinstance(channel, discord.VoiceChannel):
            log.info(f"Voice channel deleted! {channel.name} in {channel.category}, Pos: {channel.position}")
        if isinstance(channel, discord.CategoryChannel):
            log.info(f"Categoty deleted! {channel.name}, Pos: {channel.position}")


    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Handles the 'on on_guild_channel_update' event."""
        event_type = "channel_update"
        if before.position == after.position:  # Filter out position change spam
            log_ch = await self.bot.get_event_or_guild_logging_channel(before.guild.id)

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
                              description=f"Update info for: <#{after.id}>")
        now = "Now: \N{zero width space} \N{zero width space}  \N{zero width space} "

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{now}{after.name}\nBefore: {before.name}")

        if before.category != after.category:

            embed.add_field(name="Category Changed",
                            value=f"{now}{after.category}\nBefore: {before.category}")

        if before.topic != after.topic:
            embed.add_field(name="Topic Changed:", value=f"{now}{after.topic}\nBefore: {before.topic}")

        if before.slowmode_delay != after.slowmode_delay:
            before_delay = f"{before.slowmode_delay} Sec" if before.slowmode_delay > 0 else "Disabled"
            after_delay = f"{after.slowmode_delay} Sec" if after.slowmode_delay > 0 else "Disabled"
            embed.add_field(name="Slowmode Delay Changed:", value=f"{now}{after_delay}\nBefore: {before_delay}")

        if before.is_nsfw() != after.is_nsfw():
            before_nsfw = "Yes" if before.is_nsfw() else "No"
            after_nsfw = "Yes" if after.is_nsfw() else "No"
            embed.add_field(name="NSFW Status Changed:", value=f"{now}{after_nsfw}\nBefore: {before_nsfw}")

        # if before.changed_roles != after.changed_roles:
        #     embed.add_field(name="changed_roles Changed:", value=f"{now}{after.changed_roles}\nBefore: {before.changed_roles}")
        #
        # if before.overwrites != after.overwrites:
        #     changes = []
        #
            # embed.add_field(name="overwrites Changed:", value=f"{now}{after.overwrites}\nBefore: {before.overwrites}")
        #
        # if before.name != after.name:
        #     embed.add_field(name="Name Changed:", value=f"{now}{after.name}\nBefore: {before.name}")

        return embed if len(embed.fields) > 0 else None


    def determine_changed_overrides(self, embed, before, after):
        change_msgs = []
        for key, before_overwrites in before.overwrites.items():
            after_overwrites = after.overwrites[key] if key in after.overwrites else None
            if before_overwrites != after_overwrites:
                log.info(f"{key.name}: are NOT equal")
                _type = f"Role" if isinstance(key, discord.Role) else f"Member"
                header = f"{_type} Permission Overwrites for {key.name}:\n"
                if after_overwrites is not None:
                    after_set = set(after_overwrites)
                    before_set = set(before_overwrites)

                    # Get the items that are unique from the after overwrites
                    changes = after_set.difference(before_set)
                    changes_msg = []
                    for i in changes:
                        perm_name = string.capwords(f"{i[0]}".replace('_', ' '))
                        if i[1] is None:
                            perm_status = "Inherit"
                        else:
                            perm_status = "Allow" if i[1] is True else "Deny"

                        changes_msg.append(f"**{perm_name}** is now set to **{perm_status}**")

                    body = "\n".join(changes_msg)
                else:
                    body = f"Permission Overwrites Removed"

                change_msgs.append((header, body))
                logging.warning(header + body)

        if len(change_msgs) > 0:
            embed.add_field(name="__Channel Permission Overrides Changed:__", value=f"\N{zero width space}",
                            inline=False)
            for change in change_msgs:
                embed.add_field(name=change[0], value=change[1], inline=False)
        return embed



    def get_voice_ch_update_embed(self, before: discord.VoiceChannel, after: discord.VoiceChannel):
        log.info(f"Voice channel Updated! {after.name} in {after.category}, Pos: {after.position}")
        embed = discord.Embed(title="Voice Channel Updated",
                              description=f"Update info for: <#{after.id}>")
        now = "Now: \N{zero width space} \N{zero width space}  \N{zero width space} "

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{now}{after.name}\nBefore: {before.name}")

        if before.category != after.category:
            embed.add_field(name="Category Changed",
                            value=f"{now}{after.category}\nBefore: {before.category}")

        if before.bitrate != after.bitrate:
            embed.add_field(name="Audio Bitrate Changed:", value=f"{now}{after.bitrate//1000} kbps\nBefore: {before.bitrate//1000} kbps")

        if before.user_limit != after.user_limit:
            # before_delay = f"{before.slowmode_delay} Sec" if before.slowmode_delay > 0 else "Disabled"
            # after_delay = f"{after.slowmode_delay} Sec" if after.slowmode_delay > 0 else "Disabled"
            embed.add_field(name="User Limit Changed:", value=f"{now}{after.user_limit}\nBefore: {before.user_limit}")


        # if before.changed_roles != after.changed_roles:
        #     embed.add_field(name="changed_roles Changed:", value=f"{now}{after.changed_roles}\nBefore: {before.changed_roles}")
        #
        # if before.overwrites != after.overwrites:
        #     changes = []
        #
        # embed.add_field(name="overwrites Changed:", value=f"{now}{after.overwrites}\nBefore: {before.overwrites}")

        return embed if len(embed.fields) > 0 else None


    def get_categoty_ch_update_embed(self, before: discord.CategoryChannel, after: discord.CategoryChannel):
        log.info(f"Category Updated! {after.name}, Pos: {after.position}")
        embed = discord.Embed(title="Category Updated",
                              description=f"Update info for: <#{after.id}>")
        now = "Now: \N{zero width space} \N{zero width space}  \N{zero width space} "

        if before.name != after.name:
            embed.add_field(name="Name Changed:",
                            value=f"{now}{after.name}\nBefore: {before.name}")

        if before.is_nsfw() != after.is_nsfw():
            before_nsfw = "Yes" if before.is_nsfw() else "No"
            after_nsfw = "Yes" if after.is_nsfw() else "No"
            embed.add_field(name="NSFW Status Changed:", value=f"{now}{after_nsfw}\nBefore: {before_nsfw}")

        # if before.changed_roles != after.changed_roles:
        #     embed.add_field(name="changed_roles Changed:", value=f"{now}{after.changed_roles}\nBefore: {before.changed_roles}")
        #
        # if before.overwrites != after.overwrites:
        #     changes = []
        #
        # embed.add_field(name="overwrites Changed:", value=f"{now}{after.overwrites}\nBefore: {before.overwrites}")

        return embed if len(embed.fields) > 0 else None


def setup(bot):
    bot.add_cog(ChannelEvents(bot))
