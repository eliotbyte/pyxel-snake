import math

from world import WORLD_SIZE, toroidal_delta, wrap_pos

ISO_X = 4.0
ISO_Y = 2.0
SCREEN_CX = 128
SCREEN_CY = 108
MOUTH_AHEAD_PX = 4.0


def init_screen_center(width: int, height: int) -> None:
    global SCREEN_CX, SCREEN_CY
    SCREEN_CX = width // 2
    SCREEN_CY = height // 2 + 8


def _project_relative(drx: float, dry: float, cam_deg: float) -> tuple[float, float]:
    rad = math.radians(cam_deg)
    crx = drx * math.cos(rad) + dry * math.sin(rad)
    cry = -drx * math.sin(rad) + dry * math.cos(rad)
    sx = (crx - cry) * ISO_X + SCREEN_CX
    sy = (crx + cry) * ISO_Y + SCREEN_CY
    return sx, sy


def world_to_screen_focused(
    wx: float, wy: float, focus_x: float, focus_y: float, cam_deg: float
) -> tuple[float, float]:
    drx = toroidal_delta(wx, focus_x)
    dry = toroidal_delta(wy, focus_y)
    return _project_relative(drx, dry, cam_deg)


def screen_dist_to_focus(wx: float, wy: float, focus_x: float, focus_y: float, cam_deg: float) -> float:
    drx = toroidal_delta(wx, focus_x)
    dry = toroidal_delta(wy, focus_y)
    sx, sy = _project_relative(drx, dry, cam_deg)
    return math.hypot(sx - SCREEN_CX, sy - SCREEN_CY)


def screen_dist_between(
    wx1: float, wy1: float, wx2: float, wy2: float, focus_x: float, focus_y: float, cam_deg: float
) -> float:
    sx1, sy1 = world_to_screen_focused(wx1, wy1, focus_x, focus_y, cam_deg)
    sx2, sy2 = world_to_screen_focused(wx2, wy2, focus_x, focus_y, cam_deg)
    return math.hypot(sx1 - sx2, sy1 - sy2)


def screen_dist_for_eat(
    fruit_wx: float,
    fruit_wy: float,
    head_wx: float,
    head_wy: float,
    focus_x: float,
    focus_y: float,
    cam_deg: float,
) -> tuple[float, float, float]:
    """Screen eat distance using the same visible head/fruit copies as draw."""
    hsx, hsy = entity_screen_pos(head_wx, head_wy, focus_x, focus_y, cam_deg)
    fruit_base_rx = fruit_wx - focus_x
    fruit_base_ry = fruit_wy - focus_y
    best_d = float("inf")
    best_fsx = 0.0
    best_fsy = 0.0
    for fox in (-WORLD_SIZE, 0, WORLD_SIZE):
        for foy in (-WORLD_SIZE, 0, WORLD_SIZE):
            fsx, fsy = _project_relative(fruit_base_rx + fox, fruit_base_ry + foy, cam_deg)
            d = math.hypot(fsx - hsx, fsy - hsy)
            if d < best_d:
                best_d = d
                best_fsx, best_fsy = fsx, fsy
    return best_d, best_fsx, best_fsy


def entity_screen_pos(wx: float, wy: float, focus_x: float, focus_y: float, cam_deg: float) -> tuple[float, float]:
    """Screen position of the wrap copy closest to viewport center (matches draw)."""
    base_rx = wx - focus_x
    base_ry = wy - focus_y
    best_d = float("inf")
    best_sx = 0.0
    best_sy = 0.0
    for ox in (-WORLD_SIZE, 0, WORLD_SIZE):
        for oy in (-WORLD_SIZE, 0, WORLD_SIZE):
            sx, sy = _project_relative(base_rx + ox, base_ry + oy, cam_deg)
            d = math.hypot(sx - SCREEN_CX, sy - SCREEN_CY)
            if d < best_d:
                best_d = d
                best_sx, best_sy = sx, sy
    return best_sx, best_sy


def iter_screen_positions(
    wx: float,
    wy: float,
    focus_x: float,
    focus_y: float,
    cam_deg: float,
    margin: float = 32,
    screen_w: int = 256,
    screen_h: int = 200,
):
    base_rx = wx - focus_x
    base_ry = wy - focus_y
    seen: set[tuple[int, int]] = set()

    for ox in (-WORLD_SIZE, 0, WORLD_SIZE):
        for oy in (-WORLD_SIZE, 0, WORLD_SIZE):
            drx = base_rx + ox
            dry = base_ry + oy
            sx, sy = _project_relative(drx, dry, cam_deg)
            key = (round(sx * 2), round(sy * 2))
            if key in seen:
                continue
            if -margin <= sx < screen_w + margin and -margin <= sy < screen_h + margin:
                seen.add(key)
                yield sx, sy


