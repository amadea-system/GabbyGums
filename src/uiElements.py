"""


"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple, Callable, Any

import discord
from discord.ext import commands

from fuzzywuzzy import process


class InvalidInput(Exception):
    pass


class DiscordPermissionsError(Exception):
    pass


class CannotAddReactions(DiscordPermissionsError):
    def __init__(self):
        super().__init__(f"Insufficient permissions to add reactions to user interface!\n"
                         f"Please have an admin add the **Add Reactions** and **Read Message History** permissions to this bot and make sure that the channel you are using commands in is configured to allow those permissions as well.")


class CannotEmbedLinks(DiscordPermissionsError):
    def __init__(self):
        super().__init__('Bot does not have embed links permission in this channel.')


class CannotSendMessages(DiscordPermissionsError):
    def __init__(self):
        super().__init__('Bot cannot send messages in this channel.')


class CannotAddExtenalReactions(DiscordPermissionsError):
    def __init__(self):
        super().__init__(f"Gabby Gums is missing the **Use External Emojis** Permission!\n"
                         f"Please have an admin add the **Use External Emojis** permissions to this bot and make sure that the channel you are using commands in is configured to allow External Emojis as well.")



async def do_nothing(*args, **kwargs):
    pass


@dataclass
class PageResponse:
    """Data Storage class for returning the user response (if any) and the UI Message(es) that the Page sent out."""
    response: Optional[Any]
    ui_message: Optional[discord.Message]
    # user_messages: List[discord.Message] = field(default_factory=[])

    def __str__(self):
        return str(self.content())

    def content(self):
        if isinstance(self.response, str):
            return self.response
        elif isinstance(self.response, discord.Message):
            return self.response.content
        else:
            return self.response

    def c(self):
        return self.content()


class Page:
    """
    An interactive form that can be interacted with in a variety of ways including Boolean reaction, string input, non-interactive response message, soon to be more.
    Calls a Callback with the channel and response data to enable further response and appropriate handling of the data.
    """
    LOG = logging.getLogger("GGBot.Page")

    def __init__(self, page_type: str, name: Optional[str] = None, body: Optional[str] = None,
                 callback: Callable = do_nothing, additional: str = None, embed: Optional[discord.Embed] = None, previous_msg: Optional[Union[discord.Message, PageResponse]] = None, timeout: int = 120.0):
        # self.header_name = header_name
        # self.header_body = header_body
        self.name = name
        self.body = body
        self.additional = additional
        self.embed = embed
        self.timeout = timeout

        self.page_type = page_type.lower()
        self.callback = callback
        self.prev = previous_msg.ui_message if isinstance(previous_msg, PageResponse) else previous_msg

        self.response = None
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

        # if self.previous is not None:
        #     await self.previous.remove(user, page)

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
    cancel_emoji = '🛑'
    def __init__(self, buttons: List[Tuple[Union[discord.PartialEmoji, str], Any]] = None, allowable_responses: List[str] = None, cancel_btn=True, edit_in_place=False, **kwrgs):
        """
        Callback signature: ctx: commands.Context, page: reactMenu.Page
        """
        self.ctx = None
        self.match = None
        self.cancel_btn = cancel_btn
        self.allowable_responses = allowable_responses or []
        self.edit_in_place = edit_in_place
        self.canceled = False
        self.buttons = buttons or []
        self.sent_msg = []

        if self.cancel_btn:
            self.buttons.append((self.cancel_emoji, None))

        super().__init__(page_type="n/a", **kwrgs)

    async def run(self, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page
        """
        self.ctx = ctx
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        await self.check_permissions()

        self.page_message = await self.send(self.construct_std_page_msg(), embed=self.embed)

        # self.sent_msg.append(self.page_message)

        # self.page_message: discord.Message = await channel.send(embed=self.embed)
        # if self.cancel_btn:
        #     await self.page_message.add_reaction("❌")

        for (reaction, _) in self.buttons:
            try:
                await self.page_message.add_reaction(reaction)
            except discord.Forbidden:
                raise CannotAddReactions()

        while True:

            done, pending = await asyncio.wait([
                self.ctx.bot.wait_for('raw_reaction_add', timeout=self.timeout, check=self.react_check),
                self.ctx.bot.wait_for('message', timeout=self.timeout, check=self.msg_check)
            ], return_when=asyncio.FIRST_COMPLETED)

            try:
                stuff = done.pop().result()

            except asyncio.TimeoutError:
                # await ctx.send("Command timed out.")
                await self.remove()
                # await ctx.send("Timed Out!")
                await ctx.send("Done!")
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
                    if content.startswith(ctx.bot.command_prefix):
                        self.sent_msg.append(
                            await self.ctx.send(f"It appears that you used a command while a menu system is still running. Disregarding the input."))
                    else:
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

                if not self._can_remove_reactions or not self.edit_in_place:  # If we can't remove the reactions, we'll just fall back to removing the message.
                    await self.remove()
                    # self.prev = None
                return PageResponse(response=self.match, ui_message=self.prev)


    def react_check(self, payload):
        """Uses raw_reaction_add"""
        if len(self.buttons) == 0:
            return False
        if payload.user_id != self.ctx.author.id:
            return False

        if payload.message_id != self.page_message.id:
            return False

        if self.cancel_emoji == str(payload.emoji):
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

    async def check_permissions(self):
        permissions = self.ctx.channel.permissions_for(self.ctx.guild.me)
        self._verify_permissions(self.ctx, permissions)
        #
        # if self.prev is None and not self._can_remove_reactions:
        #     # Only send this warning message the first time the menu system is activated.
        #     await self.ctx.send(f"\N{WARNING SIGN}\ufe0f Gabby Gums is missing the `Manage Messages` permission!\n"
        #                         f"While you can continue without giving Gabby Gums this permission, you will experience a suboptimal menu system experience.")

    def _verify_permissions(self, ctx, permissions):
        if not permissions.send_messages:
            raise CannotSendMessages()

        if self.embed is not None and not permissions.embed_links:
            raise CannotEmbedLinks()

        self._can_remove_reactions = permissions.manage_messages

        if len(self.buttons) > 0:
            if not permissions.add_reactions:
                raise CannotAddReactions()
            if not permissions.read_message_history:
                raise CannotAddReactions()
            if not permissions.external_emojis:
                raise CannotAddExtenalReactions()


    async def send(self, content: Optional[str] = None, embed: Optional[discord.Embed] = None) -> discord.Message:

        if self.prev and self._can_remove_reactions:
            await self.prev.edit(content=content, embed=embed)
        else:
            self.prev = await self.ctx.send(content=content, embed=embed)
            self.sent_msg.append(self.prev)
        return self.prev


    async def remove(self, user: bool = True, page: bool = True):

        # if self.previous is not None:
        #     await self.previous.remove(user, page)

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


