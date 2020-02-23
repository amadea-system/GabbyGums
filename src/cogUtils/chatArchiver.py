"""
Methods for generating HTML and TXT archives of a discord chat from a list of discord messages.

Part of the Gabby Gums Discord Logger.
"""


import logging
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

from jinja2 import Template, Environment, FileSystemLoader

if TYPE_CHECKING:
    from events.bulkMessageDelete import CompositeMessage, MessageGroups
    import discord

log = logging.getLogger(__name__)


# https://gist.github.com/glombard/7554134
# md = markdown.Markdown(extensions=['meta'])ch
# md = markdown.Markdown(output_format="html")
# md = markdown.Markdown()


file_loader = FileSystemLoader(searchpath="./htmlTemplates/")
env = Environment(loader=file_loader)
# env.filters['markdown'] = lambda text: Markup(md.convert(text))
template = env.get_template('mainChat.html')


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


def generate_html_archive(channel: 'discord.TextChannel', messages: 'MessageGroups', msg_count: int) -> StringIO:
    archive = StringIO()

    ctx = {'guild': channel.guild, 'channel': channel}
    output = template.render(ctx=ctx, msg_groups=messages, msg_count=msg_count)
    archive.writelines(output)
    archive.seek(0)
    return archive


# Unused, for debugging purposes.
def save_html_archive(channel: 'discord.TextChannel', messages: 'MessageGroups', msg_count: int):
    """This method does the same as generate_html_archive() except instead of returning a StringIO object suitable for passing to Discord, it saves the html for debugging. """
    ctx = {'guild': channel.guild, 'channel': channel}
    output = template.render(ctx=ctx, msg_groups=messages, msg_count=msg_count)

    with open('archive.html', 'w', encoding="utf-16") as archive:
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

    with open('debug_archive.html.txt', 'w', encoding="utf-16") as archive:
        archive.write(f"{len(lines)} messages archived from #{channel_name} @ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S-UTC')}\n\n")
        for line in lines:
            archive.write(line)
