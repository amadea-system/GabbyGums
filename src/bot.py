"""

"""
import sys
import logging
import traceback
from typing import Optional, Dict, Tuple, List, Union

import discord
from discord.ext import commands, tasks
import asyncpg

import db
from utils.errors import handle_permissions_error
from miscUtils import log_error_msg

log = logging.getLogger(__name__)

extensions = (
    # -- Command Extensions -- #
    'cmds.configuration',
    'cmds.dev',
    'cmds.helpCmd',
    'cmds.inviteManagement',
    'cmds.utilities',

    # -- Event Extensions -- #
    'events.bulkMessageDelete',
    'events.channelEvents',
    'events.inviteEvents',
    'events.memberBans',
    'events.memberJoinLeave',
    'events.memberUpdate',
    'events.messageDelete',
    'events.messageEdit',
    'events.userUpdate',
)


class GGBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pk_id: int = 466378653216014359  # Plural Kit's Account ID.
        self.db_pool: Optional[asyncpg.pool.Pool] = None
        self.config: Optional[Dict] = None
        self.hmac_key: Optional[bytes] = None
        # self.alerted_guilds: List[Tuple[str, int]] = []  # Stores a list of guilds that have been alerted to permission problems.
        self.has_permission_problems: List[int] = []
        self.invites_initialized = False

        self.update_playing.start()


    def load_cogs(self):
        for extension in extensions:
            try:
                self.load_extension(extension)
                log.info(f"Loaded {extension}")
            except Exception as e:
                log.info(f'Failed to load extension {extension}.', file=sys.stderr)
                traceback.print_exc()


    async def send_log(self, log_ch: discord.TextChannel, event_type: str, embed: Optional[discord.Embed] = None, file: Optional[discord.File] = None) -> discord.Message:
        log.info(f"sending {event_type} to {log_ch.name}")
        try:
            msg = await log_ch.send(embed=embed, file=file)
            return msg
        except discord.Forbidden as e:
            await handle_permissions_error(self, log_ch, event_type, e, None)
            # await alert_guild_permissions_error(self, log_ch, event_type, e, None)


    # region Now Playing Update Task Methods
    # noinspection PyCallingNonCallable
    @tasks.loop(minutes=30)
    async def update_playing(self):
        log.info("Updating now Playing...")
        await self.set_playing_status()


    @update_playing.before_loop
    async def before_update_playing(self):
        await self.wait_until_ready()


    async def set_playing_status(self):
        activity = discord.Game("{}help | in {} Servers".format(self.command_prefix, len(self.guilds)))
        await self.change_presence(status=discord.Status.online, activity=activity)

    # endregion

    # region Get Logging Channel Methods

    async def get_event_or_guild_logging_channel(self, guild_id: int, event_type: Optional[str] = None, user_id: Optional[int] = None) -> Optional[discord.TextChannel]:

        # Check if there are any user overrides.
        if user_id is not None:
            has_override, override_ch_id = await self.check_user_overrides(guild_id, user_id)
            if has_override:
                return await self.get_channel_safe(override_ch_id) if override_ch_id is not None else None

        if event_type is not None:
            log_configs = await db.get_server_log_configs(self.db_pool, guild_id)
            event_configs = log_configs[event_type]
            if event_configs is not None:
                if event_configs.enabled is False:
                    return None  # Logs for this type are disabled. Exit now.
                if event_configs.log_channel_id is not None:
                    return await self.get_channel_safe(event_configs.log_channel_id)  # return event specific log channel

        # No valid event specific configs exist. Attempt to use default log channel.
        _log_channel_id = await db.get_log_channel(self.db_pool, guild_id)
        if _log_channel_id is not None:
            return await self.get_channel_safe(_log_channel_id)

        # No valid event configs or global configs found. Only option is to silently fail
        return None


    async def get_channel_safe(self, channel_id: int) -> Optional[discord.TextChannel]:
        channel = self.get_channel(channel_id)
        if channel is None:
            log.info("bot.get_channel failed. Querying API...")
            try:
                channel = await self.fetch_channel(channel_id)
            except discord.NotFound:
                return None
        return channel
    # endregion

    # region User/Chan/Cat Ignored Checkers


    async def is_channel_ignored(self, guild_id: int, channel_id: int) -> bool:
        _ignored_channels = await db.get_ignored_channels(self.db_pool, int(guild_id))
        if int(channel_id) in _ignored_channels:
            return True
        return False


    async def check_user_overrides(self, guild_id: int, user_id: int) -> Tuple[bool, Optional[int]]:
        """
        Check to see if the user is configures to be ignored or redirected

        Returns (True, None) if the user is ignored
        Returns (True, TextChannel_ID) if the user is redirected
        Returns (False, None) If there are no overrides at all
        """
        guild_id = int(guild_id)
        user_id = int(user_id)
        user_overrides = await db.get_users_overrides(self.db_pool, guild_id)
        for user in user_overrides:
            if user['user_id'] == user_id:
                return True, user['log_ch']
        return False, None


    async def is_category_ignored(self, guild_id: int, category: Optional[discord.CategoryChannel]) -> bool:
        if category is not None:  # If channel is not in a category, don't bother querying DB
            _ignored_categories = await db.get_ignored_categories(self.db_pool, int(guild_id))
            if category.id in _ignored_categories:
                return True
        return False
    # endregion


    async def is_pk_here(self, guild: discord.Guild) -> bool:
        """Checks if Plural Kit exists on the server. Returns bool"""

        pk_user: Union[discord.User, discord.Member] = guild.get_member(self.pk_id)
        if pk_user is not None:
            log.info(f"Found PK with get in {guild.name} ({guild.id})")
            return True

        # Couldn't find PK in cache, attempting fetch.
        try:
            pk_user = await guild.fetch_member(self.pk_id)
            if pk_user is not None:
                await log_error_msg(self, f"Found PK with **Fetch** in {guild.name} ({guild.id})")
                return True

        except discord.NotFound:
            await log_error_msg(self, f"Could not find pk in {guild.name} ({guild.id})")
            return False


