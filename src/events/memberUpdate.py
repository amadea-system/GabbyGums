"""
Cog for the on_member_update event.
Logs from this event include:
    Nickname changes in a guild (guild_member_nickname)

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

from embeds import member_nick_update

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class MemberUpdate(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handles the 'on Member Update' event."""
        event_type_nick = "guild_member_nickname"  # nickname
        event_type_update = "guild_member_update"  # Everything else. Currently unused.

        if before.nick != after.nick:

            log_channel = await self.bot.get_event_or_guild_logging_channel(after.guild.id, event_type_nick)
            if log_channel is None:
                # Silently fail if no log channel is configured.
                return

            embed = member_nick_update(before, after)
            await log_channel.send(embed=embed)


    @commands.command()
    async def hello(self, ctx, *, member: discord.Member = None):
        """Says hello"""
        member = member or ctx.author
        await ctx.send('Hello {0.name}~'.format(member))


def setup(bot):
    bot.add_cog(MemberUpdate(bot))
