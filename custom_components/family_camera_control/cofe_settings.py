"""Observed Cofe settings envelopes, with read/modify/write preservation.

Offline serialization only: no native transport, authentication or HA services.
Mode/value mappings were recovered from the app's actual DEX instructions;
envelopes and bean fields were inspected using REA. Syntax is not authentication.
"""
from copy import deepcopy

WHITE_LIGHT_MODES = frozenset({"Auto", "KeepOpen", "Close", "Timing", "Intelligent"})
LIGHT_SENSITIVITY = {"low": 2, "middle": 4, "high": 6}
LIGHT_DURATION_CHOICES = frozenset({5, 10, 30, 60, 90, 120})
ALERT_DURATION_CHOICES = frozenset({5, 10, 15, 20})


def _envelope(name, session_id, config):
    if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
        raise ValueError("A session string is required; its validity must be established separately")
    return {"Name": name, "SessionID": session_id, name: config}


def white_light_update(existing, *, session_id, channel=None, mode=None,
                       sensitivity=None, duration=None):
    """Prepare only app-discrete settings; preserve all unrelated current fields.

The duration choices apply to M8.u, NOT the M8.g seekbar branch (progress+10,
unknown maximum). Establish the device's active UI/capabilities before sending.
Channel bounds here are a local policy, not a discovered camera inventory.
Night-vision picker IDs 0..6 are a separate Camera.Param.DayNightColor setting.
"""
    if not isinstance(existing, dict) or not existing:
        raise ValueError("Read the existing white-light object before modifying it")
    name = "Camera.WhiteLight"
    if channel is not None:
        if type(channel) is not int or not 0 <= channel <= 31:
            raise ValueError("Channel must be 0..31 (local policy)")
        name += f".[{channel}]"
    result = deepcopy(existing)
    if mode is not None:
        if not isinstance(mode, str) or mode not in WHITE_LIGHT_MODES:
            raise ValueError("Unknown white-light WorkMode")
        if "WorkMode" not in result:
            raise ValueError("Existing configuration does not expose WorkMode")
        result["WorkMode"] = mode
    if sensitivity is not None or duration is not None:
        trigger = result.get("MoveTrigLight")
        if not isinstance(trigger, dict):
            raise ValueError("Existing configuration does not expose MoveTrigLight")
        if sensitivity is not None:
            if not isinstance(sensitivity, str) or sensitivity not in LIGHT_SENSITIVITY:
                raise ValueError("Sensitivity must be low, middle or high")
            if "Level" not in trigger:
                raise ValueError("Existing configuration does not expose trigger Level")
            trigger["Level"] = LIGHT_SENSITIVITY[sensitivity]
        if duration is not None:
            if type(duration) is not int or duration not in LIGHT_DURATION_CHOICES:
                raise ValueError("Duration must be an observed M8.u app choice")
            if "Duration" not in trigger:
                raise ValueError("Existing configuration does not expose trigger Duration")
            trigger["Duration"] = duration
    if mode is None and sensitivity is None and duration is None:
        raise ValueError("At least one setting change is required")
    return _envelope(name, session_id, result)


def intelligent_alert_update(existing, *, session_id, enabled=None, duration=None):
    """Prepare the observed unindexed alarm object; SDK channel is separately -1."""
    if not isinstance(existing, dict) or not existing:
        raise ValueError("Read the existing intelligent-alert object before modifying it")
    result = deepcopy(existing)
    if enabled is not None:
        if type(enabled) is not bool:
            raise ValueError("Alert enable must be boolean")
        if "Enable" not in result:
            raise ValueError("Existing configuration does not expose Enable")
        result["Enable"] = enabled
    if duration is not None:
        if type(duration) is not int or duration not in ALERT_DURATION_CHOICES:
            raise ValueError("Alert duration must be an observed app choice")
        if "Duration" not in result:
            raise ValueError("Existing configuration does not expose Duration")
        result["Duration"] = duration
    if enabled is None and duration is None:
        raise ValueError("At least one setting change is required")
    return _envelope("Alarm.IntellAlertAlarm", session_id, result)
