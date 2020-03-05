"""
An in memory cache of all guild settings.
All DB Writes, Reads, and Updates must go through this class to ensure GG is interacting with fresh data.


Part of the Gabby Gums Discord Logger.
"""

import logging

from typing import TYPE_CHECKING, Union, Optional, Dict, List, Tuple, NamedTuple
import GuildConfigs

if TYPE_CHECKING:
    from bot import GGBot

log = logging.getLogger(__name__)



class GuildSettingsCache:

    def __init__(self, bot: 'GGBot'):
        self.bot = bot
        self.initialized = False
        self.configs: Dict[int, GuildConfigs.GuildLoggingConfig]
        self.default_log_ch: Dict[int, int]
        self.ignored_users: Dict[int, int]
        self.ignored_channels: Dict[int, int]
        self.ignored_category: Dict[int, int]


    async def init_cache(self):
        # Call DB calls that don't exist yet to fill up cache
        self.initialized = True





