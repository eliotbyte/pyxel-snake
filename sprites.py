import json
import math
from pathlib import Path

import pyxel

IMG_SNAKE = 0
SPRITE_SIZE = 16
NUM_HEAD_DIRS = 16
SHADOW_OFFSET_Y = 8

HOVER_LIFT = 2
FRUIT_HOVER_LIFT = HOVER_LIFT + 4
BOB_AMP = 2
BOB_PERIOD = 1.2
SEGMENT_BOB_DELAY = 0.1

SHADOW_SMALL = 0
SHADOW_MED = 1
SHADOW_BIG = 2
SHADOW_SPRITES = ("shadow_small", "shadow_med", "shadow_big")

BUBBLE_BIG = "bubble_big"
BUBBLE_SHRINK = "bubble_shrink"
BUBBLE_SQUASH = "bubble_squash"
BUBBLE_POP = "bubble_pop"

FRUIT_EGGPLANT = 0
FRUIT_APPLE = 1
FRUIT_STRAWBERRY = 2
FRUIT_GRAPE = 3
FRUIT_CHERRY = 4
FRUIT_DAIKON = 5
FRUIT_RADISH = 6
FRUIT_WATERMELON = 7
FRUIT_ORANGE = 8
FRUIT_LEMON = 9
FRUIT_BANANA = 10

FRUIT_NAMES = (
    "fruit_eggplant",
    "fruit_apple",
    "fruit_strawberry",
    "fruit_grape",
    "fruit_cherry",
    "fruit_daikon",
    "fruit_radish",
    "fruit_watermelon",
    "fruit_orange",
    "fruit_lemon",
    "fruit_banana",
)
FRUIT_COUNT = len(FRUIT_NAMES)
FOOD_COUNT = FRUIT_COUNT

BUBBLE_FRUIT_SCALE = 0.5
CRUMB_SIZE = 8

_ATLAS: dict[str, dict] = {}


def init_atlas(manifest_path: str | Path = "assets/snake.manifest.json") -> None:
    global _ATLAS
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    _ATLAS = data["sprites"]


def _sprite(name: str) -> dict:
    try:
        return _ATLAS[name]
    except KeyError as exc:
        raise KeyError(f"Missing sprite {name!r} in atlas") from exc


def _blt_sprite(
    sx: float,
    sy: float,
    name: str,
    w: int = SPRITE_SIZE,
    h: int = SPRITE_SIZE,
    scale: float = 1.0,
) -> None:
    sprite = _sprite(name)
    x = sx - w / 2
    y = sy - h / 2
    bank = sprite["bank"]
    u = sprite["u"]
    v = sprite["v"]
    colkey = sprite["colkey"]
    if scale == 1.0:
        pyxel.blt(x, y, bank, u, v, w, h, colkey)
    else:
        pyxel.blt(x, y, bank, u, v, w, h, colkey, scale=scale)


def _blt_sprite_region(
    sx: float,
    sy: float,
    name: str,
    u: int,
    v: int,
    w: int,
    h: int,
    scale: float = 1.0,
) -> None:
    sprite = _sprite(name)
    x = sx - w / 2
    y = sy - h / 2
    colkey = sprite["colkey"]
    if scale == 1.0:
        pyxel.blt(x, y, sprite["bank"], u, v, w, h, colkey)
    else:
        pyxel.blt(x, y, sprite["bank"], u, v, w, h, colkey, scale=scale)


def bob_y_offset(time: float, phase_delay: float = 0.0) -> float:
    return math.sin((time - phase_delay) * 2 * math.pi / BOB_PERIOD) * BOB_AMP


def hover_y(ground_sy: float, time: float, phase_delay: float = 0.0, lift: float | None = None) -> float:
    return ground_sy - (lift if lift is not None else HOVER_LIFT) + bob_y_offset(time, phase_delay)


def shadow_for_bob(base_shadow: int, bob_offset: float) -> int:
    if bob_offset < 0 and base_shadow > SHADOW_SMALL:
        return base_shadow - 1
    return base_shadow


def head_sprite_name(dir_idx: int, mouth_open: bool) -> str:
    prefix = "head_open" if mouth_open else "head_closed"
    return f"{prefix}_{dir_idx % NUM_HEAD_DIRS:02d}"


def draw_head(sx: float, sy: float, dir_idx: int, mouth_open: bool = False) -> None:
    _blt_sprite(sx, sy, head_sprite_name(dir_idx, mouth_open))


def draw_tail(sx: float, sy: float, tail_index: int) -> None:
    _blt_sprite(sx, sy, f"tail_{tail_index:02d}")


def draw_bubble(sx: float, sy: float, sprite_name: str, scale: float = 1.0) -> None:
    _blt_sprite(sx, sy, sprite_name, scale=scale)


def draw_fruit_quarter(sx: float, sy: float, kind: int, quarter: int, scale: float = 1.0) -> None:
    base = _sprite(FRUIT_NAMES[kind % FRUIT_COUNT])
    qu = (quarter % 2) * CRUMB_SIZE
    qv = (quarter // 2) * CRUMB_SIZE
    _blt_sprite_region(sx, sy, FRUIT_NAMES[kind % FRUIT_COUNT], base["u"] + qu, base["v"] + qv, CRUMB_SIZE, CRUMB_SIZE, scale)


def draw_fruit(sx: float, sy: float, kind: int, scale: float = 1.0) -> None:
    _blt_sprite(sx, sy, FRUIT_NAMES[kind % FRUIT_COUNT], scale=scale)


def draw_shadow(sx: float, sy: float, shadow_idx: int) -> None:
    _blt_sprite(sx, sy + SHADOW_OFFSET_Y, SHADOW_SPRITES[shadow_idx % len(SHADOW_SPRITES)])
