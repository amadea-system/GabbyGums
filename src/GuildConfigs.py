"""
Gabby Gums
Functions and enums for configuring guild specific settings
"""
from __future__ import annotations

from dataclasses import dataclass, fields, asdict
from typing import Optional, List, Dict

from discord.permissions import Permissions

example_log_config = {
    "message_delete": {
        "enabled": True,
        "log_channel_id": None
    },
    "message_edit": {
        "enabled": True,
        "log_channel_id": 617420419359703071
    },
    "member_join": {
        "enabled": False,
        "log_channel_id": 617420419359703071
    },
    "member_leave": {
        "enabled": False,
        "log_channel_id": None
    },
    "guild_member_nickname": {
        "enabled": False,
        "log_channel_id": None
    }
}


@dataclass
class EventConfig:
    enabled: Optional[bool] = True
    log_channel_id: Optional[int] = None

    @classmethod
    def from_dict(cls, _dict) -> EventConfig:
        configs = cls()

        if _dict is None:
            return configs

        if 'enabled' in _dict:
            configs.enabled = _dict['enabled']
        if 'log_channel_id' in _dict:
            configs.log_channel_id = _dict['log_channel_id']

        return configs


# TODO: Should we just use a dict instead of going to all the hassle of converting back and forth?
@dataclass
class GuildLoggingConfig:
    # Can't use Optional here as it break the loading of nested dictionaries.
    # All commented out event types are for future use. They are commented out so they do not appear in available_event_types()
    message_edit: EventConfig = None
    message_delete: EventConfig = None
    member_join: EventConfig = None
    member_leave: EventConfig = None
    member_ban: EventConfig = None
    member_unban: EventConfig = None
    member_kick: EventConfig = None
    member_avatar_change: EventConfig = EventConfig(enabled=False)
    guild_member_nickname: EventConfig = None
    username_change: EventConfig = None
    # bulk_message_delete: EventConfig = None
    channel_create: EventConfig = None
    channel_delete: EventConfig = None
    channel_update: EventConfig = None
    invite_create: EventConfig = None
    invite_delete: EventConfig = None
    # role_create: EventConfig = None
    # role_delete: EventConfig = None
    # role_update: EventConfig = EventConfig(enabled=False)
    # message_react_remove: EventConfig = None
    # voice_channel_join: EventConfig = None
    # voice_channel_leave: EventConfig = None
    # voice_channel_switch: EventConfig = None
    # guild_member_update: EventConfig = None
    # guild_update: EventConfig = None


    def __setitem__(self, key, value):
        t_key = key.lower()
        # t_key = t_key.replace('_', '')
        for variable in self.__dict__.keys():
            t_var = variable #.replace('_', '')

            if t_var.lower() == t_key:
                setattr(self, variable, value)
                return
        raise KeyError('{} is not a valid key for type GuildLoggingConfig'.format(key))

    def __getitem__(self, item):
        t_key = item.lower()
        for variable in self.__dict__.keys():
            t_var = variable #.replace('_', '')
            if t_var.lower() == t_key:
                return getattr(self, variable)
        raise KeyError('{} is not a valid key for type GuildLoggingConfig'.format(item))

    def to_dict(self) -> dict:
        return asdict(self)

    def available_event_types(self) -> List[str]:
        return list(self.__dict__.keys())

    @classmethod
    def from_dict(cls, _dict) -> GuildLoggingConfig:
        configs = cls()
        if _dict is None:
            return configs

        for key in configs.__dict__.keys():
            if key in _dict:

                # Make sure defaults get loaded properly.
                if key == "member_avatar_change" and _dict[key] is None:
                    configs[key] = EventConfig(enabled=False)
                else:
                    configs[key] = EventConfig.from_dict(_dict[key])
        return configs

    def contains_channel(self, channel_id: int) -> bool:
        for value in self.__dict__.items():
            if isinstance(value, EventConfig):
                if value.log_channel_id is not None and value.log_channel_id == channel_id:
                    return True

        return False


class EventConfigDocs:
    """Class for holding documentation for an event type"""
    def __init__(self, brief: str, more: Optional[str] = None, required_permissions: Optional[Dict] = None):
        self.brief: str = brief
        self._more: Optional[str] = more
        self.permissions: Dict = required_permissions if required_permissions is not None else {}


    def __str__(self):
        return self.brief

    @property
    def more(self) -> str:
        return self._more or ""

    @property
    def full(self) -> str:
        if self._more is not None:
            return f"{self.brief}\n{self._more}"
        else:
            return self.brief


class GuildConfigDocs:
    """Class for documenting the Guild Configuration Types"""

    message_edit = EventConfigDocs('''Logs when messages are edited.''')
    message_delete = EventConfigDocs('''Logs when messages are deleted and bulk message deletes.''', '''(This is typically when a member gets banned or if a "message purge" bot command is used).''')
    member_join = EventConfigDocs('''Logs when a member joins your server and what invite they used.''', '''(Requires the `Manage Server` permission ONLY for invite tracking)''')
    member_leave = EventConfigDocs('''Logs when a member leaves your server.''')
    member_ban = EventConfigDocs("Logs when a member gets banned from your server.", "(Requires the `View Audit Log` permission ONLY to determine the moderator that did the banning and the reason)")
    member_unban = EventConfigDocs("Logs when a member gets unbanned from your server.", "(Requires the `View Audit Log` permission ONLY to determine the moderator that did the unbanning and the reason)")
    member_kick = EventConfigDocs("Logs when a member gets kicked from your server.", "(Requires the `View Audit Log` permission to work)", {'view_audit_log': True})
    member_avatar_change = EventConfigDocs("Logs when a member changes their avatar. (Off by default)")
    guild_member_nickname = EventConfigDocs("Logs when a member changes their server nickname.")
    username_change = EventConfigDocs("Logs when a member changes their Discord username or discriminator.")
    channel_create = EventConfigDocs("Logs when a channel is created in your server.")
    channel_delete = EventConfigDocs("Logs when a channel is deleted in your server.")
    channel_update = EventConfigDocs("Logs when a channel is changed in your server.\n(Position changes and person who created/updated/deleted channel coming soon!)", required_permissions={'external_emojis': True})
    invite_create: EventConfig = EventConfigDocs("Logs when an invite is created in your server.", "(Requires the 'Manage Channels' permission to work)", {'manage_channels': True})
    invite_delete: EventConfig = EventConfigDocs("Logs when an invite is deleted in your server.", "(Requires the 'Manage Channels' permission to work)", {'manage_channels': True})


    def __getitem__(self, item):
        t_key = item.lower()
        class_members = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__")]
        for variable in class_members:
            t_var = variable #.replace('_', '')
            if t_var.lower() == t_key:
                return getattr(self, variable)
        raise KeyError('{} is not a valid key for type GuildConfigDocs'.format(item))

def load_nested_dict(dc, _dict):
    try:
        fieldtypes = {f.name: f.type for f in fields(dc)}
        return dc(**{f: load_nested_dict(fieldtypes[f], _dict[f]) for f in _dict})
    except:
        return _dict  # Not a dataclass field


