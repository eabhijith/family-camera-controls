"""Experimental payload shape observed in Cofe Online; no network transport.

SDK command argument 1402 and OPElecPTZControl were observed in static APK analysis.
Its wire mapping is not established. This does not prove support/channel mapping
on any particular camera. It is not
registered as an HA action until legitimate authentication and live tests exist.
The bounds and 32-pixel default below are local safety policies, not recovered
camera limits/defaults. Syntax validation does not authenticate a session or
verify a channel. The caller must establish those independently.
"""
import re

SDK_COMMAND_ARGUMENT = 1402
# Backwards-compatible name for existing research tests; not a wire command ID.
COMMAND_ID = SDK_COMMAND_ARGUMENT
NAME = "OPElecPTZControl"
DIRECTIONS = {"up": ("DirectionUp", 0, 1), "down": ("DirectionDown", 0, 1),
              "left": ("DirectionLeft", 1, 0), "right": ("DirectionRight", 1, 0)}


def build_payload(direction, *, session, channel, pixels=32):
    if direction not in DIRECTIONS:
        raise ValueError("Unsupported electronic-view direction")
    if not isinstance(session, str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,16}", session):
        raise ValueError("Session identifier must have 0x-prefixed hexadecimal syntax")
    if type(channel) is not int or not 0 <= channel <= 31:
        raise ValueError("Channel must be an integer between 0 and 31 (local policy)")
    if type(pixels) is not int or not 1 <= pixels <= 100:
        raise ValueError("Pixel adjustment must be between 1 and 100")
    command, x, y = DIRECTIONS[direction]
    return {"Name": NAME, "SessionID": session, NAME: {"Command": command,
            "Parameter": {"Channel": channel, "Preset": 0, "Step": 4,
                          "POINT": {"PixelsX": x * pixels, "PixelsY": y * pixels}}}}
