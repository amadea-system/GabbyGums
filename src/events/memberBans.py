"""
Cog for the on_member_ban and on_member_unban events.
Logs from these event include:
    When a user is banned
    When a user is unbanned

Part of the Gabby Gums Discord Logger.
"""

import asyncio
import logging

from datetime import timedelta, datetime
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands

import aiohttp

from embeds import member_nick_update, member_ban, member_unban
from utils import get_audit_logs, MissingAuditLogPermissions
import db

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class NotFound404(Exception):
    pass


class CouldNotConnectToPKAPI(Exception):
    pass


async def get_pk_system_from_userid(user_id: int) -> Optional[Dict]:

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.pluralkit.me/v1/a/{user_id}') as r:
                if r.status == 200:  # We received a valid response from the PK API.
                    logging.info(f"User has an associated PK Account linked to thier Discord Account.")

                    # Convert the JSON response to a dict
                    pk_response = await r.json()

                    # Unpack and return.
                    logging.info(f"Got system: {pk_response}")
                    # system_id = pk_response['id']
                    # return system_id
                    return pk_response
                elif r.status == 404:
                    # No PK Account found.
                    log.info("No PK Account found.")
                    return None

    except aiohttp.ClientError as e:
        raise CouldNotConnectToPKAPI  # Really not strictly necessary, but it makes the code a bit nicer I think.


