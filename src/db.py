"""
For use with Gabby Gums

"""


import logging
import functools
from dataclasses import dataclass, field
from typing import List, Optional
import time
from datetime import datetime, timedelta
import json

import asyncpg
from discord import Invite, Message
import GuildConfigs


async def create_db_pool(uri: str) -> asyncpg.pool.Pool:

    # FIXME: Error Handling
    async def init_connection(conn):
        await conn.set_type_codec('json',
                                  encoder=json.dumps,
                                  decoder=json.loads,
                                  schema='pg_catalog')

    pool: asyncpg.pool.Pool = await asyncpg.create_pool(uri, init=init_connection)

    return pool


def db_deco(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            response = await func(*args, **kwargs)
            end_time = time.perf_counter()
            if len(args) > 1:
                logging.info("DB Query {} from {} in {:.3f} ms.".format(func.__name__, args[1], (end_time - start_time) * 1000))
            else:
                logging.info("DB Query {} in {:.3f} ms.".format(func.__name__, (end_time - start_time) * 1000))
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
async def set_server_log_configs(pool, sid: int, log_configs: GuildConfigs.GuildLoggingConfig):
    async with pool.acquire() as conn:
        await ensure_server_exists(conn, sid)
        await conn.execute("UPDATE servers SET log_configs = $1 WHERE server_id = $2", log_configs.to_dict(), sid)


@db_deco
async def get_server_log_configs(pool, sid: int) -> GuildConfigs.GuildLoggingConfig:
    async with pool.acquire() as conn:
        value = await conn.fetchval('SELECT log_configs FROM servers WHERE server_id = $1', sid)
        # return GuildConfigs.load_nested_dict(GuildConfigs.GuildLoggingConfig, value) if value else GuildConfigs.GuildLoggingConfig()
        return GuildConfigs.GuildLoggingConfig.from_dict(value)

# ----- Ignored Users DB Functions ----- #

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


# ----- Ignored Channels DB Functions ----- #

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


# ----- Ignored Categories DB Functions ----- #

@db_deco
async def add_ignored_category(pool, sid: int, ignored_category_id: int):  # Good
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO ignored_category(category_id, server_id) VALUES($1, $2)", ignored_category_id, sid)


@db_deco
async def remove_ignored_category(pool, sid: int, ignored_category_id: int):  # Good
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM ignored_category WHERE server_id = $1 AND category_id = $2", sid, ignored_category_id)


@db_deco
async def get_ignored_categories(pool, sid: int) -> List[int]:  # Good
    async with pool.acquire() as conn:
        raw_rows = await conn.fetch('SELECT category_id FROM ignored_category WHERE server_id = $1', sid)
        category_ids = [row["category_id"] for row in raw_rows]
    return category_ids


# ----- Invite DB Functions ----- #

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
    invites: List[StoredInvite] = field(default_factory=[])  # Needed to ensure that all StoredInvites do not share the same list

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


# ----- Cached Messages DB Functions ----- #

@dataclass
class CachedMessage:
    message_id: int
    server_id: int
    user_id: int
    ts: datetime
    content: Optional[str]
    attachments: Optional[List[str]]
    webhook_author_name: Optional[str]
    system_pkid: Optional[str]
    member_pkid: Optional[str]
    pk_system_account_id: Optional[int]


@db_deco
async def cache_message(pool, sid: int, message_id: int, author_id: int, message_content: Optional[str] = None,
                        attachments: Optional[List[str]] = None, webhook_author_name: Optional[str] = None,
                        system_pkid: Optional[str] = None, member_pkid: Optional[str] = None, pk_system_account_id: Optional[int] = None):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO messages(server_id, message_id, user_id, content, attachments, webhook_author_name) VALUES($1, $2, $3, $4, $5, $6)", sid, message_id, author_id, message_content, attachments, webhook_author_name)


@db_deco
async def get_cached_message(pool, sid: int, message_id: int) -> Optional[CachedMessage]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM messages WHERE message_id = $1", message_id)
        return CachedMessage(**row) if row is not None else None


@db_deco
async def update_cached_message(pool, sid: int, message_id: int, new_content: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE messages SET content = $1 WHERE message_id = $2", new_content, message_id)


@db_deco
async def update_cached_message_pk_details(pool, sid: int, message_id: int, system_pkid: str, member_pkid: str,
                                           pk_system_account_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE messages SET system_pkid = $1, member_pkid = $2, pk_system_account_id = $3 WHERE message_id = $4",
                           system_pkid, member_pkid, pk_system_account_id, message_id)


@db_deco
async def delete_cached_message(pool, sid: int, message_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE message_id = $1", message_id)


@db_deco
async def get_number_of_rows_in_messages(pool, table: str = "messages") -> int:  # Slow! But only used for g!top so okay.
    async with pool.acquire() as conn:
        num_of_rows = await conn.fetchval("SELECT COUNT(*) FROM messages")
        return num_of_rows


@db_deco
async def get_cached_messages_older_than(pool, hours: int):
    # This command is limited only to servers that we are Admin/Owner of for privacy reasons.
    # Servers: GGB, PN, AS
    async with pool.acquire() as conn:
        now = datetime.now()
        offset = timedelta(hours=hours)
        before = now - offset
        raw_rows = await conn.fetch(" SELECT * from messages WHERE ts > $1 and server_id in (624361300327268363, 433446063022538753, 468794128340090890)", before)
        return raw_rows


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
                               server_id       BIGINT PRIMARY KEY,
                               server_name     TEXT,
                               log_channel_id  BIGINT,
                               logging_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                               log_configs     JSON DEFAULT NULL
                           )
                       ''')

        # Create ignored_channels table
        await conn.execute('''
                           CREATE TABLE if not exists ignored_channels(
                                id         SERIAL PRIMARY KEY,
                                server_id  BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                                channel_id BIGINT NOT NULL,
                                UNIQUE (server_id, channel_id)
                           )
                       ''')

        # Create ignored_category table
        await conn.execute('''
                           CREATE TABLE if not exists ignored_category(
                                id          SERIAL PRIMARY KEY,
                                server_id   BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                                category_id BIGINT NOT NULL,
                                UNIQUE (server_id, category_id)
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

        # Create users table
        await conn.execute('''
                           CREATE TABLE if not exists users(
                               user_id       BIGINT PRIMARY KEY,
                               server_id     BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                               username      TEXT,
                               discriminator SMALLINT,
                               nickname      TEXT,
                               is_webhook    BOOL DEFAULT FALSE,
                               UNIQUE (user_id, server_id)
                           )
                       ''')

        # Create message cache table
        # Will need to execute the following to alter the existing production table:
        # ALTER TABLE messages ADD COLUMN webhook_author_name TEXT DEFAULT NULL;
        # ALTER TABLE messages ADD COLUMN system_pkid TEXT DEFAULT NULL;
        # ALTER TABLE messages ADD COLUMN member_pkid TEXT DEFAULT NULL;
        # ALTER TABLE messages ADD COLUMN pk_system_account_id BIGINT DEFAULT NULL;
        await conn.execute('''
                           CREATE TABLE if not exists messages(
                               message_id           BIGINT PRIMARY KEY,
                               server_id            BIGINT NOT NULL REFERENCES servers(server_id) ON DELETE CASCADE,
                               user_id              BIGINT NOT NULL,
                               content              TEXT DEFAULT NULL,
                               attachments          TEXT[] DEFAULT NULL,
                               ts                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                               webhook_author_name  TEXT DEFAULT NULL,
                               system_pkid          TEXT DEFAULT NULL,
                               member_pkid          TEXT DEFAULT NULL,
                               pk_system_account_id BIGINT DEFAULT NULL
                           )
                       ''')



