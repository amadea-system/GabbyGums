"""
Class for parsing and converting the discord flavor of Markdown.

Part of the Gabby Gums Discord Logger.
"""

import logging

from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Match

import regex as re
from jinja2 import escape

log = logging.getLogger(__name__)


class DiscordMarkdown:
    # TODO: Consider optimising by not using lazy quantifiers: https://www.rexegg.com/regex-quantifiers.html
    # codeblock_pattern = re.compile(r"(?P<stag>```)(?:(?P<lang>[a-zA-Z0-9-]+?)\n+)?\n*(?P<content>[^`]+?)\n*(?P<etag>```)")  # Multiline. Group 1 is Code Language (May be None), Group 2 is the content of the block
    codeblock_pattern = re.compile(r"(?P<stag>```)(?:(?P<lang>[a-zA-Z0-9-]+?)\n+)?\n*(?P<content>[\s\S]+?)\n*(?P<etag>```)")  # Multiline. Group 1 is Code Language (May be None), Group 2 is the content of the block
    # inlinecodeblock_pattern: Pattern = re.compile(r"(?P<stag>`)(?P<content>.+?)(?P<etag>`)")
    # inlinecodeblock_pattern = re.compile(r"^[^`\/]*?(`)([^`]*?[^`])(\1)(?!`)", flags=re.MULTILINE)
    inlinecodeblock_pattern = re.compile(r"(?<!\\)(`)(?P<content>[^`]*?[^`])(\1)(?!`)")
    strikethrough_pattern = re.compile(r"(?<!\\)~~(?P<content>.+?)(?<!\\)~~(?!_)")  # Singleline. G2 is content.
    spoiler_pattern = re.compile(r"(?<!\\)\|\|(?P<content>.+?)(?<!\\)\|\|")  # Singleline. G2 is content.
    bold_pattern = re.compile(r"(?<!\\)\*\*(?P<content>.+?)(?<!\\)\*\*")  # Singleline. G2 is content.
    underline_pattern = re.compile(r"(?<!\\)__(?P<content>.+?)(?<!\\)__")  # Singleline. G2 is content.
    italics_pattern1 = re.compile(r"(?<!\\)\*(?P<content>.+?)(?<!\\)\*")  # Singleline. G2 is content.
    italics_pattern2 = re.compile(r"(?<!\\)_(?P<content>.+?)(?<!\\)_")  # Singleline. G2 is content.
    # incompat_blockQuote_pattern = re.compile(r"^(?: *>>> ([\s\S]*))|^(?: *> ([^\n]*\n*))", flags=re.MULTILINE)  # (r"(?: *>>> ([\s\S]*))|(?: *> ([^\n]*))") # (?: *>>> ([\s\S]*))|
    blockQuote_pattern = re.compile(r"^(?: *&gt;&gt;&gt; ([\s\S]*))|^(?: *&gt; ([^\n]*\n*))",
                                    flags=re.MULTILINE)  # (r"(?: *>>> ([\s\S]*))|(?: *> ([^\n]*))") # (?: *>>> ([\s\S]*))|
    symbols_pattern = re.compile(r"(?P<content>[^a-zA-Z0-9\s])")
    escaped_symbols_pattern = re.compile(r"\\(?P<content>[^a-zA-Z0-9\s])")

    suppresed_embed_link_pattern = re.compile(r"&lt;(?P<content>http[s]?:\/\/\S+?)&gt;")
    web_link_pattern = re.compile(r"\[(.+)\]\([^\n\S]*?(http[s]?:\/\/[\S]+?)[^\n\S]*?\)|(http[s]?:\/\/[\S]+)")  # TODO: Consider optimising by having normal links match first.
    nitro_emote_pattern = re.compile(r"&lt;(?P<animated>a)?:(?P<name>[0-9a-zA-Z_]{2,32}):(?P<id>[0-9]{15,21})&gt;")
    womboji_pattern = re.compile(r"([a-zA-Z0-9!-;=?-~\s]*)?\s*<a?:[0-9a-zA-Z_]{2,32}:[0-9]{15,21}>\s*([a-zA-Z0-9!-;=?-~\s]*)?")  # http://www.asciitable.com/


    @classmethod
    def escape_symbols_repl(cls, m: Match):
        content = m.group('content')
        return "\\"+content


    @classmethod
    def escape_symbols(cls, _input: str) -> str:
        """Adds an extra escape char to every escapable character. Used for code blocks so the escape characters will remain at the end."""
        output = cls.symbols_pattern.sub(cls.escape_symbols_repl, _input)
        return output

    @classmethod
    def remove_escaped_symbol_repl(cls, m: Match):
        content = m.group('content')
        return content

    @classmethod
    def remove_escaped_symbol(cls, _input: str) -> str:
        """Removes the escape characters."""
        output = cls.escaped_symbols_pattern.sub(cls.remove_escaped_symbol_repl, _input)
        return output


    @classmethod
    def codeblock_repl(cls, m: Match):
        e_tag = "</div>"

        if m.group("lang") is not None:
            s_tag = f'<div class="pre pre--multiline language-{m.group("lang")}">'
        else:
            s_tag = '<div class="pre pre--multiline nohighlight">'

        # Clean up the content
        content = m.group('content')
        content = cls.escape_symbols(content)

        replacement = f"{s_tag}{content}{e_tag}"
        return replacement


    @classmethod
    def codeblock(cls, _input: str) -> Tuple[str, int]:

        output = cls.codeblock_pattern.subn(cls.codeblock_repl, _input)
        return output


    @classmethod
    def inline_codeblock_repl(cls, m: Match):
        s_tag = '<span class="pre pre--inline">'
        e_tag = '</span>'

        # Clean up the content
        content = m.group('content')  # Markup(match.group('content')).striptags()
        content = cls.escape_symbols(content)
        replacement = f"{s_tag}{content}{e_tag}"
        return replacement

    @classmethod
    def inline_codeblock(cls, _input: str) -> Tuple[str, int]:
        output = cls.inlinecodeblock_pattern.subn(cls.inline_codeblock_repl, _input)
        return output

    # region foldpls

    @classmethod
    def spoiler(cls, _input: str) -> Tuple[str, int]:
        s_tag = '<span class="spoiler">'
        e_tag = "</span>"
        repl = r"{}\g<content>{}".format(s_tag, e_tag)
        output = cls.spoiler_pattern.subn(repl, _input)
        return output


    @classmethod
    def bold(cls, _input: str) -> Tuple[str, int]:
        first_tag = '<strong>'
        end_tag = "</strong>"
        repl = r"{}\g<content>{}".format(first_tag, end_tag)
        output = cls.bold_pattern.subn(repl, _input)
        return output


    @classmethod
    def underline(cls, _input: str) -> Tuple[str, int]:
        first_tag = '<u>'
        end_tag = "</u>"
        repl = r"{}\g<content>{}".format(first_tag, end_tag)
        output = cls.underline_pattern.subn(repl, _input)
        return output


    @classmethod
    def italics(cls, _input: str) -> Tuple[str, int]:
        first_tag = '<em>'
        end_tag = "</em>"
        repl = r"{}\g<content>{}".format(first_tag, end_tag)
        output, count = cls.italics_pattern1.subn(repl, _input)
        output, count2 = cls.italics_pattern2.subn(repl, output)

        return output, count+count2


    @classmethod
    def strikethrough(cls, _input: str) -> Tuple[str, int]:
        first_tag = "<s>"
        end_tag = "</s>"
        repl = r"{}\g<content>{}".format(first_tag, end_tag)
        output = cls.strikethrough_pattern.subn(repl, _input)
        return output
    # endregion


    @classmethod
    def blockquote_repl(cls, m: Match):
        s_tag = '<div class="quote">'
        e_tag = "</div>"

        if m.group(1) is not None:  # Triple
            replacement = f"{s_tag}{m.group(1)}{e_tag}"
            # log.info(f"Matched 3bq")
            return replacement
        elif m.group(2) is not None:  # Single
            content = m.group(2).replace('\n', '')  # Get the content and strip the newline
            replacement = f"{s_tag}{content}{e_tag}"
            # log.info(f"Matched 1bq")
            return replacement
        else:
            pass
            # log.info(f"No bq match found. can we even get here?")


    @classmethod
    def blockquote(cls, _input: str) -> Tuple[str, int]:
        output = cls.blockQuote_pattern.subn(cls.blockquote_repl, _input)
        return output


    @classmethod
    def remove_suppressed_embed_arrows(cls, _input: str) -> str:
        # s_tag = '<span class="spoiler">'
        # e_tag = "</span>"
        repl = r"\g<content>"
        output = cls.suppresed_embed_link_pattern.sub(repl, _input)
        return output


    @classmethod
    def linkify_repl(cls, m: Match):
        s_tag = '<a href="'
        m_tag = '">'
        e_tag = "</a>"

        if m.group(3) is not None:  # Normal Web Link
            replacement = f"{s_tag}{m.group(3)}{m_tag}{m.group(3)}{e_tag}"
            return replacement
        elif m.group(2) is not None:  # Inline link
            replacement = f"{s_tag}{m.group(2)}{m_tag}{m.group(1)}{e_tag}"
            # log.info(f"Matched 1bq")
            return replacement
        else:
            log.warning("No linkify_repl match???")

    @classmethod
    def linkify(cls, _input: str) -> str:

        output = cls.web_link_pattern.sub(cls.linkify_repl, _input)
        return output


    @classmethod
    def emojify_repl(cls, m: Match):
        # animated, name, id
        s_tag = '<img class="emoji" alt="'

        m1_tag = '" title="'
        m2_tag = '" src="'
        e_tag = '">'
        if m.group('animated'):
            # animated emoji
            emoji_url = f"https://cdn.discordapp.com/emojis/{m.group('id')}.gif"
        else:
            emoji_url = f"https://cdn.discordapp.com/emojis/{m.group('id')}.png"

        replacement = f"{s_tag}{m.group('name')}{m1_tag}{m.group('name')}{m2_tag}{emoji_url}{e_tag}"
        return replacement


    @classmethod
    def wombojify_repl(cls, m: Match):
        s_tag = '<img class="emoji emoji--large" alt="'

        m1_tag = '" title="'
        m2_tag = '" src="'
        e_tag = '">'
        if m.group('animated'):
            # animated emoji
            emoji_url = f"https://cdn.discordapp.com/emojis/{m.group('id')}.gif"
        else:
            emoji_url = f"https://cdn.discordapp.com/emojis/{m.group('id')}.png"

        replacement = f"{s_tag}{m.group('name')}{m1_tag}{m.group('name')}{m2_tag}{emoji_url}{e_tag}"
        return replacement


    @classmethod
    def emojify(cls, _input: str, original_txt: str) -> str:
        womboji = True
        # check if we need big or small emoji:
        womboji_matchs: List[Tuple[str, str]] = cls.womboji_pattern.findall(original_txt)

        for match in womboji_matchs:
            if match[0] != '' or match[1] != '':
                womboji = False
                break

        if womboji:
            output = cls.nitro_emote_pattern.sub(cls.wombojify_repl, _input)
        else:
            output = cls.nitro_emote_pattern.sub(cls.emojify_repl, _input)

        return output


    @classmethod
    def markdown(cls, _input: str) -> str:
        output = _input
        # First ensure the input is "safe"
        output = escape(_input)

        # CODE BLOCKS MUST BE FIRST
        output, count = cls.codeblock(output)  # Codeblock MUST be before inline codeblocks
        output, count = cls.inline_codeblock(output)  # inline Codeblock MUST be next

        output = cls.remove_suppressed_embed_arrows(output)
        output, count = cls.blockquote(output)
        output, count = cls.spoiler(output)
        output, count = cls.strikethrough(output)
        output, count = cls.bold(output)
        output, count = cls.underline(output)
        output, count = cls.italics(output)
        output = cls.linkify(output)
        output = cls.emojify(output, _input)

        # UNESCAPING MUST BE LAST
        output = cls.remove_escaped_symbol(output)

        return output


markdown = DiscordMarkdown()
