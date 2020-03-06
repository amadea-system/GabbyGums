"""
Functions for interfacing with the Plural Kit API.
API Functions include:

Part of the Gabby Gums Discord Logger.
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, List, Union, Tuple, NamedTuple

import aiohttp

log = logging.getLogger(__name__)


class CouldNotConnectToPKAPI(Exception):
    pass


async def get_pk_system_from_userid(user_id: int) -> Optional[Dict]:

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.pluralkit.me/v1/a/{user_id}') as r:
                if r.status == 200:  # We received a valid response from the PK API.
                    logging.info(f"User has an associated PK Account linked to thier Discord Account.")

                    # Convert the JSON response to a dict
                    pk_response = await r.json()

                    # Unpack and return.
                    logging.info(f"Got system: {pk_response}")
                    # system_id = pk_response['id']
                    # return system_id
                    return pk_response
                elif r.status == 404:
                    # No PK Account found.
                    log.info("No PK Account found.")
                    return None

    except aiohttp.ClientError as e:
        raise CouldNotConnectToPKAPI  # Really not strictly necessary, but it makes the code a bit nicer I think.

