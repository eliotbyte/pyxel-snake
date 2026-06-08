import math

SPAWN_ANIM_DURATION = 1.0
SPAWN_SCALE_MIN = 0.25


def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * pow(t - 1.0, 3) + c1 * pow(t - 1.0, 2)


def ease_in_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * t


def spawn_scale(t: float) -> float:
    if t >= 1.0:
        return 1.0
    return SPAWN_SCALE_MIN + (1.0 - SPAWN_SCALE_MIN) * ease_out_back(t)


def shrink_scale(t: float) -> float:
    if t >= 1.0:
        return SPAWN_SCALE_MIN
    return SPAWN_SCALE_MIN + (1.0 - SPAWN_SCALE_MIN) * (1.0 - ease_in_cubic(t))