class MemberBans(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        event_type = "member_join"
        
        await asyncio.sleep(1)  # Make sure the warning is displayed AFTER the New Member Joined Tab
        if await db.any_banned_systems(self.bot.db_pool, member.guild.id):
            log.info("Guild has banned PK Accounts. Check if current user is banned.")
            try:
                pk_response = await get_pk_system_from_userid(member.id)
                system_id = pk_response['id'] if pk_response is not None else None
            except CouldNotConnectToPKAPI:
                pk_response = None
                system_id = None  # add warning message to embed or maybe retry later?

            if system_id is not None and pk_response is not None:
                banned_users = await db.get_banned_system(self.bot.db_pool, member.guild.id, system_id)
                if len(banned_users) > 0:
                    log.info(f"This system ({system_id}) is banned. It is advised that this discord account be banned.")

                    log_channel = await self.bot.get_event_or_guild_logging_channel(member.guild.id, event_type)
                    if log_channel is None:
                        # Silently fail if no log channel is configured.
                        return
                    embed = self.get_banned_pk_account_joined_embed(member, pk_response)
                    await log_channel.send(embed=embed)
        else:
            log.info('Guild has no banned PK systems.')


    def get_banned_pk_account_joined_embed(self, member: discord.Member, system_info: Dict) -> discord.Embed:

        if 'name' in system_info and system_info['name'] is not None:
            desc = "PK System: {} - System ID: {}\nLinked to: <@{}> - {}#{}".format(system_info['name'], system_info['id'], member.id, member.name, member.discriminator)
            info_value = f"Warning! <@{member.id}> is linked to a Plural Kit system, **{system_info['name']}**, that is banned from this server!\n"

        else:
            desc = "PK System ID: {}\nLinked to: <@{}> - {}#{}".format(system_info['id'], member.id, member.name, member.discriminator)
            info_value = f"Warning! <@{member.id}> is linked to a Plural Kit system, ID: **{system_info['id']}**, that is banned from this server!\n"

        embed = discord.Embed(description=desc,
                              color=discord.Color.red(), timestamp=datetime.utcnow())

        embed.set_author(name="⚠️WARNING!⚠️Banned Plural Kit System Joined")

        if "avatar_url" in system_info and system_info["avatar_url"] is not None:
            avatar_url = system_info['avatar_url']
            # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
            ios_compatible_avatar_url = avatar_url
            embed.set_thumbnail(url=ios_compatible_avatar_url)

        embed.add_field(name="Info:",
                        value=info_value,
                        inline=False)

        embed.set_footer(text="System ID: {}".format(system_info['id']))

        return embed


    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.User, discord.Member]):
        """ User can be either a User (if they were hackbanned) Or a Member () If they were in the guild when banned"""

        await self.log_member_ban_or_unban(guild, user, "ban")
        # Check to see if the user has an associated Plural Kit Account.
        try:
            pk_response = await get_pk_system_from_userid(user.id)
            system_id = pk_response['id'] if pk_response is not None else None
        except CouldNotConnectToPKAPI:
            pk_response = None
            system_id = None  # add warning message to embed or maybe retry later?

        if system_id is not None and pk_response is not None:
            await db.add_banned_system(self.bot.db_pool, guild.id, system_id, user.id)
            banned_accounts = await db.get_banned_system(self.bot.db_pool, guild.id, system_id)
            log.info(f"The following accounts associated with {system_id} are banned: {banned_accounts}")
            # Send follow up embed.
            log_channel = await self.bot.get_event_or_guild_logging_channel(guild.id, 'member_ban')
            if log_channel is None:
                # Silently fail if no log channel is configured.
                return
            embed = self.get_pk_account_ban_embed(user, pk_response)
            await log_channel.send(embed=embed)


    def get_pk_account_ban_embed(self, member: discord.Member, system_info: Dict) -> discord.Embed:

        if 'name' in system_info and system_info['name'] is not None:
            desc = "{} - System ID: {}\nLinked to :<@{}> - {}#{}".format(system_info['name'], system_info['id'], member.id, member.name, member.discriminator)
            info_value = f"The Plural Kit system, **{system_info['name']}**, has been banned from this server as a Discord account linked to that system was banned.\n\n" \
                         f"You will be warned if any Discord accounts that are linked to that system join this server." #" and they will be auto-banned if Gabby Gums has been configured to do so."
        else:
            desc = "System ID: {}\nLinked to :<@{}> - {}#{}".format(system_info['id'], member.id, member.name, member.discriminator)
            info_value = f"The Plural Kit system, ID: **{system_info['id']}**, has been banned as a Discord account linked to that system was banned.\n\n" \
                         f"You will be warned if any Discord accounts that are linked to that system join this server." #" and they will be auto-banned if Gabby Gums has been configured to do so."
        embed = discord.Embed(description=desc,
                              color=discord.Color.dark_red(), timestamp=datetime.utcnow())

        embed.set_author(name="Plural Kit System Banned", icon_url="http://i.imgur.com/Imx0Znm.png")

        if "avatar_url" in system_info and system_info["avatar_url"] is not None:
            avatar_url = system_info['avatar_url']
            # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
            ios_compatible_avatar_url = avatar_url
            embed.set_thumbnail(url=ios_compatible_avatar_url)

        embed.add_field(name="Info:",
                        value=info_value,
                        inline=False)

        embed.set_footer(text="System ID: {}".format(system_info['id']))

        return embed


    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        await self.log_member_ban_or_unban(guild, user, "unban")

        log.info("Checking to see if user has any associated banned discord accounts...")
        # TODO: Should we check with the PK API to be sure, or even instead to prevent werid states that could happen from Null user_id DB entries?
        # TODO: Yeah, we should probably grab the info from the PK API As well to account for cases where we have a different System ID in the DB from thier current System ID>

        # banned_users = await db.get_banned_system_by_discordid(self.bot.db_pool, guild.id, user.id)

        try:
            pk_response = await get_pk_system_from_userid(user.id)
            system_id = pk_response['id'] if pk_response is not None else None
        except CouldNotConnectToPKAPI:
            pk_response = None
            system_id = None  # add warning message to embed or maybe retry later?

        if system_id is not None and pk_response is not None:

            banned_users = await db.get_banned_system(self.bot.db_pool, guild.id, system_id)

            if len(banned_users) > 0:
                log.info(f"Found banned accounts: {banned_users}")

                for account in banned_users:
                    if account.user_id != user.id:  # Skip the user that JUST got unbanned and any Nulls
                        log.info(f"Unbanning {account.user_id} in system {account.system_id} from discord.")

                # Remove all the banned entries from the DB.
                log.info(f"Removing system {banned_users[0].system_id} from the banned list.")
                await db.remove_banned_system(self.bot.db_pool, guild.id, banned_users[0].system_id)

                log_channel = await self.bot.get_event_or_guild_logging_channel(guild.id, 'member_unban')
                if log_channel is None:
                    # Silently fail if no log channel is configured.
                    return
                embed = self.get_pk_account_unban_emote(user, pk_response, banned_users, False)
                await log_channel.send(embed=embed)


    def get_pk_account_unban_emote(self, member: discord.User, system_info: Dict, unbanned_users: List[db.BannedUser], autoban: bool) -> discord.Embed:

        if 'name' in system_info and system_info['name'] is not None:
            desc = "{} - System ID: {}\nLinked to :<@{}> - {}#{}".format(system_info['name'], system_info['id'], member.id, member.name, member.discriminator)
            info_desc = f"The Plural Kit system, **{system_info['name']}**, has been **unbanned** from this server as a Discord account linked to that system was unbanned."

        else:
            desc = "System ID: {}\nLinked to :<@{}> - {}#{}".format(system_info['id'], member.id, member.name, member.discriminator)
            info_desc = f"The Plural Kit system, ID: **{system_info['id']}**, has been **unbanned** as a Discord account linked to that system was unbanned."

        embed = discord.Embed(description=desc, color=discord.Color.dark_green(), timestamp=datetime.utcnow())

        embed.set_author(name="Plural Kit System Unbanned", icon_url="https://i.imgur.com/OCcebCO.png")

        if "avatar_url" in system_info and system_info["avatar_url"] is not None:
            avatar_url = system_info['avatar_url']
            # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
            ios_compatible_avatar_url = avatar_url
            embed.set_thumbnail(url=ios_compatible_avatar_url)

        unban_msgs = []
        for account in unbanned_users:
            if account.user_id != member.id:
                unban_msgs.append(f"<@{account.user_id}>")

        if len(unban_msgs) == 0:
            autoban_txt = "There appears to be no other Discord accounts linked to the unbanned PK Account that are currently banned in this server."
        elif autoban:
            autoban_txt = "All Discord accounts that are linked to the PK Account that were banned here have now been unbanned. Look below for a list:"
        else:
            autoban_txt = "The following linked Discord accounts are potentially still banned:"

        unban_msg = '\n'.join(unban_msgs)
        info_value = f"{info_desc}\n{autoban_txt}\n{unban_msg}"

        embed.add_field(name="Info:",
                        value=info_value,
                        inline=False)

        embed.set_footer(text="System ID: {}".format(system_info['id']))

        return embed


    async def log_member_ban_or_unban(self, guild: discord.Guild, user: Union[discord.User, discord.Member],
                                      ban_or_unban: str):
        """ If ban, use "ban". if unban, use "unban" """
        log.info(f"User {ban_or_unban} Guild: {guild}, User: {user}")
        await asyncio.sleep(0.5)
        if ban_or_unban.lower() == "ban":
            audit_action = discord.AuditLogAction.ban
            embed_fn = member_ban
            event_type = "member_ban"
        elif ban_or_unban.lower() == "unban":
            audit_action = discord.AuditLogAction.unban
            embed_fn = member_unban
            event_type = "member_unban"
        else:
            raise ValueError("ban_or_unban must be 'ban' or 'unban' ")

        log_channel = await self.bot.get_event_or_guild_logging_channel(guild.id, event_type)
        if log_channel is None:
            # Silently fail if no log channel is configured.
            return
        # We have a log channel. Start pulling audit logs and doing stuff

        try:
            audit_log_entries = await get_audit_logs(guild, audit_action, user, timedelta(seconds=30))
            if len(audit_log_entries) > 0:
                # Assume the latest entry is the correct entry.
                # Todo: Maybe Look at the time data and reject if it's too old? Kinda redundent though since we already filter them all out...
                audit_log = audit_log_entries[0]
                log.info("Got logs")
            else:
                audit_log = None
                log.info("Got NO logs")

        except MissingAuditLogPermissions:
            audit_log = None
            log.info("need perms")
            # log.info(f"Gabby Gums needs the View Audit Log permission to display who {action_verbage} members.")

        embed = embed_fn(user, audit_log)
        await log_channel.send(embed=embed)


    # @commands.Cog.listener()
    # async def on_member_update(self, before: discord.Member, after: discord.Member):
    #     """Handles the 'on Member Update' event."""
    #     event_type_nick = "guild_member_nickname"  # nickname
    #     event_type_update = "guild_member_update"  # Everything else. Currently unused.
    #
    #     if before.nick != after.nick:
    #
    #         log_channel = await self.bot.get_event_or_guild_logging_channel(after.guild.id, event_type_nick)
    #         if log_channel is None:
    #             # Silently fail if no log channel is configured.
    #             return
    #
    #         embed = member_nick_update(before, after)
    #         await log_channel.send(embed=embed)


def setup(bot):
    bot.add_cog(MemberBans(bot))
