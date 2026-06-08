import math
import random
from dataclasses import dataclass, field

from anim import SPAWN_ANIM_DURATION, shrink_scale, spawn_scale
from sprites import FOOD_COUNT, SHADOW_BIG, SHADOW_MED, SHADOW_SMALL, shadow_for_bob

WORLD_SIZE = 64
WORLD_MARGIN = 8
SPAWN_CX = WORLD_SIZE / 2
SPAWN_CY = WORLD_SIZE / 2

FRUIT_SPAWN_COUNT = 6
FRUIT_MIN_DIST = 10
SPAWN_CANDIDATES = 48
FRUIT_DROP_HEIGHT = 16.0
FRUIT_DROP_DURATION = 0.48


def fruit_drop_shadow(z: float) -> int:
    peak = FRUIT_DROP_HEIGHT
    if z > peak * 0.65:
        return SHADOW_SMALL
    if z > peak * 0.2:
        return shadow_for_bob(SHADOW_MED, -z * 0.05)
    return SHADOW_BIG


@dataclass
class Fruit:
    wx: float
    wy: float
    kind: int
    _drop_t: float = field(default=0.0, repr=False)
    _dropping: bool = field(default=False, repr=False)
    _spawn_t: float = field(default=0.0, repr=False)
    _spawn_in: bool = field(default=False, repr=False)
    _shrinking: bool = field(default=False, repr=False)

    @classmethod
    def spawned(cls, wx: float, wy: float, kind: int) -> "Fruit":
        return cls(wx, wy, kind, _spawn_in=True, _spawn_t=0.0)

    @classmethod
    def released(cls, wx: float, wy: float, kind: int) -> "Fruit":
        return cls(wx, wy, kind, _drop_t=0.0, _dropping=True)

    def begin_shrink(self) -> None:
        self._shrinking = True
        self._spawn_in = False
        self._spawn_t = 0.0

    def is_shrink_finished(self) -> bool:
        return self._shrinking and self._spawn_t >= SPAWN_ANIM_DURATION

    def visual_scale(self) -> float:
        if self._shrinking:
            return shrink_scale(min(1.0, self._spawn_t / SPAWN_ANIM_DURATION))
        if self._spawn_in:
            return spawn_scale(min(1.0, self._spawn_t / SPAWN_ANIM_DURATION))
        return 1.0

    @property
    def collectible(self) -> bool:
        return not self._dropping and not self._shrinking and not self._spawn_in

    def update(self, dt: float) -> None:
        if self._spawn_in or self._shrinking:
            self._spawn_t += dt
            if self._spawn_in and self._spawn_t >= SPAWN_ANIM_DURATION:
                self._spawn_in = False
                self._spawn_t = 0.0
            return
        if not self._dropping:
            return
        self._drop_t += dt
        if self._drop_t >= FRUIT_DROP_DURATION:
            self._dropping = False
            self._drop_t = 0.0

    def drop_z(self) -> float:
        if not self._dropping:
            return 0.0
        t = min(1.0, self._drop_t / FRUIT_DROP_DURATION)
        return FRUIT_DROP_HEIGHT * math.sin(math.pi * t)

    def is_airborne_drop(self) -> bool:
        return self._dropping

    def shadow_idx(self, bob: float) -> int:
        scale = self.visual_scale()
        if scale < 0.45:
            base = SHADOW_SMALL
        elif scale < 0.75:
            base = SHADOW_MED
        else:
            base = SHADOW_BIG
        return shadow_for_bob(base, bob)


def wrap_pos(x: float, y: float) -> tuple[float, float]:
    return x % WORLD_SIZE, y % WORLD_SIZE


def toroidal_delta(a: float, b: float) -> float:
    d = a - b
    half = WORLD_SIZE / 2
    if d > half:
        d -= WORLD_SIZE
    if d < -half:
        d += WORLD_SIZE
    return d


def toroidal_dist(x1: float, y1: float, x2: float, y2: float) -> float:
    dx = toroidal_delta(x1, x2)
    dy = toroidal_delta(y1, y2)
    return math.hypot(dx, dy)


def _far_enough(x: float, y: float, occupied: list[tuple[float, float]], min_dist: float) -> bool:
    for ox, oy in occupied:
        if toroidal_dist(x, y, ox, oy) < min_dist:
            return False
    return True


def _nearest_occupied_dist(wx: float, wy: float, occupied: list[tuple[float, float]]) -> float:
    if not occupied:
        return float("inf")
    return min(toroidal_dist(wx, wy, ox, oy) for ox, oy in occupied)


def spawn_uniform_pos(
    occupied: list[tuple[float, float]],
    rng: random.Random,
    min_dist: float = FRUIT_MIN_DIST,
    candidates: int = SPAWN_CANDIDATES,
) -> tuple[float, float]:
    """Pick a spot far from existing objects — spreads spawns evenly."""
    lo = WORLD_MARGIN
    hi = WORLD_SIZE - WORLD_MARGIN
    best_pos: tuple[float, float] | None = None
    best_score = -1.0
    for _ in range(candidates):
        wx = rng.uniform(lo, hi)
        wy = rng.uniform(lo, hi)
        if not _far_enough(wx, wy, occupied, min_dist):
            continue
        score = _nearest_occupied_dist(wx, wy, occupied)
        if score > best_score:
            best_score = score
            best_pos = (wx, wy)
    if best_pos is not None:
        return best_pos
    relaxed = min_dist * 0.65
    for _ in range(200):
        wx = rng.uniform(lo, hi)
        wy = rng.uniform(lo, hi)
        if _far_enough(wx, wy, occupied, relaxed):
            return wx, wy
    return lo + min_dist, lo + min_dist


def spawn_fruit_room(
    occupied: list[tuple[float, float]],
    rng: random.Random,
    min_dist: float = FRUIT_MIN_DIST,
) -> Fruit:
    wx, wy = spawn_uniform_pos(occupied, rng, min_dist)
    return Fruit.spawned(wx, wy, rng.randint(0, FOOD_COUNT - 1))


def spawn_fruits_room(
    count: int,
    snake_positions: list[tuple[float, float]],
    rng: random.Random,
) -> list[Fruit]:
    occupied = list(snake_positions)
    fruits: list[Fruit] = []
    for _ in range(count):
        fruit = spawn_fruit_room(occupied, rng)
        fruits.append(fruit)
        occupied.append((fruit.wx, fruit.wy))
    return fruits
