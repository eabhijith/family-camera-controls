"""Pure movement policy; never treats unverified native lens control as supported."""
import math

DIRECTIONS = {"up": ("tilt", "UP"), "down": ("tilt", "DOWN"),
              "left": ("pan", "LEFT"), "right": ("pan", "RIGHT")}


def movement_data(direction, duration=0.3, coefficient=1.0):
    if direction == "stop":
        return {"move_mode": "Stop"}
    if direction not in DIRECTIONS:
        raise ValueError("Unsupported direction")
    if not math.isfinite(duration) or not 0.1 <= duration <= 0.5:
        raise ValueError("Duration must be between 0.1 and 0.5 seconds")
    if not math.isfinite(coefficient) or not 0.1 <= coefficient <= 1:
        raise ValueError("Movement coefficient must be between 0.1 and 1")
    axis, value = DIRECTIONS[direction]
    return {"move_mode": "ContinuousMove", axis: value,
            "distance": coefficient, "continuous_duration": duration}
