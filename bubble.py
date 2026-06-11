import math
import random
from enum import Enum, auto

from anim import SPAWN_ANIM_DURATION, SPAWN_SCALE_MIN, spawn_scale
from sprites import (
    BUBBLE_BIG,
    BUBBLE_FRUIT_SCALE,
    BUBBLE_POP,
    BUBBLE_SHRINK,
    BUBBLE_SQUASH,
    FRUIT_HOVER_LIFT,
    SHADOW_BIG,
    SHADOW_MED,
    SHADOW_SMALL,
    bob_y_offset,
    shadow_for_bob,
)
from world import Fruit, WORLD_SIZE, toroidal_delta, toroidal_dist, wrap_pos

BUBBLE_TOUCH_RADIUS = 4.5
BUBBLE_FRUIT_HP = 2
BUBBLE_FRUIT_HP_WEAK = 1
BUBBLE_EMPTY_HP_MIN = 1
BUBBLE_EMPTY_HP_MAX = 3
SQUASH_DURATION = 0.12
SQUASH_LAND_Y_OFFSET = 4.0
POP_DURATION = 0.28
IDLE_CYCLE = 1.0
JUMP_HEIGHTS = (16.0, 8.0)
JUMP_DURATIONS = (0.84, 0.64)
JUMP_HEIGHT_EXTRA = 16.0
BOUNCE_SPEED_MULT = 2.0
BOUNCE_DEFLECT_DEG = 38.0
BOUNCE_DEFLECT_MULT = 3.0


class BubblePhase(Enum):
    IDLE = auto()
    SQUASH = auto()
    AIR = auto()
    POP = auto()


