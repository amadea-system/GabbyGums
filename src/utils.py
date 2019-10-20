import discord
import textwrap


async def send_long_msg(channel: discord.TextChannel, message: str, code_block: bool = False, code_block_lang: str = "python"):

    if code_block:
        if len(code_block_lang) > 0:
            code_block_lang = code_block_lang + "\n"
        code_block_start = "```" + code_block_lang
        code_block_end = "```"
        code_block_extra_length = len(code_block_start) + len(code_block_end)
        chunks = textwrap.wrap(message, width=2000 - code_block_extra_length)
        message_chunks = [code_block_start + chunk + code_block_end for chunk in chunks]

    else:
        message_chunks = textwrap.wrap(message, width=2000)

    for chunk in message_chunks:
        await channel.send(chunk)
