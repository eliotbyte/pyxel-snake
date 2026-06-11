import math
import random
from dataclasses import dataclass

from iso import screen_velocity_for_world_heading, world_pos_screen_ahead, world_velocity_for_screen_velocity
from world import WORLD_SIZE, wrap_pos

CRUMB_JUMP_HEIGHT = 16.0
CRUMB_AIR_DURATION = 0.48
CRUMB_LAND_DURATION = 1.0
CRUMB_SCREEN_SPEED = 52.0
CRUMB_SNAKE_CARRY = 1.0
CRUMB_SPAWN_AHEAD_PX = 8.0
SMALL_CRUMB_SCALE = 0.5
SMALL_CRUMBS_PER_BIG = (1, 3)
_DIAG = 1.0 / math.sqrt(2.0)

# (quarter, screen vx, screen vy) — diagonal burst directions
BITE_CRUMBS: tuple[tuple[tuple[int, float, float], ...], ...] = (
    ((0, -_DIAG, -_DIAG), (1, _DIAG, -_DIAG)),  # bite 0: left-up, right-up
    ((2, -_DIAG, _DIAG), (3, _DIAG, _DIAG)),  # bite 1: left-down, right-down
    ((0, _DIAG, _DIAG), (3, -_DIAG, -_DIAG)),  # bite 2: right-down, left-up
)


@dataclass
class FruitCrumb:
    wx: float
    wy: float
    vwx: float
    vwy: float
    kind: int
    quarter: int
    scale: float = 1.0
    air_t: float = 0.0
    land_t: float = 0.0
    landed: bool = False

    def jump_z(self) -> float:
        if self.landed:
            return 0.0
        t = min(1.0, self.air_t / CRUMB_AIR_DURATION)
        return CRUMB_JUMP_HEIGHT * math.sin(math.pi * t)

    def update(self, dt: float) -> bool:
        if not self.landed:
            self.air_t += dt
            self.wx = (self.wx + self.vwx * dt) % WORLD_SIZE
            self.wy = (self.wy + self.vwy * dt) % WORLD_SIZE
            if self.air_t >= CRUMB_AIR_DURATION:
                self.landed = True
                self.wx, self.wy = wrap_pos(self.wx, self.wy)
                self.land_t = 0.0
            return False
        self.land_t += dt
        return self.land_t >= CRUMB_LAND_DURATION


def _append_crumb(
    crumbs: list[FruitCrumb],
    wx: float,
    wy: float,
    kind: int,
    quarter: int,
    svx: float,
    svy: float,
    cam_deg: float,
    scale: float,
    speed_mult: float,
    angle_jitter: float,
    heading_deg: float,
    snake_speed: float,
    focus_x: float,
    focus_y: float,
) -> None:
    angle = math.atan2(svy, svx) + random.uniform(-angle_jitter, angle_jitter)
    speed = CRUMB_SCREEN_SPEED * speed_mult * random.uniform(0.7, 1.05)
    vsx = math.cos(angle) * speed
    vsy = math.sin(angle) * speed
    carry_svx, carry_svy = screen_velocity_for_world_heading(
        heading_deg, snake_speed * CRUMB_SNAKE_CARRY, wx, wy, focus_x, focus_y, cam_deg
    )
    vsx += carry_svx
    vsy += carry_svy
    vwx, vwy = world_velocity_for_screen_velocity(vsx, vsy, cam_deg)
    crumbs.append(
        FruitCrumb(
            wx=wx + random.uniform(-0.12, 0.12),
            wy=wy + random.uniform(-0.12, 0.12),
            vwx=vwx,
            vwy=vwy,
            kind=kind,
            quarter=quarter,
            scale=scale,
        )
    )


def spawn_bite_crumbs(
    crumbs: list[FruitCrumb],
    wx: float,
    wy: float,
    kind: int,
    bite: int,
    cam_deg: float,
    heading_deg: float,
    snake_speed: float,
    focus_x: float,
    focus_y: float,
) -> None:
    if bite < 0 or bite >= len(BITE_CRUMBS):
        return
    wx, wy = world_pos_screen_ahead(
        wx, wy, heading_deg, CRUMB_SPAWN_AHEAD_PX, focus_x, focus_y, cam_deg
    )
    for quarter, svx, svy in BITE_CRUMBS[bite]:
        _append_crumb(
            crumbs, wx, wy, kind, quarter, svx, svy, cam_deg,
            scale=1.0, speed_mult=1.0, angle_jitter=0.0,
            heading_deg=heading_deg, snake_speed=snake_speed,
            focus_x=focus_x, focus_y=focus_y,
        )
        for _ in range(random.randint(*SMALL_CRUMBS_PER_BIG)):
            _append_crumb(
                crumbs,
                wx,
                wy,
                kind,
                quarter,
                svx,
                svy,
                cam_deg,
                scale=SMALL_CRUMB_SCALE,
                speed_mult=random.uniform(0.75, 1.25),
                angle_jitter=0.65,
                heading_deg=heading_deg,
                snake_speed=snake_speed,
                focus_x=focus_x,
                focus_y=focus_y,
            )
