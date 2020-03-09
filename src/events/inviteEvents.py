"""
Cog for the on_member_update event.
Logs from this event include:
    Nickname changes in a guild (guild_member_nickname)

Part of the Gabby Gums Discord Logger.
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

import db

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class InviteEvent(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Handles the 'on_invite_create' event."""
        event_type = "invite_create"

        await db.store_invite(self.bot.db_pool, invite.guild.id, invite.id, invite.uses, invite.max_uses, invite.inviter.id, invite.created_at)  # Store the new invite in the DB.

        log_channel = await self.bot.get_event_or_guild_logging_channel(invite.guild.id, event_type)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            return

        embed = self.invite_created_embed(invite)
        await self.bot.send_log(log_channel, event_type, embed=embed)

    @staticmethod
    def invite_created_embed(invite: discord.Invite) -> discord.Embed:

        embed = discord.Embed(title="New Invite Created",
                              # description="<@{}> - {}#{}".format(member.id, member.name, member.discriminator),
                              color=discord.Color.gold(), timestamp=datetime.utcnow())
        #
        # embed.set_author(name="Member Left 😭",
        #                  icon_url="https://www.emoji.co.uk/files/mozilla-emojis/objects-mozilla/11928-outbox-tray.png")

        # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
        inviter: discord.Member = invite.inviter
        embed.add_field(name="Created By",
                        value="<@{}> - {}#{}".format(inviter.id, inviter.name, inviter.discriminator),
                        inline=True)
        embed.add_field(name="Code", value=f"{invite.id}")
        embed.add_field(name="For Channel", value=f"<#{invite.channel.id}>")
        if invite.max_uses == 0:
            embed.add_field(name="Max Uses", value=f"Infinite")
        else:
            embed.add_field(name="Max Uses", value=f"{invite.max_uses}")

        if invite.max_age == 0:
            embed.add_field(name="Expires", value="Never")
        elif invite.max_age < 3600:  # Minutes
            embed.add_field(name="Expires in", value=f"{invite.max_age/60:.0f} Minutes")
        else:  # Hours
            embed.add_field(name="Expires in", value=f"{invite.max_age / 60 / 60:.0f} Hours")

        if invite.temporary:
            embed.add_field(name="Temporary Invite", value=f"Yes")

        embed.set_footer(text="\N{Zero Width Space}")
        return embed


    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Handles the 'on_invite_delete' event."""
        event_type = "invite_delete"

        # get the invite from the DB.
        stored_invites: db.StoredInvites = await db.get_invites(self.bot.db_pool, invite.guild.id)
        cached_invite = stored_invites.find_invite(invite.id)

        log_channel = await self.bot.get_event_or_guild_logging_channel(invite.guild.id, event_type)
        if log_channel is not None:

            embed = self.invite_deleted_embed(invite, cached_invite)
            await self.bot.send_log(log_channel, event_type, embed=embed)

        # wait a bit before deleting the invite from the DB to allow for invite tracking.
        await asyncio.sleep(5)
        await db.remove_invite(self.bot.db_pool, invite.guild.id, invite.id)  # Could conflict with removing in member join.
        log.info(f"invite {invite.id} Removed from DB")

    @staticmethod
    def invite_deleted_embed(invite: discord.Invite, cached_invite: Optional[db.StoredInvite]) -> discord.Embed:

        embed = discord.Embed(title="Invite Deleted",
                              # description="<@{}> - {}#{}".format(member.id, member.name, member.discriminator),
                              color=discord.Color.dark_gold(), timestamp=datetime.utcnow())
        #
        # embed.set_author(name="Member Left 😭",
        #                  icon_url="https://www.emoji.co.uk/files/mozilla-emojis/objects-mozilla/11928-outbox-tray.png")

        # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)

        embed.add_field(name="Code", value=f"{invite.id}")
        if invite.channel is not None:
            embed.add_field(name="For Channel", value=f"<#{invite.channel.id}>")

        if cached_invite is not None:
            if cached_invite.invite_name is not None:
                embed.add_field(name="Invite Name", value=cached_invite.invite_name)
            embed.add_field(name="Recorded Number Of Uses", value=f"{cached_invite.uses}")

            if cached_invite.max_uses is not None:
                if cached_invite.max_uses == 0:
                    embed.add_field(name="Max Uses", value=f"Infinite")
                else:
                    embed.add_field(name="Max Uses", value=f"{cached_invite.max_uses}")

            if cached_invite.inviter_id is not None:
                embed.add_field(name="Created By", value=f"<@{cached_invite.inviter_id}>")

            if cached_invite.created_ts is not None:
                embed.add_field(name="Created on", value=cached_invite.created_at().strftime("%b %d, %Y, %I:%M:%S %p UTC"))

        # embed.set_footer(text="Created by User ID: {}".format(member.id))
        embed.set_footer(text="\N{Zero Width Space}")
        return embed


def setup(bot):
    bot.add_cog(InviteEvent(bot))
