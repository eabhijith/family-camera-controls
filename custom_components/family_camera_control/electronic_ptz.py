"""Experimental payload shape observed in Cofe Online; no network transport.

Command 1402 and OPElecPTZControl were observed in static APK analysis. This
does not prove support/channel mapping on any particular camera. It is not
registered as an HA action until legitimate authentication and live tests exist.
"""
import re

COMMAND_ID = 1402
NAME = "OPElecPTZControl"
DIRECTIONS = {"up": ("DirectionUp", 0, 1), "down": ("DirectionDown", 0, 1),
              "left": ("DirectionLeft", 1, 0), "right": ("DirectionRight", 1, 0)}


def build_payload(direction, *, session, channel, pixels=32):
    if direction not in DIRECTIONS:
        raise ValueError("Unsupported electronic-view direction")
    if not isinstance(session, str) or not re.fullmatch(r"0x[0-9a-fA-F]{1,16}", session):
        raise ValueError("An authenticated session identifier is required")
    if type(channel) is not int or not 0 <= channel <= 31:
        raise ValueError("A verified channel between 0 and 31 is required")
    if type(pixels) is not int or not 1 <= pixels <= 100:
        raise ValueError("Pixel adjustment must be between 1 and 100")
    command, x, y = DIRECTIONS[direction]
    return {"Name": NAME, "SessionID": session, NAME: {"Command": command,
            "Parameter": {"Channel": channel, "Preset": 0, "Step": 4,
                          "POINT": {"PixelsX": x * pixels, "PixelsY": y * pixels}}}}
