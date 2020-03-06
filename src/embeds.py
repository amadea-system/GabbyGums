"""

"""

import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional, Dict, Union
from db import StoredInvite, CachedMessage
import logging

log = logging.getLogger(__name__)


def split_message(message: str) -> (str, str):
    # TODO: Make better
    msg1 = message[:1000]
    msg2 = message[1000:]
    return msg1, msg2


def about_message() -> discord.Embed:
    help_msg = "Created by **Luna and Hibiki** (<@!389590659335716867>).\n\n"
    "This bot is for use on any server, with or with out pluralKit " \
    "and most importantly can be used by/for any kind of system or singlet, " \
    "this includes Endogenic systems, Tulpa systems, Traumagenic systems, Mixed systems, Gateway systems, roleplayers, " \
    "and **ANYONE** else I did not specifically list.\n"
    "This bot does NOT work with the System Time bot and we kindly request that it is not modified to work with System Time.\n"
    "For support, suggestions, or anything else, feel free to join our support server @ https://discord.gg/3Ugade9\n\n"

    embed = discord.Embed(title="Gabby Gums",
                          description="A simple logging bot that ignores PluralKit proxies.",
                          color=0x9932CC)
    embed.add_field(name="Who can use Gabby Gums",
                    value="Anyone.\n"
                    "Regardless of system type or plurality, all people are valid. "
                          "As such, all people are allowed to use this bot.\n"
                    "This bot is not coded with support for the System Time bot. "
                          "We would also kindly request that it is not modified to work with System Time")
    embed.add_field(name="Support Server",
                    value="For support, suggestions, just want to chat with someone, "
                          "or anything else, feel free to join our support server @ https://discord.gg/3Ugade9")

    embed.set_footer(text="Created by Luna, Hibiki, and Fluttershy aka Amadea System (Hibiki#8792) "
                          "| Github: https://github.com/amadea-system/GabbyGums/")

    return embed


def edited_message(author_id, author_name: str, author_discrim, channel_id, before_msg: str, after_msg: str,
                   message_id: str, guild_id) -> discord.Embed:

    before_msg = before_msg if before_msg else "Message not in the cache."

    embed = discord.Embed(title="Edited Message",
                          description="<@{}> - {}#{}".format(author_id, author_name, author_discrim),
                          color=0x61cd72, timestamp=datetime.utcnow())

    embed.set_thumbnail(
        url="https://i.imgur.com/Q8SzUdG.png")
    embed.add_field(name="Info:",
                    value="A message by <@{author_id}>, was edited in <#{channel_id}>\n"
                          "[Go To Message](https://discordapp.com/channels/{guild_id}/{channel_id}/{message_id})".format(author_id=author_id, channel_id=channel_id, guild_id=guild_id, message_id=message_id),
                    inline=False)

    if len(before_msg) > 1024 or len(after_msg) > 1024:  # To simplify things, if one is greater split both
        before_msg1, before_msg2 = split_message(before_msg)
        after_msg1, after_msg2 = split_message(after_msg)
        embed.add_field(name="Message Before Edit:", value=before_msg1, inline=False)
        if len(before_msg2.strip()) > 0:
            embed.add_field(name="Message Before Edit Continued:", value=before_msg2, inline=False)

        embed.add_field(name="Message After Edit:", value=after_msg1, inline=False)
        if len(after_msg2.strip()) > 0:
            embed.add_field(name="Message After Edit Continued:", value=after_msg2, inline=False)
    else:
        embed.add_field(name="Message Before Edit:", value=before_msg, inline=True)
        embed.add_field(name="Message After Edit:", value=after_msg, inline=True)
    embed.set_footer(text="User ID: {}".format(author_id))

    return embed


