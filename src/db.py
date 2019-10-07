"""
For use with Gabby Gums

"""


import logging
import functools
from dataclasses import dataclass, field
from typing import List, Optional
import time


import asyncio
import asyncpg
from discord import Invite


async def create_db_pool(uri: str) -> asyncpg.pool.Pool:

    # FIXME: Error Handling
    return await asyncpg.create_pool(uri)


def db_deco(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            response = await func(*args, **kwargs)
            end_time = time.perf_counter()
            logging.info("DB Query {} from {} in {:.3f} ms.".format(func.__name__, args[1], (end_time - start_time) * 1000))

            return response
        except asyncpg.exceptions.PostgresError:
            logging.exception("Error attempting database query: {} for server: {}".format(func.__name__, args[1]))
    return wrapper


async def ensure_server_exists(conn, sid: int):
    # TODO: Add name as well.
    response = await conn.fetchval("select exists(select 1 from servers where server_id = $1)", sid)
    if response is False:
        logging.warning("SERVER {} WAS NOT IN DB. ADDING WITHOUT NAME!".format(sid))
        await conn.execute(
            "INSERT INTO servers(server_id, server_name) VALUES($1, $2)",
            sid, "NOT_AVAILABLE")
    return response


@db_deco
async def add_server(pool, sid: int, name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO servers(server_id, server_name) VALUES($1, $2)",
            sid, name)


@db_deco
async def remove_server(pool, sid: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM servers WHERE server_id = $1", sid)


@db_deco
async def update_server_name(pool, sid: int, name: str):
    async with pool.acquire() as conn:
        await ensure_server_exists(conn, sid)
        await conn.execute("UPDATE servers SET server_name = $1 WHERE server_id = $2", name, sid)


@db_deco
async def update_log_channel(pool, sid: int, log_channel_id: int = None):  # Good
    async with pool.acquire() as conn:
        await ensure_server_exists(conn, sid)
        await conn.execute("UPDATE servers SET log_channel_id = $1 WHERE server_id = $2", log_channel_id, sid)


@db_deco
async def get_log_channel(pool, sid: int) -> Optional[int]:  # Good
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT log_channel_id FROM servers WHERE server_id = $1', sid)
        return row['log_channel_id'] if row else None


@db_deco
async def update_log_enabled(pool, sid: int, log_enabled: bool):
    async with pool.acquire() as conn:
        await ensure_server_exists(conn, sid)
        await conn.execute("UPDATE servers SET logging_enabled = $1 WHERE server_id = $2", log_enabled, sid)


@db_deco
async def add_ignored_user(pool, sid: int, ignored_user_id: int):  # Good
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO ignored_users(user_id, server_id) VALUES($1, $2)", ignored_user_id, sid)


@db_deco
async def remove_ignored_user(pool, sid: int, ignored_user_id: int):  # Good
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM ignored_users WHERE server_id = $1 AND user_id = $2", sid, ignored_user_id)


@db_deco
async def get_ignored_users(pool, sid: int) -> List[int]:  # Good
    async with pool.acquire() as conn:
        # TODO: Optimise by replacing * with user_id
        raw_rows = await conn.fetch('SELECT * FROM ignored_users WHERE server_id = $1', sid)
        rows = [row["user_id"] for row in raw_rows]
    return rows


@db_deco
async def add_ignored_channel(pool, sid: int, ignored_channel_id: int):  # Good
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO ignored_channels(channel_id, server_id) VALUES($1, $2)", ignored_channel_id, sid)


@db_deco
async def remove_ignored_channel(pool, sid: int, ignored_channel_id: int):  # Good
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM ignored_channels WHERE server_id = $1 AND channel_id = $2", sid, ignored_channel_id)


@db_deco
async def get_ignored_channels(pool, sid: int) -> List[int]:  # Good
    async with pool.acquire() as conn:
        # TODO: Optimise by replacing * with channel_id
        raw_rows = await conn.fetch('SELECT * FROM ignored_channels WHERE server_id = $1', sid)
        rows = [row["channel_id"] for row in raw_rows]
    return rows


@db_deco
async def store_invite(pool, sid: int, invite_id: str, invite_uses: int = 0):
    async with pool.acquire() as conn:
        does_exist = await conn.fetchval("select exists(select 1 from invites where server_id = $1 and invite_id = $2)", sid, invite_id)
        if does_exist is False:
            await add_new_invite(pool, sid, invite_id, invite_uses)
        else:
            await update_invite_uses(pool, sid, invite_id, invite_uses)


async def add_new_invite(pool, sid: int, invite_id: str, invite_uses: int = 0):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO invites(server_id, invite_id, uses) VALUES($1, $2, $3)", sid, invite_id, invite_uses)


async def update_invite_uses(pool, sid: int, invite_id: str, invite_uses: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE invites SET uses = $1 WHERE server_id = $2 AND invite_id = $3", invite_uses, sid, invite_id)


@db_deco
async def update_invite_name(pool, sid: int, invite_id: str, invite_name: Optional[str] = None):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE invites SET invite_name = $1 WHERE server_id = $2 AND invite_id = $3", invite_name, sid, invite_id)

@db_deco
async def remove_invite(pool, sid, invite_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM invites WHERE server_id = $1 AND invite_id = $2", sid, invite_id)


@dataclass
class StoredInvite:
    server_id: int
    invite_id: str
    uses: int
    id: Optional[int] = None
    invite_name: Optional[str] = None
    invite_desc: Optional[str] = None
    actual_invite: Optional[Invite] = None


@dataclass
class StoredInvites:
    invites: List[StoredInvite] = field(default_factory=[])

    def find_invite(self, invite_id: str) -> Optional[StoredInvite]:
        for invite in self.invites:
            if invite.invite_id == invite_id:
                return invite

        return None


@db_deco
async def get_invites(pool, sid: int) -> StoredInvites:
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch('SELECT * FROM invites WHERE server_id = $1', sid)
        #Fixme: Does fetch return None or 0 length list when no entries are found?
        return StoredInvites(invites=[StoredInvite(**row) for row in raw_rows])


@db_deco
async def fetch_full_table(pool, table: str) -> List[int]:  # good
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch('SELECT * FROM {}'.format(table))
    return raw_rows


async def create_tables(pool):
    # Create servers table
    async with pool.acquire() as conn:
        await conn.execute('''
                           CREATE TABLE if not exists servers(
                               server_id BIGINT PRIMARY KEY,
                               server_name TEXT,
                               log_channel_id BIGINT,
                               logging_enabled BOOLEAN NOT NULL DEFAULT TRUE
                           )
                       ''')

        # Create ignored_channels table
        await conn.execute('''
                           CREATE TABLE if not exists ignored_channels(
                                id SERIAL PRIMARY KEY,
                                server_id BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                                channel_id BIGINT NOT NULL,
                                UNIQUE (server_id, channel_id)
                           )
                       ''')

        # Create ignored_users table
        await conn.execute('''
                               CREATE TABLE if not exists ignored_users(
                                    id           SERIAL PRIMARY KEY,
                                    server_id    BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE, 
                                    user_id      BIGINT NOT NULL,
                                    UNIQUE (server_id, user_id)
                               )
                           ''')

        # Create invites table
        # Will need to execute "ALTER TABLE invites ADD UNIQUE (server_id, invite_id)" to alter the existing production table
        await conn.execute('''
                              CREATE TABLE if not exists invites(
                                  id            SERIAL PRIMARY KEY,
                                  server_id     BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                                  invite_id     TEXT NOT NULL,
                                  uses          INTEGER NOT NULL DEFAULT 0,
                                  invite_name   TEXT,
                                  invite_desc   TEXT,
                                  UNIQUE (server_id, invite_id)
                              )
                          ''')

        # Create username_tracking table
        await conn.execute('''
                           CREATE TABLE if not exists past_names(
                               id           SERIAL PRIMARY KEY,
                               server_id    BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                               user_id      BIGINT NOT NULL,
                               name         TEXT,
                               discriminator SMALLINT,
                               nickname     TEXT
                           )
                       ''')