class Bubble:
    def __init__(
        self,
        wx: float,
        wy: float,
        fruit_kind: int | None = None,
        *,
        rng: random.Random | None = None,
        hp: int | None = None,
    ) -> None:
        self.wx, self.wy = wrap_pos(wx, wy)
        self.fruit_kind = fruit_kind
        self._released_fruit: Fruit | None = None
        self.phase = BubblePhase.IDLE
        if fruit_kind is not None:
            self.hp = hp if hp is not None else BUBBLE_FRUIT_HP
        else:
            roll = rng if rng is not None else random
            self.hp = roll.randint(BUBBLE_EMPTY_HP_MIN, BUBBLE_EMPTY_HP_MAX)
        self.idle_time = 0.0
        self.squash_timer = 0.0
        self.pop_timer = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.jump_idx = 0
        self.jump_timer = 0.0
        self.jump_z = 0.0
        self._jump_height = JUMP_HEIGHTS[0]
        self._jump_duration = JUMP_DURATIONS[0]
        self._squash_next: str | None = None
        self._squash_landed = False
        self._ref_snake_speed = 0.0
        self.removed = False
        self._pop_lift = 0.0
        self._spawn_t = 0.0
        self._spawning = False

    def begin_spawn(self) -> None:
        self._spawning = True
        self._spawn_t = 0.0

    def _spawn_progress(self) -> float:
        t = min(1.0, self._spawn_t / SPAWN_ANIM_DURATION)
        bscale = spawn_scale(t)
        return max(0.0, min(1.0, (bscale - SPAWN_SCALE_MIN) / (1.0 - SPAWN_SCALE_MIN)))

    def visual_scale(self) -> float:
        if not self._spawning:
            return 1.0
        t = min(1.0, self._spawn_t / SPAWN_ANIM_DURATION)
        return spawn_scale(t)

    def fruit_inside_scale(self) -> float:
        if self.fruit_kind is None:
            return 1.0
        if not self._spawning:
            return BUBBLE_FRUIT_SCALE
        p = self._spawn_progress()
        return BUBBLE_FRUIT_SCALE + (1.0 - BUBBLE_FRUIT_SCALE) * (1.0 - p)

    def is_spawn_blocking(self) -> bool:
        return self._spawning and self._spawn_t < SPAWN_ANIM_DURATION * 0.85

    def contains_fruit(self) -> bool:
        return self.fruit_kind is not None

    def take_released_fruit(self) -> Fruit | None:
        fruit = self._released_fruit
        self._released_fruit = None
        return fruit

    def draw_y_offset(self) -> float:
        if self.phase == BubblePhase.SQUASH and self._squash_landed:
            return SQUASH_LAND_Y_OFFSET
        return 0.0

    def is_active(self) -> bool:
        return not self.removed

    def sprite_idx(self) -> str:
        if self.phase == BubblePhase.POP:
            return BUBBLE_POP
        if self.phase == BubblePhase.SQUASH:
            return BUBBLE_SQUASH
        half = IDLE_CYCLE * 0.5
        return BUBBLE_BIG if (self.idle_time % IDLE_CYCLE) < half else BUBBLE_SHRINK

    def draws_shadow(self) -> bool:
        return self.phase != BubblePhase.POP

    def shadow_idx(self, bob: float) -> int:
        peak = self._jump_height if self.phase == BubblePhase.AIR else 16.0
        if self.jump_z > peak * 0.65:
            return SHADOW_SMALL
        if self.jump_z > peak * 0.2:
            return shadow_for_bob(SHADOW_MED, -self.jump_z * 0.05)
        return shadow_for_bob(SHADOW_BIG, bob if self.phase == BubblePhase.IDLE else 0.0)

    def screen_lift(self, t: float) -> float:
        if self.phase == BubblePhase.POP:
            return self._pop_lift
        bob = bob_y_offset(t) if self.phase == BubblePhase.IDLE else 0.0
        hover = FRUIT_HOVER_LIFT if self.phase == BubblePhase.IDLE else FRUIT_HOVER_LIFT * 0.5
        return hover + bob + self.jump_z

    def can_be_hit(self) -> bool:
        return self.phase == BubblePhase.IDLE and not self.removed and not self.is_spawn_blocking()

    @staticmethod
    def _bounce_angle_deg(
        head_x: float, head_y: float, heading_deg: float, bubble_wx: float, bubble_wy: float
    ) -> float:
        dx = toroidal_delta(bubble_wx, head_x)
        dy = toroidal_delta(bubble_wy, head_y)
        rad = math.radians(heading_deg)
        fx, fy = math.cos(rad), math.sin(rad)
        lx, ly = -fy, fx
        lateral = dx * lx + dy * ly
        if math.hypot(dx, dy) < 0.001:
            return heading_deg
        t = max(-1.0, min(1.0, lateral / BUBBLE_TOUCH_RADIUS))
        return heading_deg + t * BOUNCE_DEFLECT_DEG * BOUNCE_DEFLECT_MULT

    def try_hit(self, head_x: float, head_y: float, heading_deg: float, snake_speed: float) -> bool:
        if not self.can_be_hit():
            return False
        if toroidal_dist(head_x, head_y, self.wx, self.wy) > BUBBLE_TOUCH_RADIUS:
            return False
        self.hp -= 1
        self._ref_snake_speed = snake_speed
        bounce_deg = self._bounce_angle_deg(head_x, head_y, heading_deg, self.wx, self.wy)
        rad = math.radians(bounce_deg)
        launch_speed = snake_speed * BOUNCE_SPEED_MULT
        self.vx = math.cos(rad) * launch_speed
        self.vy = math.sin(rad) * launch_speed
        self.jump_idx = 0
        self.jump_z = 0.0
        self._begin_squash("jump")
        return True

    def _begin_squash(self, next_action: str, landed: bool = False) -> None:
        self.phase = BubblePhase.SQUASH
        self.squash_timer = SQUASH_DURATION
        self._squash_next = next_action
        self._squash_landed = landed

    def _begin_pop(self, bob: float = 0.0) -> None:
        if self.phase == BubblePhase.IDLE:
            hover = FRUIT_HOVER_LIFT
        else:
            hover = FRUIT_HOVER_LIFT * 0.5
        self._pop_lift = hover + bob + self.jump_z + self.draw_y_offset()
        self.phase = BubblePhase.POP
        self.pop_timer = POP_DURATION
        self.vx = 0.0
        self.vy = 0.0

    def force_pop(self, bob: float = 0.0) -> None:
        if self.removed or self.phase == BubblePhase.POP:
            return
        self.hp = 0
        self.vx = 0.0
        self.vy = 0.0
        self.jump_idx = 0
        self._begin_pop(bob)

    def _finish_pop(self) -> None:
        if self.fruit_kind is not None:
            self._released_fruit = Fruit.released(self.wx, self.wy, self.fruit_kind)
            self.fruit_kind = None
        self.removed = True

    def _begin_jump(self) -> None:
        self.phase = BubblePhase.AIR
        self.jump_timer = 0.0
        self.jump_z = 0.0
        idx = min(self.jump_idx, len(JUMP_HEIGHTS) - 1)
        base_h = JUMP_HEIGHTS[idx]
        base_d = JUMP_DURATIONS[idx]
        extra = random.uniform(0.0, JUMP_HEIGHT_EXTRA)
        self._jump_height = base_h + extra
        self._jump_duration = base_d * (self._jump_height / base_h)

    def _set_speed(self, speed: float) -> None:
        mag = math.hypot(self.vx, self.vy)
        if mag > 0.001:
            self.vx = self.vx / mag * speed
            self.vy = self.vy / mag * speed

    def _on_land(self) -> None:
        if self.jump_idx == 0:
            self.jump_z = 0.0
            self._set_speed(self._ref_snake_speed)
            self.jump_idx = 1
            self._begin_squash("jump", landed=True)
        else:
            self.vx = 0.0
            self.vy = 0.0
            self.jump_idx = 0
            if self.hp <= 0:
                self._begin_pop()
            else:
                self.jump_z = 0.0
                self._begin_squash("idle", landed=True)

    def update(self, dt: float, anim_t: float = 0.0) -> None:
        if self._spawning:
            self._spawn_t += dt
            if self._spawn_t >= SPAWN_ANIM_DURATION:
                self._spawning = False

        if self.phase != BubblePhase.POP and not self.removed:
            self.idle_time += dt

        if self.phase == BubblePhase.IDLE:
            return

        if self.phase == BubblePhase.POP:
            self.pop_timer -= dt
            if self.pop_timer <= 0.0:
                self._finish_pop()
            return

        if self.phase == BubblePhase.SQUASH:
            self.squash_timer -= dt
            if self.squash_timer > 0.0:
                return
            nxt = self._squash_next
            self._squash_next = None
            if nxt == "jump":
                self._begin_jump()
            else:
                self.phase = BubblePhase.IDLE
            return

        self.wx = (self.wx + self.vx * dt) % WORLD_SIZE
        self.wy = (self.wy + self.vy * dt) % WORLD_SIZE

        self.jump_timer += dt
        t = self.jump_timer / self._jump_duration
        if t < 1.0:
            self.jump_z = self._jump_height * math.sin(math.pi * t)
        else:
            self._on_land()
