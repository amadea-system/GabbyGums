"""
Cog for the on_user_update event.
Logs from this event include:
    Avatar changes
    Username Changes
    Discriminator Changes

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple

import discord
from discord.ext import commands

from imgUtils.avatarChangedImgProcessor import get_avatar_changed_image
from embeds import user_name_update, user_avatar_update

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class UserUpdate(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

    # For debugging purposes only.
    @commands.is_owner()
    @commands.command(name="pfp")
    async def pfp_test_cmd(self, ctx: commands.Context, after: discord.Member):

        event_type_avatar = "user_avatar_update"
        before: discord.Member = ctx.author
        # noinspection PyTypeChecker
        await self.avatar_changed_update(before, after)

    # For debugging purposes only.
    @commands.is_owner()
    @commands.command(name="pfp-all")
    async def pfp_all_test_cmd(self, ctx: commands.Context, maximum_number: int = 10):
        from random import SystemRandom as sRandom
        random = sRandom()
        members: List[discord.Member] = list(self.bot.get_all_members())
        await ctx.send(f"Generating {maximum_number} avatar changed embeds out of {len(members)} total members.")
        some_members = random.choices(members, k=maximum_number)
        for member in some_members:
            # noinspection PyTypeChecker
            await self.avatar_changed_update(member, member)
        await ctx.send(f"Done sending test embeds.")


    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        # username, Discriminator

        if before.avatar != after.avatar:
            # Get a list of guilds the user is currently in.
            await self.avatar_changed_update(before, after)

        if before.name != after.name or before.discriminator != after.discriminator:
            await self.username_changed_update(before, after)


    async def username_changed_update(self, before: discord.User, after: discord.User):
        event_type_name = "username_change"
        # Username and/or discriminator changed
        embed = user_name_update(before, after)

        guilds = [guild for guild in self.bot.guilds if before in guild.members]
        if len(guilds) > 0:
            for guild in guilds:
                log_channel = await self.bot.get_event_or_guild_logging_channel(guild.id, event_type_name, after.id)
                if log_channel is not None:
                    # await log_channel.send(embed=embed)
                    await self.bot.send_log(log_channel, event_type_name, embed=embed)


    async def avatar_changed_update(self, before: discord.User, after: discord.User):
        """Sends the appropriate logs on a User Avatar Changed Event"""
        event_type_avatar = "member_avatar_change"

        guilds = [guild for guild in self.bot.guilds if before in guild.members]
        if len(guilds) > 0:
            # get the pfp changed embed image and convert it to a discord.File
            avatar_changed_file_name = "avatarChanged.png"

            avatar_info = {"before name": before.name, "before id": before.id,
                           "before pfp": before.avatar_url_as(format="png"),
                           "after name": after.name, "after id": after.id,
                           "after pfp": after.avatar_url_as(format="png")
                           }  # For Debugging

            with await get_avatar_changed_image(self.bot, before, after, avatar_info) as avatar_changed_bytes:
                # create the embed
                embed = user_avatar_update(before, after, avatar_changed_file_name)

                # loop through all the guilds the member is in and send the embed and image
                for guild in guilds:
                    log_channel = await self.bot.get_event_or_guild_logging_channel(guild.id, event_type_avatar, after.id)
                    if log_channel is not None:
                        # The File Object needs to be recreated for every post, and the buffer needs to be rewound to the beginning
                        # TODO: Handle case where avatar_changed_bytes could be None.
                        avatar_changed_bytes.seek(0)
                        avatar_changed_img = discord.File(filename=avatar_changed_file_name, fp=avatar_changed_bytes)
                        # Send the embed and file
                        # await log_channel.send(file=avatar_changed_img, embed=embed)
                        await self.bot.send_log(log_channel, event_type_avatar, embed=embed, file=avatar_changed_img)


def setup(bot):
    bot.add_cog(UserUpdate(bot))