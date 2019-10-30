"""
Gabby Gums
Functions and enums for configuring guild specific settings
"""

from dataclasses import dataclass, fields, asdict
from typing import Optional, List

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


# TODO: Should we just use a dict instead of going to all the hassle of converting back and forth?
@dataclass
class GuildLoggingConfig:
    # Can't use Optional here as it break the loading of nested dictionaries.
    # All commented out event types are for future use. They are commented out so they do not appear in available_event_types()
    message_edit: EventConfig = None
    message_delete: EventConfig = None
    member_join: EventConfig = None
    member_leave: EventConfig = None
    guild_member_nickname: EventConfig = None
    # bulk_message_delete: EventConfig = None
    # username_change: EventConfig = None
    # channel_create: EventConfig = None
    # channel_delete: EventConfig = None
    # channel_update: EventConfig = None
    # role_create: EventConfig = None
    # role_delete: EventConfig = None
    # role_update: EventConfig = EventConfig(enabled=False)
    # message_react_remove: EventConfig = None
    # voice_channel_join: EventConfig = None
    # voice_channel_leave: EventConfig = None
    # voice_channel_switch: EventConfig = None
    # guild_member_update: EventConfig = None
    # guild_update: EventConfig = None
    # guild_ban_add: EventConfig = None
    # guild_ban_remove: EventConfig = None

    def __setitem__(self, key, value):
        t_key = key.lower()
        # t_key = t_key.replace('_', '')

        for variable in self.__dict__.keys():
            t_var = variable#.replace('_', '')

            if t_var.lower() == t_key:
                setattr(self, variable, value)
                return
        raise KeyError('{} is not a valid key for type GuildLoggingConfig'.format(key))


    def __getitem__(self, item):
        t_key = item.lower()

        for variable in self.__dict__.keys():
            t_var = variable#.replace('_', '')
            if t_var.lower() == t_key:
                return getattr(self, variable)
        raise KeyError('{} is not a valid key for type GuildLoggingConfig'.format(item))

    def to_dict(self) -> dict:
        return asdict(self)

    def available_event_types(self) -> List[str]:
        return list(self.__dict__.keys())


def load_nested_dict(dc, _dict):
    try:
        fieldtypes = {f.name: f.type for f in fields(dc)}
        return dc(**{f: load_nested_dict(fieldtypes[f], _dict[f]) for f in _dict})
    except:
        return _dict  # Not a dataclass field