def deleted_message(message_content: Optional[str], author: Optional[discord.Member], channel_id: int, message_id: int = -1,
                    webhook_info: Optional[CachedMessage] = None, pk_system_owner: Optional[discord.Member] = None,
                    cached: bool = True) -> discord.Embed:

    # If the webhook_info is none, create dummy object to make if's neater
    if webhook_info is None:
        webhook_info = CachedMessage(None, None, None, None, None, None, None, None, None, None)

    if cached:
        pk_id_msg = ""
        if webhook_info.member_pkid is not None or webhook_info.system_pkid is not None:
            s = '\u205f'  # Medium Mathematical Space
            pk_id_msg = f"{s}\n{s}\nSystem ID: {s}{s}{s}**{webhook_info.system_pkid}** \nMember ID: {s}**{webhook_info.member_pkid}**"
            log.info("pk_id_msg set")

        if author is None:
            log.info("Author is None")
            # We have NO info on the author of the message.
            if webhook_info.webhook_author_name is not None:
                log.info("Webhook Author is NOT None")
                description_text = f"{webhook_info.webhook_author_name}{pk_id_msg}"
                info_author = f"**{webhook_info.webhook_author_name}**"
            else:
                log.info("Webhook Author is None")
                description_text = info_author = "Uncached User"

        elif author.discriminator == "0000":
            description_text = f"{author.name}{pk_id_msg}"
            info_author = f"**{author.name}**"
        else:
            description_text = f"<@{author.id}> - {author.name}#{author.discriminator}"
            info_author = f"<@{author.id}>"

        embed = discord.Embed(title="Deleted Message",
                              description=description_text,
                              color=0x9b59b6,
                              timestamp=datetime.utcnow())
        embed.set_thumbnail(url="http://i.imgur.com/fJpAFgN.png")

        embed.add_field(name="Info:",
                        value="A message by {}, was deleted in <#{}>".format(info_author, channel_id),
                        inline=False)

        if pk_system_owner is not None:
            embed.add_field(name="Linked Discord Account:",
                            value=f"<@{pk_system_owner.id}> - {pk_system_owner.name}#{pk_system_owner.discriminator}",
                            inline=False)

        if len(message_content) > 1024:
            msg_cont_1, msg_cont_2 = split_message(message_content)
            embed.add_field(name="Message:", value=msg_cont_1, inline=False)
            embed.add_field(name="Message continued:", value=msg_cont_2, inline=False)
        else:
            embed.add_field(name="Message:", value=message_content, inline=False)

        if author is not None:
            embed.set_footer(text=f"User ID: {author.id}")

        return embed
    else:
        return unknown_deleted_message(channel_id, message_id)


def unknown_deleted_message(channel_id, message_id) -> discord.Embed:
    embed = discord.Embed(title="Deleted Message",
                          description="Unknown User", color=0x9b59b6, timestamp=datetime.utcnow())
    embed.set_thumbnail(url="http://i.imgur.com/fJpAFgN.png")
    embed.add_field(name="Info:",
                    value="A message not in the cache was deleted in <#{}>".format(channel_id),
                    inline=False)
    embed.add_field(name="Message ID:", value=message_id, inline=False)

    return embed


def member_join(member: discord.Member, invite: Optional[StoredInvite], pk_info: Optional[Dict], manage_guild=True) -> discord.Embed:
    embed = discord.Embed(description="<@!{}> - {}#{}".format(member.id, member.name, member.discriminator),
                          color=0x00ff00, timestamp=datetime.utcnow())

    embed.set_author(name="New Member Joined!!!",
                     icon_url="https://www.emoji.co.uk/files/twitter-emojis/objects-twitter/11031-inbox-tray.png")

    # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    ios_compatible_avatar_url = member.avatar_url_as(static_format="png")
    embed.set_thumbnail(url=ios_compatible_avatar_url)

    embed.add_field(name="Info:",
                    value="{} has joined the server!!!".format(member.display_name),
                    inline=False)
    account_age = datetime.utcnow() - member.created_at
    embed.add_field(name="Account Age", value="**{}** days old".format(account_age.days), inline=True)
    embed.add_field(name="Current Member Count", value="**{}** Members".format(member.guild.member_count), inline=True)

    if pk_info is not None:
        embed.add_field(name="\N{Zero Width Space}‌‌‌", value="\n__**Plural Kit Information**__", inline=False)
        # embed.add_field(name="\N{Zero Width Space}‌‌‌", value="\N{Zero Width Space}", inline=True)  # Add a blank embed to force the PK info onto it's own line.

        if "name" in pk_info:
            embed.add_field(name="System Name", value=pk_info['name'], inline=True)
        embed.add_field(name="System ID", value=pk_info['id'], inline=True)

        # Compute the account age
        pk_created_date = datetime.strptime(pk_info['created'], '%Y-%m-%dT%H:%M:%S.%fZ')
        pk_account_age = datetime.utcnow() - pk_created_date
        embed.add_field(name="PK Account Age", value=f"**{pk_account_age.days}** days old", inline=True)

    if invite is not None:
        embed.add_field(name=" ‌‌‌", value="\n__**Invite Information**__", inline=False)

        if invite.invite_name is not None:
            embed.add_field(name="Name:", value="{}".format(invite.invite_name))

        if invite.invite_id is not None:
            embed.add_field(name="Code", value="{}".format(invite.invite_id))

        if invite.actual_invite is not None:
            embed.add_field(name="Uses", value="{}".format(invite.actual_invite.uses))
            embed.add_field(name="Created By", value="<@!{}> - {}#{}".format(invite.actual_invite.inviter.id,
                                                                             invite.actual_invite.inviter.name,
                                                                             invite.actual_invite.inviter.discriminator))

            embed.add_field(name="Created on",
                            value=invite.actual_invite.created_at.strftime("%b %d, %Y, %I:%M:%S %p UTC"))
    else:
        if not manage_guild:
            embed.add_field(name="Permissions Warning!",
                            value="**Manage Server Permissions** needed for invite tracking.")
        elif member.bot:
            embed.add_field(name=" ‌‌‌", value="\n__**Invite Information**__", inline=False)
            embed.add_field(name="Code", value="Bot OAuth Link")
        else:
            embed.add_field(name="__**Invite Information**__",
                            value="Unable to determine invite information. It's likely the invite was a one time use invite."
                                  " You may be able to determine the inviter by using the Audit Log.", inline=False)

    embed.set_footer(text="User ID: {}".format(member.id))

    return embed


