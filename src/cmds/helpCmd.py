"""
Extension that implements a custom Embed based help system.
Currently supports:
    General Help Page

Help System Convention: prefix[command_name|alias1|alias...] <req_arg> [opt_arg]

Part of the Gabby Gums Discord Logger.
"""

import logging
import itertools

import discord
from discord.ext import commands as dpy_cmds

from miscUtils import split_text

log = logging.getLogger(__name__)

support_link = "https://discord.gg/3Ugade9"


class EmbedHelp(dpy_cmds.DefaultHelpCommand):

    async def send_bot_help(self, mapping):
        ctx: dpy_cmds.Context = self.context
        bot: dpy_cmds.Bot = ctx.bot
        dest: discord.abc.Messageable = self.get_destination()

        # TODO: Move this to the error handler.
        permissions: discord.Permissions = ctx.guild.me.permissions_in(dest)
        if not permissions.embed_links:
            await dest.send(f"Error! Gabby Gums must have the `Embed Links` permission in this channel to continue. Please give Gabby Gums the `Embed Links` permission and try again."
                            f"\nIf you need assistance, please join our support server @ {support_link} and we will be happy to help you.")
            return

        embed = discord.Embed(title='Gabby Gums Help', color=0x9932CC)

        embed.add_field(name="Who can use Gabby Gums",
                        value="Anyone!\n"
                              "Regardless of system type or plurality, all people are valid. "
                              "As such, all people are allowed to use this bot.\n")
        embed.add_field(name="Support Server",
                        value="For support, suggestions, just want to chat with someone, "
                              f"or anything else, feel free to join our support server @ {support_link}")

        embed.set_footer(text="Created by Luna, Hibiki, and Fluttershy aka Amadea System (Hibiki#8792) "
                              "| Github: https://github.com/amadea-system/GabbyGums/")

        no_category = '\u200b{0.no_category}:'.format(self)

        def get_category(command, *, no_category=no_category):
            cog = command.cog
            return cog.qualified_name + ':' if cog is not None else no_category


        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        max_size = self.get_max_size(filtered)
        to_iterate = itertools.groupby(filtered, key=get_category)

        # Now we can add the commands to the page.
        for category, commands in to_iterate:
            commands = sorted(commands, key=lambda c: c.name) if self.sort_commands else list(commands)

            field_values = []
            get_width = discord.utils._string_width  # TODO: Don't use protected member.
            for command in commands:
                width = max_size - (get_width(command.name) - len(command.name))
                entry = '{0}`{1:<{width}}`\N{EM QUAD}{2}'.format(self.indent * ' ', command.name, command.short_doc, width=width)
                field_values.append(self.shorten_text(entry))

            field_values = split_text(field_values, max_size=1000)
            for i, field_value in enumerate(field_values):
                name = category if i == 0 else "\N{Zero Width Space}"
                embed.add_field(name=name, value=f"{field_value}", inline=False)

        note = self.get_ending_note()
        if note:
            embed.add_field(name="\N{Zero Width Space}", value=note)

        await dest.send(embed=embed)


def setup(bot):
    bot.help_command = EmbedHelp(width=100, indent=0, no_category="Everything Else")