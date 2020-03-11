"""
Cog containing various commands for managing invite tracking.
Commands include:


Part of the Gabby Gums Discord Logger.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

import db
import miscUtils

if TYPE_CHECKING:
    from bot import GGBot
    from events.memberJoinLeave import MemberJoinLeave

log = logging.getLogger(__name__)


class InviteManagement(commands.Cog, name="Invite Management"):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    # ----- Invite Commands ----- #


    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.group(name="invites",
                    brief="Allows for naming invites for easier identification and listing details about them.",
                    description="Allows for naming invites for easier identification and listing details about them.",
                    usage='<command>')
    async def invite_manage(self, ctx: commands.Context):
        if not ctx.guild.me.guild_permissions.manage_guild:
            await ctx.send("⚠ Gabby gums needs the **Manage Server** permission for invite tracking.")
            return
        else:
            if ctx.invoked_subcommand is None:
                await ctx.send_help(self.invite_manage)


    @invite_manage.command(name="list", brief="Lists the invites in the server and if they have a defined name.",
                           description="Lists the invites in the server and if they have a defined name.")
    async def _list_invites(self, ctx: commands.Context):
        if ctx.guild.me.guild_permissions.manage_guild:

            invites: 'MemberJoinLeave' = self.bot.get_cog('MemberJoinLeave')
            await invites.update_invite_cache(ctx.guild)  # refresh the invite cache.
            invites: db.StoredInvites = await invites.get_stored_invites(ctx.guild.id)
            embed = discord.Embed(title="Current Invites", color=0x9932CC)

            embed_count = 0
            for invite in invites.invites:
                embed.add_field(name=invite.invite_id,
                                value="Uses: {}\n Nickname: {}".format(invite.uses, invite.invite_name))
                embed_count += 1
                if embed_count == 25:
                    await ctx.send(embed=embed)
                    embed = discord.Embed(title="Current Invites Cont.", color=0x9932CC)

            if embed_count % 25 != 0:
                await ctx.send(embed=embed)


    @invite_manage.command(name="name", brief="Lets you give an invite a nickname so it can be easier to identify.",
                           usage='<Invite ID> <Invite Nickname>')
    async def _name_invite(self, ctx: commands.Context, invite_id: discord.Invite, nickname: str = None):
        bot: GGBot = ctx.bot
        if ctx.guild.me.guild_permissions.manage_guild:
            invites: 'MemberJoinLeave' = self.bot.get_cog('MemberJoinLeave')
            await invites.update_invite_cache(ctx.guild)  # refresh the invite cache.
            await db.update_invite_name(bot.db_pool, ctx.guild.id, invite_id.id, invite_name=nickname)
            await ctx.send("{} has been given the nickname: {}".format(invite_id.id, nickname))


    @invite_manage.command(name="unname", brief="Removes the name from an invite.",
                           usage='<Invite ID>')
    async def _unname_invite(self, ctx: commands.Context, invite_id: discord.Invite):
        bot: GGBot = ctx.bot
        if ctx.guild.me.guild_permissions.manage_guild:
            invites: 'MemberJoinLeave' = self.bot.get_cog('MemberJoinLeave')
            await invites.update_invite_cache(ctx.guild)  # refresh the invite cache.
            await db.update_invite_name(bot.db_pool, ctx.guild.id, invite_id.id)
            await ctx.send("{} no longer has a nickname.".format(invite_id.id))


def setup(bot):
    bot.add_cog(InviteManagement(bot))
