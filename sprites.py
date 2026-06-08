import math

import pyxel

IMG_SNAKE = 0
COLKEY = 15
SPRITE_SIZE = 16
NUM_DIRS = 8
SHADOW_OFFSET_Y = 8

HOVER_LIFT = 2
FRUIT_HOVER_LIFT = HOVER_LIFT + 4
BOB_AMP = 2
BOB_PERIOD = 1.2
SEGMENT_BOB_DELAY = 0.1

ROW_HEAD = 0
ROW_BALLS = 16
ROW_FRUIT = 32
ROW_VEGGIE = 48

# Row 0: sprites 1–8 closed, 9–16 open
OPEN_U = NUM_DIRS * SPRITE_SIZE

# Row 16: 7 body balls + 3 shadows + 4 bubble frames
BALL_GIANT = 0
BALL_BIG = 1
BALL_MED = 2
BALL_SMALL = 3
BALL_TINY = 4
BALL_TINIER = 5
BALL_SMALLEST = 6

SHADOW_SMALL = 7
SHADOW_MED = 8
SHADOW_BIG = 9

BUBBLE_BIG = 10
BUBBLE_SHRINK = 11
BUBBLE_SQUASH = 12
BUBBLE_POP = 13

BODY_BALLS = (BALL_BIG, BALL_MED, BALL_SMALL)

SNAKE_TINT_FROM = 10
AI_SNAKE_PALS = ((SNAKE_TINT_FROM, 8), (SNAKE_TINT_FROM, 14))

# Row 32: fruits (kind 0–15)
FRUIT_EGGPLANT = 0
FRUIT_APPLE = 1
FRUIT_STRAWBERRY = 2
FRUIT_GRAPE = 3
FRUIT_CHERRY = 4
FRUIT_DAIKON_BIG = 5
FRUIT_DAIKON_MED = 6
FRUIT_LEMON = 7
FRUIT_BANANA = 8
FRUIT_PEACH = 9
FRUIT_ORANGE = 10
FRUIT_PERSIMMON = 11
FRUIT_RADISH = 12
FRUIT_WATERMELON = 13
FRUIT_TOMATO = 14
FRUIT_PINEAPPLE = 15
ROW_FRUIT_COUNT = 16

# Row 48: vegetables (kind 16–23)
VEG_CARROT = 16
VEG_MUSHROOM = 17
VEG_CORN = 18
VEG_PEAR = 19
VEG_ONION = 20
VEG_CUCUMBER = 21
VEG_PEA = 22
VEG_ACORN = 23
ROW_VEGGIE_COUNT = 8

FOOD_COUNT = ROW_FRUIT_COUNT + ROW_VEGGIE_COUNT
FRUIT_COUNT = FOOD_COUNT  # spawn / random kind


def bob_y_offset(time: float, phase_delay: float = 0.0) -> float:
    return math.sin((time - phase_delay) * 2 * math.pi / BOB_PERIOD) * BOB_AMP


def hover_y(ground_sy: float, time: float, phase_delay: float = 0.0, lift: float | None = None) -> float:
    return ground_sy - (lift if lift is not None else HOVER_LIFT) + bob_y_offset(time, phase_delay)


def shadow_for_bob(base_shadow: int, bob_offset: float) -> int:
    if bob_offset < 0 and base_shadow > SHADOW_SMALL:
        return base_shadow - 1
    return base_shadow


def _blt_centered(sx: float, sy: float, u: int, v: int, w: int = SPRITE_SIZE, h: int = SPRITE_SIZE) -> None:
    x = sx - w / 2
    y = sy - h / 2
    pyxel.blt(x, y, IMG_SNAKE, u, v, w, h, COLKEY)


def _blt_centered_scaled(sx: float, sy: float, u: int, v: int, w: int, h: int, scale: float) -> None:
    # Pyxel scale/rotate pivot is the center of (x, y, w, h), not the scaled output size.
    x = sx - w / 2
    y = sy - h / 2
    if scale == 1.0:
        pyxel.blt(x, y, IMG_SNAKE, u, v, w, h, COLKEY)
    else:
        pyxel.blt(x, y, IMG_SNAKE, u, v, w, h, COLKEY, scale=scale)


def _food_uv(kind: int) -> tuple[int, int]:
    if kind < ROW_FRUIT_COUNT:
        return kind * SPRITE_SIZE, ROW_FRUIT
    col = kind - ROW_FRUIT_COUNT
    if col >= ROW_VEGGIE_COUNT:
        col = col % ROW_VEGGIE_COUNT
    return col * SPRITE_SIZE, ROW_VEGGIE


def head_uv(dir_idx: int, mouth_open: bool) -> tuple[int, int]:
    u = (dir_idx % NUM_DIRS) * SPRITE_SIZE
    if mouth_open:
        u += OPEN_U
    return u, ROW_HEAD


def draw_head(sx: float, sy: float, dir_idx: int, mouth_open: bool = False) -> None:
    u, v = head_uv(dir_idx, mouth_open)
    _blt_centered(sx, sy, u, v)


def draw_ball(sx: float, sy: float, ball_idx: int) -> None:
    u = ball_idx * SPRITE_SIZE
    _blt_centered(sx, sy, u, ROW_BALLS)


def draw_bubble(sx: float, sy: float, bubble_idx: int, scale: float = 1.0) -> None:
    u = bubble_idx * SPRITE_SIZE
    _blt_centered_scaled(sx, sy, u, ROW_BALLS, SPRITE_SIZE, SPRITE_SIZE, scale)


BUBBLE_FRUIT_SCALE = 0.5
CRUMB_SIZE = 8


def draw_fruit_quarter(sx: float, sy: float, kind: int, quarter: int, scale: float = 1.0) -> None:
    u, v = _food_uv(kind)
    qu = (quarter % 2) * CRUMB_SIZE
    qv = (quarter // 2) * CRUMB_SIZE
    _blt_centered_scaled(sx, sy, u + qu, v + qv, CRUMB_SIZE, CRUMB_SIZE, scale)


def draw_fruit(sx: float, sy: float, kind: int, scale: float = 1.0) -> None:
    u, v = _food_uv(kind)
    _blt_centered_scaled(sx, sy, u, v, SPRITE_SIZE, SPRITE_SIZE, scale)


def draw_shadow(sx: float, sy: float, shadow_idx: int) -> None:
    u = shadow_idx * SPRITE_SIZE
    _blt_centered(sx, sy + SHADOW_OFFSET_Y, u, ROW_BALLS)
