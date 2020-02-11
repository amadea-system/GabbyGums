"""


"""

import discord
from discord.ext import commands

import asyncio
import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Callable, Any
from fuzzywuzzy import process


class InvalidInput(Exception):
    pass


class DiscordPermissionsError(Exception):
    pass


class AddReactionsError(DiscordPermissionsError):
    def __init__(self):
        super().__init__(f"Insufficient permissions to add reactions to user interface!\nPlease have an admin add the **Add Reactions** and **Read Message History** permissions to this bot.")


async def do_nothing(*args, **kwargs):
    pass


class Page:
    """
    An interactive form that can be interacted with in a variety of ways including Boolean reaction, string input, non-interactive response message, soon to be more.
    Calls a Callback with the channel and response data to enable further response and appropriate handling of the data.
    """
    LOG = logging.getLogger("GGBot.Page")

    def __init__(self, page_type: str, name: Optional[str] = None, body: Optional[str] = None,
                 callback: Callable = do_nothing, additional: str = None, embed: Optional[discord.Embed] = None, previous_page: Optional = None, timeout: int = 120.0):
        # self.header_name = header_name
        # self.header_body = header_body
        self.name = name
        self.body = body
        self.additional = additional
        self.embed = embed
        self.timeout = timeout

        self.page_type = page_type.lower()
        self.callback = callback
        self.response = None
        self.previous = previous_page
        self.page_message: Optional[discord.Message] = None
        self.user_message: Optional[discord.Message] = None

    async def run(self, ctx: commands.Context):
        client = ctx.bot

        if self.page_type == "bool":
            await self.run_boolean(client, ctx)
        elif self.page_type == "str":
            await self.run_string(client, ctx)
        # elif self.page_type == "simple":
        #     await self.run_simple_response(client, ctx)
        # elif self.page_type == "custom":
        #     await self.run_custom_response(client, ctx)

        self.LOG.info("Ran {}".format(self.name))

    async def run_boolean(self, client: commands.Bot, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: bool
        """
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        page_message = await channel.send(self.construct_std_page_msg())
        self.page_message = page_message

        try:
            await page_message.add_reaction("✅")
            await page_message.add_reaction("❌")
        except discord.Forbidden as e:
            await ctx.send(f"CRITICAL ERROR!!! \n{ctx.guild.me.name} does not have the `Add Reactions` permissions!. Please have an Admin fix this issue and try again.")
            raise e

        def react_check(_reaction: discord.Reaction, _user):
            self.LOG.info("Checking Reaction: Reacted Message: {}, orig message: {}".format(_reaction.message.id, page_message.id))

            return _user == ctx.author and (str(_reaction.emoji) == '✅' or str(_reaction.emoji) == '❌')

        try:
            reaction, react_user = await client.wait_for('reaction_add', timeout=self.timeout, check=react_check)
            if str(reaction.emoji) == '✅':
                self.response = True
                await self.remove()
                await self.callback(self, client, ctx, True)
            elif str(reaction.emoji) == '❌':
                self.response = False
                await self.remove()
                await self.callback(self, client, ctx, False)

        except asyncio.TimeoutError:
            await self.remove()

    async def run_string(self, client: commands.Bot, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: discord.Message
        """
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        if self.embed is None:
            self.page_message = await channel.send(self.construct_std_page_msg())
        else:
            self.page_message = await channel.send(self.construct_std_page_msg(), embed=self.embed)

        def message_check(_msg: discord.Message):
            # self.LOG.info("Checking Message: Reacted Message: {}, orig message: {}".format(_reaction.message.id,
            #                                                                                 page_message.id))
            return _msg.author == author and _msg.channel == channel

        try:
            user_msg: discord.Message = await client.wait_for('message', timeout=self.timeout, check=message_check)
            self.user_message = user_msg
            self.response = user_msg
            await self.remove()
            await self.callback(self, client, ctx, user_msg)

        except asyncio.TimeoutError:
            # await ctx.send("Command timed out.")
            await self.remove()


    def construct_std_page_msg(self) -> str:
        page_msg = ""
        if self.name is not None:
            page_msg += "**{}**\n".format(self.name)

        if self.body is not None:
            page_msg += "{}\n".format(self.body)

        if self.additional is not None:
            page_msg += "{}\n".format(self.additional)

        # self.page_message = page_message
        return page_msg

    @staticmethod
    async def cancel(ctx, self):
        await self.remove()
        await ctx.send("Canceled!")

    async def remove(self, user: bool = True, page: bool = True):

        if self.previous is not None:
            await self.previous.remove(user, page)

        try:
            if user and self.user_message is not None:
                await self.user_message.delete(delay=1)
        except Exception:
            pass

        try:
            if page and self.page_message is not None:
                await self.page_message.delete(delay=1)
        except Exception:
            pass


class StringPage(Page):

    def __init__(self, allowable_responses: List[str], cancel_btn=True, **kwrgs):
        """
        Callback signature: ctx: commands.Context, page: reactMenu.Page
        """
        self.ctx = None
        self.match = None
        self.cancel_btn = cancel_btn
        self.allowable_responses = allowable_responses
        self.canceled = False

        super().__init__(page_type="n/a", **kwrgs)

    async def run(self, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page
        """
        self.ctx = ctx
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        if self.embed is None:
            self.page_message = await channel.send(self.construct_std_page_msg())
        else:
            self.page_message = await channel.send(self.construct_std_page_msg(), embed=self.embed)

        # self.page_message: discord.Message = await channel.send(embed=self.embed)
        if self.cancel_btn:
            await self.page_message.add_reaction("❌")

        # def message_check(_msg: discord.Message):
        #     # self.LOG.info("Checking Message: Reacted Message: {}, orig message: {}".format(_reaction.message.id,
        #     #                                                                                 page_message.id))
        #     return _msg.author == author and _msg.channel == channel

        try:
            done, pending = await asyncio.wait([
                self.ctx.bot.wait_for('message', timeout=self.timeout, check=self.msg_check),
                self.ctx.bot.wait_for('raw_reaction_add', timeout=self.timeout, check=self.react_check)
            ], return_when=asyncio.FIRST_COMPLETED)

            try:
                stuff = done.pop().result()

            except Exception as e:
                self.LOG.exception(e)
            # if any of the tasks died for any reason,
            #  the exception will be replayed here.

            for future in pending:
                future.cancel()  # we don't need these anymore

            if self.canceled:
                await self.remove()
                await ctx.send("Done!")
                return None
            else:
                await self.remove()
                return self.response

            # await self.callback(self)

        except asyncio.TimeoutError:
            # await ctx.send("Command timed out.")
            await self.remove()
            await ctx.send("Timed Out!")
            return None


    def react_check(self, payload):
        """Uses raw_reaction_add"""
        if not self.cancel_btn:
            return False
        if payload.user_id != self.ctx.author.id:
            return False

        if payload.message_id != self.page_message.id:
            return False

        if "❌" == str(payload.emoji):
            self.canceled = True
            return True

        return False

    def msg_check(self, _msg: discord.Message):
        """Uses on_message"""
        if not self.cancel_btn:
            return False
        if _msg.author.id != self.ctx.author.id:
            return False

        if _msg.channel.id != self.page_message.channel.id:
            return False

        if len(self.allowable_responses) > 0:
            self.LOG.info(f"Got: {_msg}")
            if _msg.content.lower().strip() in self.allowable_responses:
                self.response = _msg.content.lower().strip()
                self.LOG.info(f"returning: true")
                return True
        else:
            return True

        return False


class StringReactPage(Page):

    def __init__(self, buttons: List[Tuple[Union[discord.PartialEmoji, str], Any]] = None, allowable_responses: List[str] = None, cancel_btn=True, **kwrgs):
        """
        Callback signature: ctx: commands.Context, page: reactMenu.Page
        """
        self.ctx = None
        self.match = None
        self.cancel_btn = cancel_btn
        self.allowable_responses = allowable_responses or []
        self.canceled = False
        self.buttons = buttons or []
        self.sent_msg = []

        if self.cancel_btn:
            self.buttons.append(("❌", None))

        super().__init__(page_type="n/a", **kwrgs)

    async def run(self, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page
        """
        self.ctx = ctx
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        if self.embed is None:
            self.page_message = await channel.send(self.construct_std_page_msg())
        else:
            self.page_message = await channel.send(self.construct_std_page_msg(), embed=self.embed)

        self.sent_msg.append(self.page_message)

        # self.page_message: discord.Message = await channel.send(embed=self.embed)
        # if self.cancel_btn:
        #     await self.page_message.add_reaction("❌")

        for (reaction, _) in self.buttons:
            try:
                await self.page_message.add_reaction(reaction)
            except discord.Forbidden:
                raise AddReactionsError()

        # def message_check(_msg: discord.Message):
        #     # self.LOG.info("Checking Message: Reacted Message: {}, orig message: {}".format(_reaction.message.id,
        #     #                                                                                 page_message.id))
        #     return _msg.author == author and _msg.channel == channel
        while True:

            done, pending = await asyncio.wait([
                self.ctx.bot.wait_for('message', timeout=self.timeout, check=self.msg_check),
                self.ctx.bot.wait_for('raw_reaction_add', timeout=self.timeout, check=self.react_check)
            ], return_when=asyncio.FIRST_COMPLETED)

            try:
                stuff = done.pop().result()

            except asyncio.TimeoutError:
                # await ctx.send("Command timed out.")
                await self.remove()
                await ctx.send("Timed Out!")
                return None

            except Exception as e:
                self.LOG.exception(e)
            # if any of the tasks died for any reason,
            #  the exception will be replayed here.

            for future in pending:
                future.cancel()  # we don't need these anymore

            if self.canceled:
                await self.remove()
                await ctx.send("Done!")
                return None

            if self.match is not None and len(self.allowable_responses) > 0:
                # self.LOG.info(f"Got: {self.match}")
                if self.match not in self.allowable_responses:
                    content = self.match
                    possible_match = process.extractOne(content, self.allowable_responses, score_cutoff=50)
                    best_match = possible_match[0] if possible_match else None
                    did_you_mean = f"\nDid you mean:" if best_match else ""
                    self.sent_msg.append(await self.ctx.send(f"`{content}` is not a valid choice. Please try again.{did_you_mean}"))

                    if best_match:
                        self.sent_msg.append(await self.ctx.send(f"{best_match}"))  # Send as it's own msg so it's easy to copy and paste.

                    # Force match and canceled to be None/False to loop around and let the user try again.
                    self.match = None
                    self.canceled = False

            if self.match is not None:
                if callable(self.match):
                    await self.match(self.ctx, self)

                await self.remove()
                return self.match


    def react_check(self, payload):
        """Uses raw_reaction_add"""
        if not self.cancel_btn:
            return False
        if payload.user_id != self.ctx.author.id:
            return False

        if payload.message_id != self.page_message.id:
            return False

        if "❌" == str(payload.emoji):
            self.canceled = True
            return True

        to_check = str(payload.emoji)
        for (emoji, func) in self.buttons:
            if to_check == emoji:
                self.match = func
                # self.match = emoji
                return True

        return False

    def msg_check(self, _msg: discord.Message):
        """Uses on_message"""

        if _msg.author.id != self.ctx.author.id:
            return False

        if _msg.channel.id != self.page_message.channel.id:
            return False

        self.LOG.info(f"returning: true. content: {_msg.content}")
        self.match = _msg.content.lower().strip()
        return True

        # return False


    async def remove(self, user: bool = True, page: bool = True):

        if self.previous is not None:
            await self.previous.remove(user, page)

        try:
            if user and self.user_message is not None:
                await self.user_message.delete(delay=1)
        except Exception:
            pass

        try:
            for msg in self.sent_msg:
                if page and msg is not None:
                    await msg.delete(delay=1)

        except Exception:
            pass
