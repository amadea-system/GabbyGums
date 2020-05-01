"""
Cog for the on_member_join and on_member_leave events.
Logs from these event include:
    When a user joins
    When a user leaves
    When a user is part of a PK system that has been banned

Part of the Gabby Gums Discord Logger.
"""


import asyncio
import logging

from datetime import timedelta, datetime
from typing import TYPE_CHECKING, Optional, Dict, List, Union

import discord
from discord.ext import commands

import db
from embeds import member_join, member_leave, member_kick
from miscUtils import send_long_msg, get_audit_logs, MissingAuditLogPermissions, log_error_msg
from utils.pluralKit import get_pk_system_from_userid, CouldNotConnectToPKAPI, UnknownPKError

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class MemberJoinLeave(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):

        await self.bot.wait_until_ready()  # I really don't think this is necessary, but why not.
        await asyncio.sleep(1)
        logging.info("Refreshing Invite Cache.")
        for guild in self.bot.guilds:
            await self.update_invite_cache(guild)
        logging.info("Invite Cache Ready.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        event_type = "member_join"
        try:
            pk_response = await get_pk_system_from_userid(member.id)
        except CouldNotConnectToPKAPI:
            pk_response = None  # add warning message to embed or maybe retry later?
        except UnknownPKError as e:
            await log_error_msg(self.bot, e)
            pk_response = None

        await self.handle_member_join(member, pk_response)
        await self.check_if_pk_banned(member, pk_response)

    # --- General Member Join --- #
    async def handle_member_join(self, member: discord.Member, pk_response: Optional[Dict]):
        event_type = "member_join"

        if member.guild.me.guild_permissions.manage_guild:
            invite_used = await self.find_used_invite(member)
            if invite_used is not None:
                logging.info(
                    "New user joined with link {} that has {} uses.".format(invite_used.invite_id, invite_used.uses))
            embed = member_join(member, invite_used, pk_response)
        else:
            embed = member_join(member, None, pk_response, manage_guild=False)

        log_channel = await self.bot.get_event_or_guild_logging_channel(member.guild.id, event_type)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            return

        await self.bot.send_log(log_channel, event_type, embed=embed)

    # --- PK Ban Checking --- #
    async def check_if_pk_banned(self, member: discord.Member, pk_response: Optional[Dict]):
        event_type = "member_join"

        if await db.any_banned_systems(self.bot.db_pool,
                                       member.guild.id):  # Make sure that we actually have any banned systems to match against before we hit the PK API.

            system_id = pk_response['id'] if pk_response is not None else None

            if system_id is not None and pk_response is not None:
                banned_users = await db.get_banned_system(self.bot.db_pool, member.guild.id, system_id)
                if len(banned_users) > 0:
                    log_channel = await self.bot.get_event_or_guild_logging_channel(member.guild.id, event_type)
                    if log_channel is None:
                        # Silently fail if no log channel is configured.
                        return
                    embed = self.banned_pk_account_joined_embed(member, pk_response)
                    # await log_channel.send(embed=embed)
                    await self.bot.send_log(log_channel, event_type, embed=embed)

    def banned_pk_account_joined_embed(self, member: discord.Member, system_info: Dict) -> discord.Embed:

        if 'name' in system_info and system_info['name'] is not None:
            desc = "**{}** - System ID: **{}**\n\nLinked to: <@{}> - {}#{}".format(system_info['name'],
                                                                                   system_info['id'], member.id,
                                                                                   member.name, member.discriminator)
            info_value = f"Warning! <@{member.id}> is linked to a Plural Kit system, **{system_info['name']}**, that is banned from this server!\n"

        else:
            desc = "PK System ID: **{}**\n\nLinked to: <@{}> - {}#{}".format(system_info['id'], member.id, member.name,
                                                                             member.discriminator)
            info_value = f"Warning! <@{member.id}> is linked to a Plural Kit system, ID: **{system_info['id']}**, that is banned from this server!\n"

        embed = discord.Embed(description=desc,
                              color=discord.Color.red(), timestamp=datetime.utcnow())

        embed.set_author(name="\N{WARNING SIGN} WARNING! Banned Plural Kit System Joined")

        if "avatar_url" in system_info and system_info["avatar_url"] is not None:
            avatar_url = system_info['avatar_url']
            ios_compatible_avatar_url = avatar_url
            embed.set_thumbnail(url=ios_compatible_avatar_url)

        embed.add_field(name="Info:",
                        value=info_value,
                        inline=False)

        embed.set_footer(text="System ID: {}".format(system_info['id']))

        return embed


    # --- Member Leave --- #
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        event_type_leave = "member_leave"
        event_type_kick = "member_kick"

        leave_log_channel = await self.bot.get_event_or_guild_logging_channel(member.guild.id, event_type_leave)
        kick_log_channel = await self.bot.get_event_or_guild_logging_channel(member.guild.id, event_type_kick)
        if leave_log_channel is None and kick_log_channel is None:
            # Silently fail if no log channel is configured.
            return
        # We have a log channel. Start pulling audit logs and doing stuff

        if kick_log_channel is not None:  # Don't try to see if it's a kick if we shouldn't log kicks
            guild: discord.Guild = member.guild
            try:
                audit_log_entries = await get_audit_logs(guild, discord.AuditLogAction.kick, member, timedelta(seconds=30))
                if len(audit_log_entries) > 0:
                    # Assume the latest entry is the correct entry.
                    # Todo: Maybe Look at the time data and reject if it's too old? Kinda redundent though since we already filter them all out...
                    audit_log = audit_log_entries[0]
                    # reason = f" because: {audit_log.reason}" if audit_log.reason else ". No Reason was given"
                    # logging.info(f"Got Audit log entries")
                    # return
                else:
                    # logging.info(f"No audit log entries present")
                    audit_log = None

            except MissingAuditLogPermissions:
                # log.info(f"{member.name} left.")
                # log.info(f"Gabby Gums needs the View Audit Log permission to display who kicked the member.")
                # logging.info("Need more perms")
                audit_log = None
        else:
            audit_log = None

        if audit_log is not None and kick_log_channel is not None:
            embed = member_kick(member, audit_log)
            # await kick_log_channel.send(embed=embed)
            await self.bot.send_log(kick_log_channel, event_type_kick, embed=embed)
        elif leave_log_channel is not None:
            embed = member_leave(member)
            # await leave_log_channel.send(embed=embed)
            await self.bot.send_log(leave_log_channel, event_type_leave, embed=embed)


    # --- Invite Helper Functions --- #


    async def get_stored_invites(self, guild_id: int) -> db.StoredInvites:
        """Retrieves the stored invites from the DB"""
        stored_invites = await db.get_invites(self.bot.db_pool, guild_id)
        return stored_invites


    async def update_invite_cache(self, guild: discord.Guild, invites: Optional[List[discord.Invite]] = None,
                                  stored_invites: Optional[db.StoredInvites] = None) -> Optional[db.StoredInvites]:
        """
        Pulls all the invites for a guild from Discord, Adds the new ones to the DB and removes the deleted ones from the DB.

        Can optionally accept a list of upto date discord.Invites
            and/or recent potentially stale (From discord POV) StoredInvite obj for API and DB efficiency

        Returns an up to date StoredInvites Object.
        """

        try:
            if not guild.me.guild_permissions.manage_guild:
                return  # We don't have permissions to get any invites from this guild! Bail.

            if invites is None:
                invites: List[discord.Invite] = await guild.invites()

            for invite in invites:
                await db.store_invite(self.bot.db_pool, guild.id, invite.id, invite.uses, invite.max_uses, invite.inviter.id, invite.created_at)

            if stored_invites is None:
                stored_invites = await self.get_stored_invites(guild.id)

            await asyncio.sleep(1)  # Wait a sec before deleting any invites in case an on_invite_delete fired right after this to allow it to grab the invite cache.
            valid_invites = await self.remove_invalid_invites(guild.id, invites, stored_invites)
            return valid_invites

        except discord.Forbidden as e:
            logging.exception("update_invite_cache error: {}".format(e))

            if 'error_log_channel' not in self.bot.config:
                return
            error_log_channel = self.bot.get_channel(self.bot.config['error_log_channel'])
            await error_log_channel.send(e)


    async def remove_invalid_invites(self, guild_id: int, current_invites: List[discord.Invite],
                                     stored_invites: db.StoredInvites) -> db.StoredInvites:
        """
        From a list of upto date Discord Invites, and a potentially stale StoredInvites obj,
        Remove all invalid Invites from the DB and return an up to date StoredInvites Object.
        """

        def search_for_invite(_current_invites: List[discord.Invite], invite_id: str) -> Optional[discord.Invite]:
            for invite in _current_invites:
                if invite.id == invite_id:
                    return invite
            return None

        valid_invites: List[db.StoredInvite] = []
        for stored_invite in stored_invites.invites:
            current_invite = search_for_invite(current_invites, stored_invite.invite_id)
            if current_invite is None:
                await db.remove_invite(self.bot.db_pool, guild_id, stored_invite.invite_id)
            else:
                valid_invites.append(stored_invite)

        stored_invites.invites = valid_invites
        return stored_invites


    async def find_used_invite(self, member: discord.Member) -> Optional[db.StoredInvite]:

        stored_invites: db.StoredInvites = await self.get_stored_invites(member.guild.id)
        current_invites: List[discord.Invite] = await member.guild.invites()

        if member.bot:
            # The member is a bot. An oauth invite was used.
            await self.update_invite_cache(member.guild, invites=current_invites)
            return None

        new_invites: List[discord.Invite] = []  # This is where we will store newly created invites.
        # invite_used: Optional[db.StoredInvite] = None
        for current_invite in current_invites:
            stored_invite = stored_invites.find_invite(current_invite.id)
            if stored_invite is None:
                new_invites.append(current_invite)  # This is a new Invite. store it so we have it in case we need it
            else:
                if current_invite.uses > stored_invite.uses:
                    # We have a matched invite!
                    stored_invite.uses = current_invite.uses  # Correct the count of the stored invite.
                    stored_invite.actual_invite = current_invite
                    await self.update_invite_cache(member.guild, invites=current_invites)
                    return stored_invite  # Todo: FIX! This works, unless we somehow missed the last user join.
                else:
                    pass  # not the used invite. look at the next invite.
        # We scanned through all the current invites and was unable to find a match from the cache. Look through new invites
        log.info("Invite was not found in current_invites")

        for new_invite in new_invites:
            if new_invite.uses > 0:
                # Todo: FIX! This works, unless we somehow missed the last user join.
                invite_used = db.StoredInvite(server_id=new_invite.guild.id, invite_id=new_invite.id,
                                              uses=new_invite.uses, invite_name="New Invite!", actual_invite=new_invite)
                await self.update_invite_cache(member.guild, invites=current_invites)
                return invite_used
        log.info("Invite was not found in new_invites\n searching throuch cache for deleted invites.")

        # At this point, it could be a deleted invite.
        for stored_invite in stored_invites.invites:
            log.info(f"Checking if {stored_invite.invite_id} was the used invite.")
            found_invite = discord.utils.get(current_invites, id=stored_invite.invite_id)
            if found_invite is None:
                log.info(f"{stored_invite.invite_id} IS the used invite.")
                # We have a stored invite that no longer exists according to Discord. THis is probably the invite used.
                stored_invite.uses += 1
                await self.update_invite_cache(member.guild, invites=current_invites)
                return stored_invite

        # Somehow we STILL haven't found the invite that was used... I don't think we should ever get here, unless I forgot something...
        # We should never get here, so log it very verbosly in case we do so I can avoid it in the future.
        current_invite_debug_msg = "invites=["
        for invite in current_invites:
            debug_msg = "Invite(code={code}, uses={uses}, max_uses={max_uses}, max_age={max_age}, revoked={revoked}," \
                        " created_at={created_at}, inviter={inviter}, guild={guild})".format(code=invite.code,
                                                                                             uses=invite.uses,
                                                                                             max_uses=invite.max_uses,
                                                                                             max_age=invite.max_age,
                                                                                             revoked=invite.revoked,
                                                                                             created_at=invite.created_at,
                                                                                             inviter=invite.inviter,
                                                                                             guild=invite.guild)
            current_invite_debug_msg = current_invite_debug_msg + debug_msg
        current_invite_debug_msg = current_invite_debug_msg + "]"

        log_msg = "UNABLE TO DETERMINE INVITE USED.\n Stored invites: {}, Current invites: {} \n" \
                  "Server: {}, Member: {}".format(stored_invites, current_invite_debug_msg, repr(member.guild),
                                                  repr(member))
        logging.info(log_msg)

        try_again_for_current_invites: List[discord.Invite] = await member.guild.invites()

        try_again_invite_debug_msg = "Tryagain-invites=["
        for invite in try_again_for_current_invites:
            debug_msg = "Invite(code={code}, uses={uses}, max_uses={max_uses}, max_age={max_age}, revoked={revoked}," \
                        " created_at={created_at})".format(code=invite.code,
                                                           uses=invite.uses,
                                                           max_uses=invite.max_uses,
                                                           max_age=invite.max_age,
                                                           revoked=invite.revoked,
                                                           created_at=invite.created_at)
            try_again_invite_debug_msg = try_again_invite_debug_msg + debug_msg
            try_again_invite_debug_msg = try_again_invite_debug_msg + "]"

        # Check to see if they are receiving Invite Create/Delete events.
        permissions: discord.Permissions = member.guild.me.guild_permissions
        manage_ch_perm = permissions.manage_channels
        invite_events_msg = "✅ GG is receiving Invite Events." if manage_ch_perm else "❌ GG is **NOT** receiving Invite Events. Invite tracking will not be as accurate."
        if 'error_log_channel' in self.bot.config:
            error_log_channel = self.bot.get_channel(self.bot.config['error_log_channel'])
            await error_log_channel.send(f"UNABLE TO DETERMINE INVITE USED.\n{invite_events_msg}")
            await send_long_msg(error_log_channel, "Stored invites: {}".format(stored_invites), code_block=True)
            await send_long_msg(error_log_channel, "Current invites: {}".format(current_invite_debug_msg), code_block=True)
            await send_long_msg(error_log_channel, "2nd_try Current invites: {}".format(try_again_invite_debug_msg), code_block=True)
            await send_long_msg(error_log_channel, "Server: {}".format(repr(member.guild)), code_block=True)
            await send_long_msg(error_log_channel, "Member who joined: {}".format(repr(member)), code_block=True)

        await self.update_invite_cache(member.guild, invites=current_invites)
        return None


def setup(bot):
    bot.add_cog(MemberJoinLeave(bot))


