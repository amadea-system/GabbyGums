"""
Methods for generating HTML and TXT archives of a discord chat from a list of discord messages.

Part of the Gabby Gums Discord Logger.
"""


import logging
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord

if TYPE_CHECKING:
    from events.bulkMessageDelete import CompositeMessage

log = logging.getLogger(__name__)


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
            author: Union[discord.Member, discord.User] = message.author
            author_info = author.id if author else "None"

        msg = f"[{message.created_at.strftime('%Y-%m-%d %H:%M:%S-UTC')}] {message.user_name_and_discrim} ({author_info}):" \
              f"\n    {content}\n\n"
        lines.append(msg)

    archive.write(f"{len(lines)} messages archived from #{channel_name} @ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S-UTC')}\n\n")
    for line in lines:
        archive.write(line)

    archive.seek(0)
    return archive

