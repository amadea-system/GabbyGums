"""

"""

import discord
from datetime import datetime
from typing import Optional, Union
from db import StoredInvite


# TODO: Make these all async?


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
        embed.add_field(name="Message Before Edit:", value=before_msg1, inline=True)
        if len(before_msg2.strip()) > 0:
            print("before_msg2: {}".format(before_msg2))
            embed.add_field(name="Message Before Edit Continued:", value=before_msg2, inline=True)

        embed.add_field(name="Message After Edit:", value=after_msg1, inline=True)
        if len(after_msg2.strip()) > 0:
            print("after_msg2: {}\n\n".format(after_msg2))
            embed.add_field(name="Message After Edit Continued:", value=after_msg2, inline=True)
    else:
        embed.add_field(name="Message Before Edit:", value=before_msg, inline=True)
        embed.add_field(name="Message After Edit:", value=after_msg, inline=True)
    embed.set_footer(text="User ID: {}".format(author_id))

    return embed


def deleted_message(message_content: str, author: discord.Member, channel_id: int, message_id: int = -1,
                    cached: bool = True) -> discord.Embed:

    if cached:
        if author.discriminator == "0000":
            description_text = "{}#{}".format(author.name, author.discriminator)
            info_author = "{}#{}".format(author.name, author.discriminator)
        else:
            description_text = "<@{}> - {}#{}".format(author.id, author.name, author.discriminator)
            info_author = "<@{}>".format(author.id)

        embed = discord.Embed(title="Deleted Message",
                              description=description_text,
                              color=0x9b59b6,
                              timestamp=datetime.utcnow())
        embed.set_thumbnail(url="http://i.imgur.com/fJpAFgN.png")
        embed.add_field(name="Info:",
                        value="A message by {}, was deleted in <#{}>".format(info_author, channel_id),
                        inline=False)

        if len(message_content) > 1024:
            msg_cont_1, msg_cont_2 = split_message(message_content)
            embed.add_field(name="Message:", value=msg_cont_1, inline=False)
            embed.add_field(name="Message continued:", value=msg_cont_2, inline=False)
        else:
            embed.add_field(name="Message:", value=message_content, inline=False)

        embed.set_footer(text="User ID: {}".format(author.id))

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


def member_join(member: discord.Member, invite: Optional[StoredInvite], manage_guild=True) -> discord.Embed:
    embed = discord.Embed(description="<@!{}> - {}#{}".format(member.id, member.name, member.discriminator),
                          color=0x00ff00, timestamp=datetime.utcnow())

    embed.set_author(name="New Member Joined!!!",
                     icon_url="https://www.emoji.co.uk/files/twitter-emojis/objects-twitter/11031-inbox-tray.png")
    embed.set_thumbnail(url=member.avatar_url)

    embed.add_field(name="Info:",
                    value="{} has joined the server!!!".format(member.display_name),
                    inline=False)
    account_age = datetime.utcnow() - member.created_at
    embed.add_field(name="Account Age", value="**{}** days old".format(account_age.days), inline=True)
    embed.add_field(name="Current Member Count", value="**{}** Members".format(member.guild.member_count))

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
    embed.set_thumbnail(url=member.avatar_url)
    embed.add_field(name="Info:",
                    value="{} has left the server 😭.".format(member.display_name),
                    inline=False)
    embed.set_footer(text="User ID: {}".format(member.id))

    return embed


def member_nick_update(before: discord.Member, after: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        description="<@{}> - {}#{} changed their nickname.".format(after.id, after.name, after.discriminator),
        color=0x00ffff, timestamp=datetime.utcnow())

    embed.add_field(name="Old Nickname", value=before.nick, inline=True)
    embed.add_field(name="New Nickname", value=after.nick, inline=True)
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