def member_leave(member: discord.Member) -> discord.Embed:
    embed = discord.Embed(description="<@{}> - {}#{}".format(member.id, member.name, member.discriminator),
                          color=0xf82125, timestamp=datetime.utcnow())

    embed.set_author(name="Member Left 😭",
                     icon_url="https://www.emoji.co.uk/files/mozilla-emojis/objects-mozilla/11928-outbox-tray.png")

    # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    ios_compatible_avatar_url = member.avatar_url_as(static_format="png")
    embed.set_thumbnail(url=ios_compatible_avatar_url)
    embed.add_field(name="Info:",
                    value="{} has left the server 😭.".format(member.display_name),
                    inline=False)
    embed.set_footer(text="User ID: {}".format(member.id))

    return embed


def member_kick(member: discord.Member, audit_log: Optional[discord.AuditLogEntry]) -> discord.Embed:
    embed = discord.Embed(description="<@{}> - {}#{}".format(member.id, member.name, member.discriminator),
                          color=discord.Color.dark_orange(), timestamp=datetime.utcnow())

    embed.set_author(name="Member Kicked",
                     icon_url="https://i.imgur.com/o96t3cV.png")

    # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    ios_compatible_avatar_url = member.avatar_url_as(static_format="png")
    embed.set_thumbnail(url=ios_compatible_avatar_url)
    embed.add_field(name="Info:",
                    value="{} was kicked from the server.".format(member.display_name),
                    inline=False)

    if audit_log is not None:
        embed.add_field(name="Kicked By:",
                        value="<@{}> - {}#{}".format(audit_log.user.id, audit_log.user.name, audit_log.user.discriminator), inline=False)

        reason = f"{audit_log.reason}" if audit_log.reason else "No Reason was given."
        embed.add_field(name="Reason:",
                        value=reason,
                        inline=False)

    embed.set_footer(text="User ID: {}".format(member.id))

    return embed

def member_ban(member: discord.Member, audit_log: Optional[discord.AuditLogEntry]) -> discord.Embed:
    embed = discord.Embed(description="<@{}> - {}#{}".format(member.id, member.name, member.discriminator),
                          color=discord.Color.dark_red(), timestamp=datetime.utcnow())

    embed.set_author(name="Member Banned", icon_url="http://i.imgur.com/Imx0Znm.png")

    # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    ios_compatible_avatar_url = str(member.avatar_url_as(static_format="png"))
    embed.set_thumbnail(url=ios_compatible_avatar_url)
    embed.add_field(name="Info:",
                    value="**{}** was banned from the server.".format(member.display_name),
                    inline=False)

    if audit_log is not None:
        embed.add_field(name="Banned By:",
                        value="<@{}> - {}#{}".format(audit_log.user.id, audit_log.user.name, audit_log.user.discriminator), inline=False)

        reason = f"{audit_log.reason}" if audit_log.reason else "No Reason was given."
        embed.add_field(name="Reason:",
                        value=reason,
                        inline=False)
    # else:
    #     embed.add_field(name="Need `View Audit Log` Permissions to show more information",
    #                     value="\N{zero width space}")

    embed.set_footer(text="User ID: {}".format(member.id))

    return embed