class BoolPage(Page):

    def __init__(self, name: Optional[str] = None, body: Optional[str] = None,
                 callback: Callable = do_nothing, additional: str = None, embed: Optional[discord.Embed] = None, previous_msg: Optional[Union[discord.Message, PageResponse]] = None, timeout: int = 120.0):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: bool
        """
        self.ctx = None
        self.match = None
        self.canceled = False

        super().__init__(page_type="n/a", name=name, body=body, callback=callback, additional=additional, embed=embed, previous_msg=previous_msg, timeout=timeout)

    async def run(self, ctx: commands.Context):
        """
        Callback signature: page: reactMenu.Page, _client: commands.Bot, ctx: commands.Context, response: bool
        """
        self.ctx = ctx
        channel: discord.TextChannel = ctx.channel
        author: discord.Member = ctx.author
        message: discord.Message = ctx.message

        if self.embed is None:
            self.page_message = await channel.send(self.construct_std_page_msg())
        else:
            self.page_message = await channel.send(self.construct_std_page_msg(), embed=self.embed)

        try:
            await self.page_message.add_reaction("✅")
            await self.page_message.add_reaction("❌")
        except discord.Forbidden as e:
            await ctx.send(
                f"CRITICAL ERROR!!! \n{ctx.guild.me.name} does not have the `Add Reactions` permissions!. Please have an Admin fix this issue and try again.")
            raise e


        def react_check(_reaction: discord.Reaction, _user):
            self.LOG.info("Checking Reaction: Reacted Message: {}, orig message: {}".format(_reaction.message.id,
                                                                                            self.page_message.id))

            return _user == ctx.author and (str(_reaction.emoji) == '✅' or str(_reaction.emoji) == '❌')


        try:
            reaction, react_user = await self.ctx.bot.wait_for('reaction_add', timeout=self.timeout, check=react_check)
            if str(reaction.emoji) == '✅':
                self.response = True
                await self.remove()
                await self.callback(self, self.ctx.bot, ctx, True)
                return True
            elif str(reaction.emoji) == '❌':
                self.response = False
                await self.remove()
                await self.callback(self, self.ctx.bot, ctx, False)
                return False

        except asyncio.TimeoutError:
            await self.remove()
            return None


    # def react_check(self, payload):
    #     """Uses raw_reaction_add"""
    #
    #     if payload.user_id != self.ctx.author.id:
    #         return False
    #
    #     if payload.message_id != self.page_message.id:
    #         return False
    #
    #     if "❌" == str(payload.emoji):
    #         self.canceled = True
    #         return True
    #
    #     return False
