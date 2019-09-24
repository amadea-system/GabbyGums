"""
For use with Gabby Gums

"""


import logging
import functools
from typing import List, Optional
import time


import asyncio
import asyncpg


async def create_db_pool(uri: str) -> asyncpg.pool.Pool:

    # FIXME: Error Handling
    return await asyncpg.create_pool(uri)

#
# def pool_to_conn(func):
#     async def wrapper(pool, )


def db_deco(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            response = await func(*args, **kwargs)
            end_time = time.perf_counter()
            logging.info("DB Query {} in {:.3f} ms.".format(func.__name__, (end_time - start_time) * 1000))
            return response
        except asyncpg.exceptions.PostgresError:
            logging.exception("Error attempting database query: {}".format(func.__name__))
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
        await conn.execute('''
                              CREATE TABLE if not exists invites(
                                  id            SERIAL PRIMARY KEY,
                                  server_id     BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                                  invite_id     TEXT NOT NULL,
                                  uses          INTEGER NOT NULL DEFAULT 0,
                                  invite_name   TEXT,
                                  invite_desc   TEXT
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

