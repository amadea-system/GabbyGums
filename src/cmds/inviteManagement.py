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

import eCommands
import db

from embeds import command_timed_out_embed, command_canceled_embed
from utils.moreColors import gabby_gums_dark_green
from uiElements import BoolPage

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
    @eCommands.group(name="invites",
                     brief="Allows for naming invites for easier identification and listing details about them.",
                     description="Allows for naming invites for easier identification and listing details about them.")
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
            current_invites: db.StoredInvites = await invites.update_invite_cache(ctx.guild)  # refresh the invite cache.

            embed_count = 0
            if len(current_invites.invites) > 0:
                embed = discord.Embed(title="Current Invites", color=gabby_gums_dark_green())

                for invite in current_invites.invites:
                    embed.add_field(name=invite.invite_id,
                                    value="Uses: {}\n Nickname: {}".format(invite.uses, invite.invite_name))
                    embed_count += 1
                    if embed_count == 25:
                        await ctx.send(embed=embed)
                        embed = discord.Embed(title="Current Invites Cont.", color=gabby_gums_dark_green())

                if embed_count % 25 != 0:
                    await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="Current Invites",
                                      description="This server does not currently have any invites.",
                                      color=gabby_gums_dark_green())
                await ctx.send(embed=embed)


    @invite_manage.command(name="create", brief="Lets you create a new invite with a nickname.",
                           usage='<Channel ID> <Invite Nickname>',
                           examples=["#welcome Gabby Gums Github Page", "123456789123456789 Awesome Server Hub!"])
    async def _create_invite(self, ctx: commands.Context,
                             input_channel: Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel],
                             *, nickname: str = None):
        bot: GGBot = ctx.bot

        if ctx.guild.me.guild_permissions.manage_guild:

            ch_perm: discord.Permissions = ctx.guild.me.permissions_in(input_channel)
            if not ch_perm.create_instant_invite:
                await ctx.send("⚠ Gabby gums needs the **Create Invite** permission to create invites.\n"
                               "(It requires this permission globally AND for the channel the invite is being created for)")
                return

            # create the new invite.
            new_invite = await input_channel.create_invite(unique=True, reason=f"Invite created at the request of {ctx.author.display_name}.")

            # Store the invite (It's probable this will result in duplicate store invite calls. but that's okay)
            await db.store_invite(self.bot.db_pool, ctx.guild.id, new_invite.id, new_invite.uses, new_invite.max_uses, new_invite.inviter.id, new_invite.created_at)

            # Name the invite.
            await db.update_invite_name(bot.db_pool, ctx.guild.id, new_invite.id, invite_name=nickname)

            # success_embed = discord.Embed(title="New Invite Created And Named",
            #                               description=f"✅ \n"
            #                                           f"A new invite with the URL **{new_invite.url}** has been created.\n"
            #                                           f"It has been given the nickname: **{nickname}**",
            #                               color=gabby_gums_dark_green())

            success_embed = discord.Embed(title="New Invite Created And Named",
                                          description=f"✅\n"
                                                      f"A new invite for <#{input_channel.id}> has been created.\n"
                                                      f"It has been given the nickname: **{nickname}**",
                                          color=gabby_gums_dark_green())

            await ctx.send(f"Invite Link: <{new_invite.url}>", embed=success_embed)


    @invite_manage.command(name="name", brief="Lets you give an invite a nickname so it can be easier to identify.",
                           usage='<Invite ID> <Invite Nickname>',
                           examples=["Xwhk89T Gabby Gums Github Page"])
    async def _name_invite(self, ctx: commands.Context, invite: discord.Invite, *, nickname: str = None):
        bot: GGBot = ctx.bot
        if ctx.guild.me.guild_permissions.manage_guild:
            invites_cog: 'MemberJoinLeave' = self.bot.get_cog('MemberJoinLeave')
            current_invites = await invites_cog.update_invite_cache(ctx.guild)  # refresh the invite cache and get StoredInvites obj.

            if current_invites is not None:
                invite_to_name = current_invites.find_invite(invite.id)
                if invite_to_name is not None and invite_to_name.invite_name is not None:

                    conf_embed = discord.Embed(title="Invite already named!",
                                               description=f"The invite **{invite.id}** already has a name of **{invite_to_name.invite_name}**!\n"
                                                           f"Do you wish to rename it to **{nickname}**?",
                                               color=gabby_gums_dark_green())

                    conf_page = BoolPage(embed=conf_embed)

                    confirmation = await conf_page.run(ctx)
                    if confirmation is None:
                        await ctx.send(embed=command_timed_out_embed(f"Invite **{invite.id}** has not been renamed."))
                        return

                    elif confirmation is False:
                        await ctx.send(embed=command_canceled_embed(f"Invite **{invite.id}** has not been renamed."))
                        return
                    # Otherwise fall through and preform the rename

            await db.update_invite_name(bot.db_pool, ctx.guild.id, invite.id, invite_name=nickname)

            success_embed = discord.Embed(title="Invite Named",
                                          description=f"✅ **{invite.id}** has been given the nickname: **{nickname}**",
                                          color=gabby_gums_dark_green())

            await ctx.send(embed=success_embed)


    @invite_manage.command(name="unname", brief="Removes the name from an invite.",
                           usage='<Invite ID>')
    async def _unname_invite(self, ctx: commands.Context, input_invite: discord.Invite):
        bot: GGBot = ctx.bot
        if ctx.guild.me.guild_permissions.manage_guild:
            invites: 'MemberJoinLeave' = self.bot.get_cog('MemberJoinLeave')
            await invites.update_invite_cache(ctx.guild)  # refresh the invite cache.
            await db.update_invite_name(bot.db_pool, ctx.guild.id, input_invite.id)

            success_embed = discord.Embed(title="Invite Name Removed",
                                          description=f"✅ **{input_invite.id}** no longer has a nickname",
                                          color=gabby_gums_dark_green())

            await ctx.send(embed=success_embed)


def setup(bot):
    bot.add_cog(InviteManagement(bot))
