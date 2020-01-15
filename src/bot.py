"""

"""
from typing import Optional, Dict

from discord.ext import commands
import asyncpg


class GGBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_pool: Optional[asyncpg.pool.Pool] = None
        self.config: Optional[Dict] = None
