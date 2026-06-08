import math

from snake import SNAKE_SPEED
from world import WORLD_SIZE, toroidal_delta, wrap_pos

CAM_LEAD_FACTOR = 1.0
CAM_POS_LERP = 1.8
# Iso projection: heading alone maps forward to screen-right; +135° puts it up.
CAM_HEADING_OFFSET = 135.0
CAM_ROT_MAX_SPEED = 60.0
CAM_ROT_ACCEL = 120.0
CAM_ROT_END_RADIUS = 20.0
CAM_ROT_END_POWER = 2.5
CAM_ROT_SNAP_ERROR = 0.3
CAM_ROT_SNAP_VEL = 1.0


def cam_target_deg(heading_deg: float) -> float:
    return heading_deg + CAM_HEADING_OFFSET


def lead_point(head_x: float, head_y: float, heading_deg: float) -> tuple[float, float]:
    rad = math.radians(heading_deg)
    lead = CAM_LEAD_FACTOR * SNAKE_SPEED
    return wrap_pos(head_x + math.cos(rad) * lead, head_y + math.sin(rad) * lead)


def angle_diff(from_deg: float, to_deg: float) -> float:
    return (to_deg - from_deg + 180.0) % 360.0 - 180.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _update_cam_rotation(cam_deg: float, cam_rot_vel: float, target_deg: float, dt: float) -> tuple[float, float]:
    error = angle_diff(cam_deg, target_deg)

    if abs(error) < CAM_ROT_SNAP_ERROR and abs(cam_rot_vel) < CAM_ROT_SNAP_VEL:
        return target_deg, 0.0

    t = min(1.0, abs(error) / CAM_ROT_END_RADIUS)
    speed_cap = CAM_ROT_MAX_SPEED * (t**CAM_ROT_END_POWER)
    desired_vel = math.copysign(speed_cap, error)

    dv = desired_vel - cam_rot_vel
    cam_rot_vel += _clamp(dv, -CAM_ROT_ACCEL * dt, CAM_ROT_ACCEL * dt)

    step = cam_rot_vel * dt
    if abs(step) > abs(error):
        step = error
        cam_rot_vel = 0.0

    return cam_deg + step, cam_rot_vel


def update_camera(
    cam_x: float,
    cam_y: float,
    cam_deg: float,
    cam_rot_vel: float,
    head_x: float,
    head_y: float,
    heading_deg: float,
    dt: float,
) -> tuple[float, float, float, float]:
    target_x, target_y = lead_point(head_x, head_y, heading_deg)
    target_deg = cam_target_deg(heading_deg)

    pos_t = 1 - math.exp(-CAM_POS_LERP * dt)
    cam_x = (cam_x + toroidal_delta(target_x, cam_x) * pos_t) % WORLD_SIZE
    cam_y = (cam_y + toroidal_delta(target_y, cam_y) * pos_t) % WORLD_SIZE

    cam_deg, cam_rot_vel = _update_cam_rotation(cam_deg, cam_rot_vel, target_deg, dt)

    return cam_x, cam_y, cam_deg, cam_rot_vel
