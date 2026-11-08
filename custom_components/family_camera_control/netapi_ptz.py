"""Observed EseeCloud multi-PTZ JSON subtree, not a complete wire request.

Independently implemented from static evidence of BaseSettingSession. There is
no network transport or registered HA action. Authentication, envelope fields,
transport channel and device/lens mapping must be established separately.
"""

SAFE_APP_COMMANDS = frozenset({"StepUp", "StepDown", "StepLeft", "StepRight", "Stop"})


def build_multi_ptz_subtree(*, channel, command):
    """Build a bounded research payload; number bounds are local policy only."""
    if type(channel) is not int or not 0 <= channel <= 31:
        raise ValueError("Channel must be 0..31 (local policy, not verified device inventory)")
    if not isinstance(command, str) or command not in SAFE_APP_COMMANDS:
        raise ValueError("Only observed step/stop commands are allowed by this local policy")
    return {"IPCam": {"NetAPI": {"R/MultiPTZ/Control": {
        "Chn": channel, "Cmd": command, "Arg": 1, "Arg2": 0,
    }}}}