def member_unban(member: discord.User, audit_log: Optional[discord.AuditLogEntry]) -> discord.Embed:
    embed = discord.Embed(description="<@{}> - {}#{}".format(member.id, member.name, member.discriminator),
                          color=discord.Color.dark_green(), timestamp=datetime.utcnow())

    embed.set_author(name="Member Unbanned", icon_url="https://i.imgur.com/OCcebCO.png")

    # Need to use format other than WebP for image to display on iOS. (I think this is a recent discord bug.)
    ios_compatible_avatar_url = str(member.avatar_url_as(static_format="png"))
    embed.set_thumbnail(url=ios_compatible_avatar_url)
    embed.add_field(name="Info:",
                    value="**{}** was unbanned from the server.".format(member.display_name),
                    inline=False)

    if audit_log is not None:
        embed.add_field(name="Unbanned By:",
                        value="<@{}> - {}#{}".format(audit_log.user.id, audit_log.user.name, audit_log.user.discriminator), inline=False)

        reason = f"{audit_log.reason}" if audit_log.reason else "No Reason was given."
        embed.add_field(name="Reason:",
                        value=reason,
                        inline=False)
    # else:
    #     embed.add_field(name="Need `View Audit Log` Permissions to show more information",
    #                     value="\N{zero width space}")

    embed.set_footer(text="User ID: {}".format(member.id))

    return embed


def member_nick_update(before: discord.Member, after: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        description="<@{}> - {}#{} changed their nickname.".format(after.id, after.name, after.discriminator),
        color=0x00ffff, timestamp=datetime.utcnow())

    embed.set_author(name="Nickname Changed")

    embed.set_thumbnail(url="https://i.imgur.com/HtQ53lx.png")

    embed.add_field(name="Old Nickname", value=before.nick, inline=True)
    embed.add_field(name="New Nickname", value=after.nick, inline=True)
    embed.set_footer(text="User ID: {}".format(after.id))

    return embed


def user_name_update(before: discord.User, after: discord.User) -> discord.Embed:

    if before.name != after.name and before.discriminator == after.discriminator:
        # Name changed, discriminator did not
        changed_txt = "Username"
    elif before.name == after.name and before.discriminator != after.discriminator:
        # Discrim changed, Name did not
        changed_txt = "Discriminator"
    else:
        # Both changed
        changed_txt = "Username & Discriminator"

    embed = discord.Embed(description=f"<@{after.id}> - {after.name}#{after.discriminator} changed their {changed_txt}.",
                          color=discord.Color.teal(), timestamp=datetime.utcnow())

    embed.set_author(name=f"{changed_txt} Changed")

    if before.name != after.name:
        embed.add_field(name="Old Username:", value=before.name, inline=True)
        embed.add_field(name="New Username:", value=after.name, inline=True)

    if before.discriminator != after.discriminator:
        embed.add_field(name="Old Discriminator:", value=before.discriminator, inline=True)
        embed.add_field(name="New Discriminator:", value=after.discriminator, inline=True)

    embed.set_footer(text="User ID: {}".format(after.id))

    return embed


def user_avatar_update(before: discord.User, after: discord.User, embed_image_filename: str) -> discord.Embed:

    embed = discord.Embed(description="<@{}> - {}#{} changed their avatar.".format(after.id, after.name, after.discriminator),
                          color=0x00aaaa, timestamp=datetime.utcnow())

    embed.set_author(name="Avatar Changed")
    embed.set_image(url=f"attachment://{embed_image_filename}")

    embed.set_footer(text="User ID: {}".format(after.id))

    return embed


def exception_w_message(message: discord.Message) -> discord.Embed:
    embed = discord.Embed()
    embed.colour = 0xa50000
    embed.title = message.content
    guild_id = message.guild.id if message.guild else "DM Message"

    embed.set_footer(text="Server: {}, Channel: {}, Sender: <@{}> - {}#{}".format(
        message.author.name, message.author.discriminator, message.author.id,
        guild_id, message.channel.id))
    return embed
