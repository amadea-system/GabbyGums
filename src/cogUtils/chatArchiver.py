"""
Methods for generating HTML and TXT archives of a discord chat from a list of discord messages.

Part of the Gabby Gums Discord Logger.
"""

import hmac
import regex as re
import logging
import hashlib

from functools import partial
from datetime import datetime
from io import StringIO, SEEK_END, SEEK_SET
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Match

from jinja2 import Template, Environment, FileSystemLoader

if TYPE_CHECKING:
    from events.bulkMessageDelete import CompositeMessage, MessageGroups
    import discord
    from discord.ext import commands

log = logging.getLogger(__name__)

auth_key_pattern = re.compile(r"<!--([0-9a-f]+)-->")

file_loader = FileSystemLoader(searchpath="./htmlTemplates/")
env = Environment(loader=file_loader)
env.trim_blocks = True
env.lstrip_blocks = True
template = env.get_template('mainChat.html')


class CouldNotFindAuthenticationCode(Exception):
    pass


def generate_txt_archive(messages: List['CompositeMessage'], channel_name) -> StringIO:

    archive = StringIO()
    lines = []
    for message in messages:
        if message.content:
            content = message.content
        else:
            content = "----Message contained no text----"

        if message.is_pk:
            author_info = f"System ID: {message.system_id}, Member ID: {message.member_id}"
        else:
            author: Union['discord.Member', 'discord.User'] = message.author
            author_info = author.id if author else "None"

        msg = f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S-UTC')}] {message.user_name_and_discrim} ({author_info}):" \
              f"\n    {content}\n\n"
        lines.append(msg)

    archive.write(f"{len(lines)} messages archived from #{channel_name} @ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S-UTC')}\n\n")
    for line in lines:
        archive.write(line)

    archive.seek(0)
    return archive



async def generate_html_archive(bot: 'commands.bot', channel: 'discord.TextChannel', messages: 'MessageGroups', msg_count: int) -> StringIO:

    fn = partial(blocking_generate_html_archive, channel, messages, msg_count)
    archive = await bot.loop.run_in_executor(None, fn)
    return archive


def blocking_generate_html_archive(channel: 'discord.TextChannel', messages: 'MessageGroups', msg_count: int) -> StringIO:
    archive = StringIO()

    ctx = {'guild': channel.guild, 'channel': channel}
    output = template.render(ctx=ctx, msg_groups=messages, msg_count=msg_count)
    archive.writelines(output)
    archive.seek(0)

    return archive


def generate_SHA256_hash(_input: StringIO) -> str:
    """Generates a SHA256 hash for a StringIO Object and seeks the Object back to 0 at the end."""
    _input.seek(0)
    hasher = hashlib.sha256()
    hasher.update(str(_input.read()).encode('utf-8'))  # 16
    _input.seek(0)
    return hasher.hexdigest()


def get_hmac(_input: StringIO, security_key: bytes) -> str:
    _input.seek(0)
    msg = str(_input.read()).encode('utf-8')
    hasher = hmac.new(security_key, msg, hashlib.sha3_256)  # Create the HMAC Hasher
    hash = hasher.hexdigest()  # Get the hmac hash
    _input.seek(0)
    return hash


def write_hmac(_input: StringIO, security_key: bytes):
    """Generates a Hash-base Message Authentication Code for a given StringIO Object and writes it to the end of the file."""

    _input.seek(0)  # Seek the StringIO back to the beginning so it can be read.

    hash = get_hmac(_input, security_key)
    # log.info(f"Got HMAC: {hash}")
    _input.seek(0, SEEK_END)  # Make sure we are at the end of the file so we can write the hmac
    _input.write(f"\n<!--{hash}-->")  # Write the hash to the StringIO

    _input.seek(0)  # Finally Seek the StringIO back to the beginning so it's ready the next time it needs to be read.


def verify_file(file: StringIO, security_key: bytes) -> bool:


    file.seek(0, SEEK_END)  # Seek to the end of the file. so we can iterate backward.
    pos = file.tell()  # store the position that is the end of the file.
    # log.info(f"Pos: {pos}")

    file.seek(0, SEEK_END)  # Seek back to the end of the file.
    while pos > 0 and file.read(1) != '\n':  # Go backwards through the file until we hit a new line or the start of the file.
        pos -= 1
        file.seek(pos, SEEK_SET)
    # log.info(f"Pos after seeking: {pos}")
    auth_code = None
    if pos > 0:
        file.seek(pos+1, SEEK_SET)  # Go forward one char to get tot he start of the last line. This is where the auth code lies.
        auth_code = file.readline()  # Grab the auth code

        file.seek(pos, SEEK_SET)  # Go back to the new line
        file.truncate()  # And delete everything after it so we can get back to a HMACable file.

    if auth_code is not None:
        auth_code_match: Match = auth_key_pattern.match(auth_code)
        if auth_code_match is not None:
            auth_code = auth_code_match.group(1)
            log.info(f"Got auth code: {auth_code}")
            hash = get_hmac(file, security_key)
            log.info(f"files hmac: {hash}")

            # if hash == auth_code:
            if hmac.compare_digest(hash, auth_code):
                log.info("File is unmodified.")
                return True
            else:
                log.info("Authentication Code mismatch. File has been modified.")
                return False

    raise CouldNotFindAuthenticationCode("Could not find authentication code in the archive file!")


# Unused, for debugging purposes.
def save_html_archive(channel: 'discord.TextChannel', messages: 'MessageGroups', msg_count: int):
    """This method does the same as generate_html_archive() except instead of returning a StringIO object suitable for passing to Discord, it saves the html for debugging. """
    ctx = {'guild': channel.guild, 'channel': channel}
    output = template.render(ctx=ctx, msg_groups=messages, msg_count=msg_count)

    with open('archive.html', 'w', encoding="utf-8") as archive:    # 16
        archive.writelines(output)


# Unused, for debugging purposes.
def save_htmlDebug_txt_archive(messages: List['CompositeMessage'], channel_name):
    messages.reverse()
    lines = []
    for message in messages:
        if message.content:
            content = message.content
        else:
            content = "----Message contained no text----"

        if message.is_pk:
            author_info = f"System ID: {message.system_id}, Member ID: {message.member_id}"
        else:
            author: Union['discord.Member', 'discord.User'] = message.author
            author_info = author.id if author else "None"

        msg = f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S-UTC')}] {message.user_name_and_discrim} ({author_info}):" \
              f"\n\n    {content}\n\n"
        lines.append(msg)

    with open('debug_archive.html.txt', 'w', encoding="utf-8") as archive:    # 16
        archive.write(f"{len(lines)} messages archived from #{channel_name} @ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S-UTC')}\n\n")
        for line in lines:
            archive.write(line)
