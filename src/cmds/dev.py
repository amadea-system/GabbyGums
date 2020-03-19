"""
Cog containing various developer only commands used for debugging purposes only.
Commands include:
    devtest
    dump
    past_messages

Part of the Gabby Gums Discord Logger.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import discord
from discord.ext import commands
import eCommands

import db
import miscUtils
from utils.paginator import FieldPages

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)


class Dev(commands.Cog):
    def __init__(self, bot: 'GGBot'):
        self.bot = bot


    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    # ----- Debugging Commands ----- #

    @commands.guild_only()
    @eCommands.group(brief="Owner only test command")
    async def devtest(self, ctx: commands.Context):
        await ctx.send(f"hello from {__name__}")


    @commands.command(name="dump")
    async def dump(self, ctx: commands.Context, table: str):

        await ctx.send("DB Dump for {}".format(table))
        table_msg = "```python\n"
        rows = await db.fetch_full_table(self.bot.db_pool, table)

        for row in rows:
            table_msg = table_msg + str(row) + "\n"
        table_msg = table_msg + "```"
        await ctx.send(table_msg[len(table_msg) - 2000:len(table_msg)] if len(table_msg) > 2000 else table_msg)


    @commands.command(name="messages")
    async def past_messages(self, ctx: commands.Context, hours: int, _max: int = 15):
        # This command is limited only to servers that we are Admin/Owner of for privacy reasons.

        rows = await db.get_cached_messages_older_than(self.bot.db_pool, hours)
        rows = rows[len(rows) - _max:len(rows)] if len(rows) > _max else rows
        await ctx.send("Dumping the last {} records over the last {} hours".format(len(rows), hours))
        for row in rows:
            log_msg = f"mid: {row['message_id']}, sid: {row['server_id']}, uid: {row['user_id']}, " \
                f"ts: {row['ts'].strftime('%b %d, %Y, %I:%M:%S %p UTC')} webhookun: {row['webhook_author_name']}, " \
                f"system_pkid: {row['system_pkid']}, member_pkid: {row['member_pkid']}, " \
                f"PK Account: <@{row['pk_system_account_id']}> message: \n**{row['content']}**"

            logging.info(log_msg)
            await miscUtils.send_long_msg(ctx, log_msg)
            await asyncio.sleep(1)

    @commands.command(name="has_pk")
    async def has_pk(self, ctx: commands.Context):
        """This command is to show if there have been any failures in detecting PK in servers that do have PK.
        It is being used to ensure that the GGBot.is_pk_here method works 100% before actually using it to prevent disruptions to logging"""
        embed_entries = []
        problems = []
        has_pk_stats = self.bot.has_pk_cache

        for key, value in has_pk_stats.items():
            header = f"{key}"

            get = 0
            fetch = 0
            no_pk = 0
            for item in value:
                if item == "get":
                    get += 1
                elif item == "fetch":
                    fetch += 1
                elif item == "no_pk":
                    no_pk += 1
                else:
                    log.warning(f"Unrecognized item in has pk cache: {item}")

            if (get > 0 or fetch > 0) and no_pk > 0:
                problems.append(header)

            msg = F"`Get:  ` {get}\n`Fetch:` {fetch}\n`No PK:` {no_pk}"
            embed_entries.append((header, msg))

        if len(problems) > 0:
            header = f"Problems Found:"
            msg = ", ".join(problems)
            embed_entries.insert(0, (header, msg))
        else:
            header = f"No Problems Found:"
            msg = "\N{Grinning Face}"
            embed_entries.insert(0, (header, msg))

        page = FieldPages(ctx, entries=embed_entries, per_page=25)
        page.embed.title = f"Has PK Check Stats:"
        await page.paginate()


def setup(bot):
    bot.add_cog(Dev(bot))