def angle_to_dir(angle_deg: float) -> int:
    """Map screen angle (0=right, 90=down) to head frame 0=down, clockwise."""
    angle_deg = angle_deg % 360
    dir_idx = int((90 - angle_deg + 11.25) // 22.5) % 16
    return (16 - dir_idx) % 16


def movement_screen_dir(heading_deg: float, cam_deg: float) -> int:
    rad = math.radians(heading_deg)
    dwx = math.cos(rad)
    dwy = math.sin(rad)
    crad = math.radians(cam_deg)
    crx = dwx * math.cos(crad) + dwy * math.sin(crad)
    cry = -dwx * math.sin(crad) + dwy * math.cos(crad)
    dsx = (crx - cry) * ISO_X
    dsy = (crx + cry) * ISO_Y
    if abs(dsx) < 1e-9 and abs(dsy) < 1e-9:
        return 0
    screen_deg = math.degrees(math.atan2(dsy, dsx)) % 360
    return angle_to_dir(screen_deg)


def screen_velocity_for_world_heading(
    heading_deg: float,
    world_speed: float,
    wx: float,
    wy: float,
    focus_x: float,
    focus_y: float,
    cam_deg: float,
) -> tuple[float, float]:
    """World motion along heading → screen px/s at the given world position."""
    rad = math.radians(heading_deg)
    vwx = math.cos(rad) * world_speed
    vwy = math.sin(rad) * world_speed
    sx0, sy0 = world_to_screen_focused(wx, wy, focus_x, focus_y, cam_deg)
    sx1, sy1 = world_to_screen_focused(
        (wx + vwx) % WORLD_SIZE, (wy + vwy) % WORLD_SIZE, focus_x, focus_y, cam_deg
    )
    return sx1 - sx0, sy1 - sy0


def world_velocity_for_screen_velocity(vsx: float, vsy: float, cam_deg: float) -> tuple[float, float]:
    """Map constant screen px/s to world units/s for the current camera."""
    rad = math.radians(cam_deg)
    c, s = math.cos(rad), math.sin(rad)
    a = ISO_X * (c + s)
    b = ISO_X * (s - c)
    d = ISO_Y * (c - s)
    e = ISO_Y * (s + c)
    det = a * e - b * d
    if abs(det) < 1e-9:
        return 0.0, 0.0
    vwx = (vsx * e - vsy * b) / det
    vwy = (-vsx * d + vsy * a) / det
    return vwx, vwy


def screen_movement_unit(
    heading_deg: float,
    wx: float,
    wy: float,
    focus_x: float,
    focus_y: float,
    cam_deg: float,
) -> tuple[float, float]:
    """Unit screen vector for world heading (sprite mirror not applied)."""
    vsx, vsy = screen_velocity_for_world_heading(heading_deg, 1.0, wx, wy, focus_x, focus_y, cam_deg)
    speed = math.hypot(vsx, vsy)
    if speed < 1e-9:
        return 0.0, 0.0
    return vsx / speed, vsy / speed


def world_pos_screen_ahead(
    wx: float,
    wy: float,
    heading_deg: float,
    ahead_px: float,
    focus_x: float,
    focus_y: float,
    cam_deg: float,
) -> tuple[float, float]:
    """World position offset ahead_px screen pixels along movement direction."""
    ux, uy = screen_movement_unit(heading_deg, wx, wy, focus_x, focus_y, cam_deg)
    dwx, dwy = world_velocity_for_screen_velocity(ux * ahead_px, uy * ahead_px, cam_deg)
    return wrap_pos(wx + dwx, wy + dwy)


def mouth_screen_pos(
    head_wx: float, head_wy: float, heading_deg: float, focus_x: float, focus_y: float, cam_deg: float
) -> tuple[float, float]:
    hsx, hsy = entity_screen_pos(head_wx, head_wy, focus_x, focus_y, cam_deg)
    ux, uy = screen_movement_unit(heading_deg, head_wx, head_wy, focus_x, focus_y, cam_deg)
    return hsx + ux * MOUTH_AHEAD_PX, hsy + uy * MOUTH_AHEAD_PX
