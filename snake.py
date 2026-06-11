import math
from dataclasses import dataclass
from enum import Enum, auto

from crumbs import FruitCrumb, spawn_bite_crumbs
from iso import mouth_screen_pos, screen_dist_for_eat
from sprites import BOB_AMP, HOVER_LIFT, SHADOW_BIG, SHADOW_MED, shadow_for_bob
from world import WORLD_SIZE, toroidal_delta, toroidal_dist, wrap_pos

SNAKE_SPEED = 10.0
TURN_SPEED = 120.0
SEGMENT_SPACING = 2
# Visual width in px per tail sprite index (0,1 = reserved; 2 = tail_02 … 5 = tail_05).
TAIL_SPRITE_WIDTHS = (0, 14, 12, 8, 6, 4)
TAIL_SPRITE_MIN = 2
TAIL_SPRITE_MAX = 5
TAIL_DIGEST = 0
WAVE_AMP = 1.4
WAVE_PERIOD = 1.5
WAVE_SEGMENT_PHASE = 1.0
WAVE_SCALE_LERP_HEAD = 14.0
WAVE_SCALE_LERP_TAIL = 2.5
TRAIL_MARGIN = SEGMENT_SPACING
EAT_RADIUS = 12.0
EAT_WORLD_RADIUS = 5.0
MOUTH_OPEN_BEFORE = 8.0
FRUIT_PULL_SPEED = 140.0
FRUIT_ARRIVE_PX = 2.0
EAT_FRUIT_SCALE_END = 0.25
NUM_SEGMENTS = 3


@dataclass
class PathNode:
    cx: float
    cy: float
    heading_deg: float
    lateral: float
    arc_s: float


@dataclass
class DigestItem:
    arc: float

    def segment_index(self, num_segments: int) -> int | None:
        idx = int(self.arc / SEGMENT_SPACING) - 1
        if idx < 0 or idx >= num_segments:
            return None
        return idx


class PathNodes:
    """Spine path nodes with per-point heading and lateral offset.

    Forward: append nodes as the head moves. Reverse (future): read nodes backward
    with move_sign=-1 without appending new nodes.
    """

    def __init__(self) -> None:
        self._nodes: list[PathNode] = []

    def clear(self) -> None:
        self._nodes.clear()

    @property
    def total_length(self) -> float:
        if len(self._nodes) < 2:
            return 0.0
        return self._nodes[-1].arc_s - self._nodes[0].arc_s

    @staticmethod
    def _segment_length(x0: float, y0: float, x1: float, y1: float) -> float:
        dx = toroidal_delta(x1, x0)
        dy = toroidal_delta(y1, y0)
        return math.hypot(dx, dy)

    @staticmethod
    def _lerp_angle(deg0: float, deg1: float, t: float) -> float:
        delta = (deg1 - deg0 + 180.0) % 360.0 - 180.0
        return (deg0 + delta * t) % 360.0

    @staticmethod
    def node_visual_pos(node: PathNode, amp_scale: float) -> tuple[float, float]:
        rad = math.radians(node.heading_deg)
        lx, ly = -math.sin(rad), math.cos(rad)
        offset = node.lateral * amp_scale
        return wrap_pos(node.cx + lx * offset, node.cy + ly * offset)

    def append(self, cx: float, cy: float, heading_deg: float, lateral: float) -> None:
        cx, cy = wrap_pos(cx, cy)
        if not self._nodes:
            self._nodes.append(PathNode(cx, cy, heading_deg, lateral, 0.0))
            return
        prev = self._nodes[-1]
        ds = self._segment_length(prev.cx, prev.cy, cx, cy)
        if ds < 0.0001:
            return
        self._nodes.append(PathNode(cx, cy, heading_deg, lateral, prev.arc_s + ds))

    def trim(self, required_length: float) -> None:
        while len(self._nodes) >= 2 and self.total_length > required_length:
            self._nodes.pop(0)
        if self._nodes:
            base_s = self._nodes[0].arc_s
            if base_s != 0.0:
                self._nodes = [
                    PathNode(n.cx, n.cy, n.heading_deg, n.lateral, n.arc_s - base_s) for n in self._nodes
                ]

    def sample_node(self, dist_behind: float) -> PathNode | None:
        if not self._nodes:
            return None
        head_s = self._nodes[-1].arc_s
        if dist_behind > head_s + 0.001:
            return None
        target_s = head_s - dist_behind
        if target_s <= 0.0:
            return self._nodes[0]
        for i in range(len(self._nodes) - 1, 0, -1):
            n0 = self._nodes[i - 1]
            n1 = self._nodes[i]
            if n0.arc_s <= target_s <= n1.arc_s:
                span = n1.arc_s - n0.arc_s
                t = (target_s - n0.arc_s) / span if span > 0.0 else 0.0
                dx = toroidal_delta(n1.cx, n0.cx)
                dy = toroidal_delta(n1.cy, n0.cy)
                cx, cy = wrap_pos(n0.cx + dx * t, n0.cy + dy * t)
                return PathNode(
                    cx,
                    cy,
                    self._lerp_angle(n0.heading_deg, n1.heading_deg, t),
                    n0.lateral + (n1.lateral - n0.lateral) * t,
                    target_s,
                )
        return self._nodes[0]

    def sample_pos(self, dist_behind: float, amp_scale: float) -> tuple[float, float] | None:
        node = self.sample_node(dist_behind)
        if node is None:
            return None
        return self.node_visual_pos(node, amp_scale)


class MouthState(Enum):
    CLOSED = auto()
    APPROACH = auto()
    EATING = auto()


class EatAnimation:
    SEQUENCE = [
        (True, 0.08),
        (False, 0.06),
        (True, 0.08),
        (False, 0.06),
        (True, 0.08),
        (False, 0.0),
    ]

    def __init__(self) -> None:
        self.playing = False
        self.index = 0
        self.phase_time = 0.0
        self.is_open = False

    def start(self) -> None:
        self.playing = True
        self.index = 0
        self.phase_time = 0.0
        self.is_open = self.SEQUENCE[0][0]

    @classmethod
    def total_duration(cls) -> float:
        return sum(duration for _, duration in cls.SEQUENCE)

    def update(self, dt: float) -> tuple[bool, list[int]]:
        if not self.playing:
            return False, []

        chomps: list[int] = []
        self.phase_time += dt
        while self.index < len(self.SEQUENCE) and self.phase_time >= self.SEQUENCE[self.index][1]:
            self.phase_time -= self.SEQUENCE[self.index][1]
            prev = self.index
            self.index += 1
            if prev % 2 == 0:
                chomps.append(prev // 2)

        if self.index >= len(self.SEQUENCE):
            self.playing = False
            self.is_open = False
            return True, chomps

        self.is_open = self.SEQUENCE[self.index][0]
        return False, chomps


class Snake:
    def __init__(self, wx: float, wy: float, heading_deg: float = 0.0, num_segments: int = NUM_SEGMENTS) -> None:
        self.head_x, self.head_y = wrap_pos(wx, wy)
        self.heading_deg = heading_deg
        self.move_sign = 1
        self.wave_time = 0.0
        self._path = PathNodes()
        self._lateral_wave_scales = [1.0] * (num_segments + 1)
        self.segments: list[tuple[float, float]] = []
        rad = math.radians(self.heading_deg)
        for i in range(num_segments):
            back = self.segment_arc_distance_at(i, num_segments)
            sx = self.head_x - math.cos(rad) * back
            sy = self.head_y - math.sin(rad) * back
            self.segments.append(wrap_pos(sx, sy))
        self._seed_path()

        self.mouth_state = MouthState.CLOSED
        self.eat_anim = EatAnimation()
        self.eating_fruit_index: int | None = None
        self.eating_fruit_kind: int | None = None
        self.eating_fruit_sx = 0.0
        self.eating_fruit_sy = 0.0
        self.eating_fruit_arrived = False
        self._eating_shrink_elapsed = 0.0
        self._eating_shrink_duration = 0.36
        self.eat_crumbs: list[FruitCrumb] = []

        self._digest_items: list[DigestItem] = []
        self._digest_waiting: list[None] = []

    @property
    def move_speed(self) -> float:
        return SNAKE_SPEED

    def _digest_threshold(self) -> float:
        return (len(self.segments) + 1) * SEGMENT_SPACING

    def _digest_segment0_blocked(self) -> bool:
        for item in self._digest_items:
            if item.arc < 2 * SEGMENT_SPACING:
                return True
        return False

    def _start_digest(self) -> None:
        if self._digest_segment0_blocked():
            self._digest_waiting.append(None)
        else:
            self._digest_items.append(DigestItem(0.0))

    @staticmethod
    def _tail_sprite_width(tail_index: int) -> float:
        idx = max(TAIL_SPRITE_MIN, min(tail_index, len(TAIL_SPRITE_WIDTHS) - 1))
        return float(TAIL_SPRITE_WIDTHS[idx])

    def segment_gap_before(self, seg_i: int, num_segments: int) -> float:
        curr_idx = self._segment_tail_base_index_at(seg_i, num_segments)
        if seg_i == 0:
            return SEGMENT_SPACING
        prev_idx = self._segment_tail_base_index_at(seg_i - 1, num_segments)
        prev_w = self._tail_sprite_width(prev_idx)
        curr_w = self._tail_sprite_width(curr_idx)
        base_w = float(TAIL_SPRITE_WIDTHS[TAIL_SPRITE_MIN])
        return SEGMENT_SPACING * (prev_w + curr_w) / (2.0 * base_w)

    def _segment_tail_base_index_at(self, seg_i: int, num_segments: int) -> int:
        usable = TAIL_SPRITE_MAX - TAIL_SPRITE_MIN + 1
        if num_segments <= usable:
            return TAIL_SPRITE_MIN + seg_i
        t = seg_i / max(1, num_segments - 1)
        if t < 0.35:
            tier = 1
        elif t < 0.55:
            tier = 2
        else:
            u = (t - 0.55) / 0.45
            tier = 3 + min(2, int(u * 2.99))
        return min(TAIL_SPRITE_MAX, tier + TAIL_SPRITE_MIN - 1)

    def segment_arc_distance_at(self, seg_i: int, num_segments: int) -> float:
        return sum(self.segment_gap_before(i, num_segments) for i in range(seg_i + 1))

    def segment_arc_distance(self, seg_i: int) -> float:
        return self.segment_arc_distance_at(seg_i, len(self.segments))

    def _segment_tail_base_index(self, seg_i: int) -> int:
        return self._segment_tail_base_index_at(seg_i, len(self.segments))

    def _is_digesting_segment(self, seg_i: int) -> bool:
        n = len(self.segments)
        for item in self._digest_items:
            if item.segment_index(n) == seg_i:
                return True
        return False

    def segment_tail_index(self, seg_i: int) -> int:
        base = self._segment_tail_base_index(seg_i)
        if self._is_digesting_segment(seg_i):
            dig = base - 1
            return TAIL_DIGEST if dig < TAIL_SPRITE_MIN else dig
        return base

    def segment_draws_shadow(self, seg_i: int) -> bool:
        tail_idx = self.segment_tail_index(seg_i)
        if tail_idx <= TAIL_SPRITE_MIN + 1:
            return True
        return seg_i % 2 == 0

    def segment_shadow(self, seg_i: int, bob: float) -> int:
        base = SHADOW_BIG if self.segment_tail_index(seg_i) == TAIL_DIGEST else SHADOW_MED
        return shadow_for_bob(base, bob)

    def _update_digest(self, dt: float) -> None:
        step = self.move_speed * dt
        for item in self._digest_items:
            item.arc += step

        while True:
            threshold = self._digest_threshold()
            completed = [item for item in self._digest_items if item.arc >= threshold]
            if not completed:
                break
            for item in completed:
                self._digest_items.remove(item)
                self.grow(1)

        while self._digest_waiting and not self._digest_segment0_blocked():
            self._digest_waiting.pop(0)
            self._digest_items.append(DigestItem(SEGMENT_SPACING))

    def _path_required_length(self) -> float:
        return len(self.segments) * SEGMENT_SPACING + TRAIL_MARGIN

    def _record_lateral(self) -> float:
        return WAVE_AMP * self._lateral_wave_scale(0) * math.sin(self._wave_phase(0))

    def _seed_path(self) -> None:
        self._path.append(self.head_x, self.head_y, self.heading_deg, 0.0)
        rad = math.radians(self.heading_deg)
        n = len(self.segments)
        for i in range(1, n + 2):
            if i <= n:
                back = self.segment_arc_distance_at(i - 1, n)
            else:
                back = self.segment_arc_distance_at(n - 1, n) + (i - n) * SEGMENT_SPACING
            sx = self.head_x - math.cos(rad) * back
            sy = self.head_y - math.sin(rad) * back
            self._path.append(sx, sy, self.heading_deg, 0.0)

    def grow(self, n: int = 1) -> None:
        for _ in range(n):
            new_i = len(self.segments)
            dist = self.segment_arc_distance_at(new_i, new_i + 1)
            pos = self._path.sample_pos(dist, 1.0)
            if pos is None:
                if self.segments:
                    front_x, front_y = self.segments[-1]
                else:
                    front_x, front_y = self.head_x, self.head_y
                rad = math.radians(self.heading_deg)
                pos = wrap_pos(
                    front_x - math.cos(rad) * SEGMENT_SPACING,
                    front_y - math.sin(rad) * SEGMENT_SPACING,
                )
            self.segments.append(pos)
            self._lateral_wave_scales.append(self._lateral_wave_scales[-1])
        self._path.trim(self._path_required_length())

    def positions(self) -> list[tuple[float, float]]:
        return [(self.head_x, self.head_y)] + self.segments

    def _heading_vector(self) -> tuple[float, float]:
        rad = math.radians(self.heading_deg)
        return math.cos(rad), math.sin(rad)

    def _lateral_vector(self) -> tuple[float, float]:
        vx, vy = self._heading_vector()
        return -vy, vx

    def _wave_phase(self, seg_index: int) -> float:
        omega = 2 * math.pi / WAVE_PERIOD
        return self.wave_time * omega - seg_index * WAVE_SEGMENT_PHASE

    def _amplitude_scale(self, seg_index: int) -> float:
        if seg_index <= 0:
            return 1.0 / 3.0
        if seg_index == 1:
            return 2.0 / 3.0
        return 1.0

    def _lateral_wave_scale(self, seg_index: int) -> float:
        return self._lateral_wave_scales[min(seg_index, len(self.segments))]

    def _update_lateral_wave_scales(self, dt: float, turn: float) -> None:
        head_target = 1.0 if abs(turn) < 0.01 else 0.0
        head_t = 1 - math.exp(-WAVE_SCALE_LERP_HEAD * dt)
        self._lateral_wave_scales[0] += (head_target - self._lateral_wave_scales[0]) * head_t
        tail_t = 1 - math.exp(-WAVE_SCALE_LERP_TAIL * dt)
        for i in range(1, len(self.segments) + 1):
            prev = self._lateral_wave_scales[i - 1]
            self._lateral_wave_scales[i] += (prev - self._lateral_wave_scales[i]) * tail_t

    def serpentine_world_offset(self, seg_index: int) -> tuple[float, float]:
        """Head-only lateral wave (1/3 amp); body follows path nodes."""
        lx, ly = self._lateral_vector()
        amp = (
            WAVE_AMP
            * self._amplitude_scale(seg_index)
            * self._lateral_wave_scale(seg_index)
            * math.sin(self._wave_phase(seg_index))
        )
        return lx * amp, ly * amp

    def wave_bob_offset(self, seg_index: int = 0) -> float:
        scale = self._amplitude_scale(seg_index)
        return BOB_AMP * scale * math.cos(2 * self._wave_phase(seg_index))

    def hover_screen_y(self, ground_sy: float, seg_index: int = 0) -> float:
        return ground_sy - HOVER_LIFT + self.wave_bob_offset(seg_index)

    def _move_head(self, dt: float) -> None:
        self.wave_time += dt
        vx, vy = self._heading_vector()
        self.head_x = (self.head_x + vx * self.move_speed * dt) % WORLD_SIZE
        self.head_y = (self.head_y + vy * self.move_speed * dt) % WORLD_SIZE

    def _record_path(self) -> None:
        self._path.append(self.head_x, self.head_y, self.heading_deg, self._record_lateral())
        self._path.trim(self._path_required_length())

    def _place_segment(self, front_x: float, front_y: float, seg_x: float, seg_y: float) -> tuple[float, float]:
        dx = toroidal_delta(front_x, seg_x)
        dy = toroidal_delta(front_y, seg_y)
        dist = math.hypot(dx, dy)
        if dist < 0.001:
            rad = math.radians(self.heading_deg)
            sx = front_x - math.cos(rad) * SEGMENT_SPACING
            sy = front_y - math.sin(rad) * SEGMENT_SPACING
            return wrap_pos(sx, sy)
        nx = front_x - dx / dist * SEGMENT_SPACING
        ny = front_y - dy / dist * SEGMENT_SPACING
        return wrap_pos(nx, ny)

    def _update_segments(self) -> None:
        front_x, front_y = self.head_x, self.head_y
        for i in range(len(self.segments)):
            dist = self.segment_arc_distance(i)
            seg_index = i + 1
            pos = self._path.sample_pos(dist, self._amplitude_scale(seg_index))
            if pos is not None:
                self.segments[i] = pos
                front_x, front_y = pos
            else:
                self.segments[i] = self._place_segment(front_x, front_y, self.segments[i][0], self.segments[i][1])
                front_x, front_y = self.segments[i]

    def _nearest_fruit(
        self, fruits: list, focus_x: float, focus_y: float, cam_deg: float, claimed_fruit_indices: set[int]
    ) -> tuple[int | None, float, float, float]:
        best_i: int | None = None
        best_dist = float("inf")
        best_sx = 0.0
        best_sy = 0.0
        for i, fruit in enumerate(fruits):
            if i in claimed_fruit_indices:
                continue
            if not fruit.collectible:
                continue
            if toroidal_dist(self.head_x, self.head_y, fruit.wx, fruit.wy) > EAT_WORLD_RADIUS:
                continue
            d, fsx, fsy = screen_dist_for_eat(
                fruit.wx, fruit.wy, self.head_x, self.head_y, focus_x, focus_y, cam_deg
            )
            if d < best_dist:
                best_dist = d
                best_i = i
                best_sx, best_sy = fsx, fsy
        return best_i, best_dist, best_sx, best_sy

    def _update_eat_crumbs(self, dt: float) -> None:
        self.eat_crumbs = [c for c in self.eat_crumbs if not c.update(dt)]

    def update(
        self,
        dt: float,
        fruits: list,
        focus_x: float,
        focus_y: float,
        cam_deg: float,
        turn: float = 0.0,
        claimed_fruit_indices: set[int] | None = None,
    ) -> int | None:
        claimed = claimed_fruit_indices if claimed_fruit_indices is not None else set()
        self.heading_deg = (self.heading_deg + turn * TURN_SPEED * dt) % 360
        self._update_lateral_wave_scales(dt, turn)

        self._move_head(dt)
        self._record_path()
        self._update_segments()
        self._update_digest(dt)
        self._update_eat_crumbs(dt)

        if self.mouth_state == MouthState.EATING:
            mouth_sx, mouth_sy = mouth_screen_pos(
                self.head_x, self.head_y, self.heading_deg, focus_x, focus_y, cam_deg
            )
            self._eating_shrink_elapsed += dt
            if not self.eating_fruit_arrived:
                dx = mouth_sx - self.eating_fruit_sx
                dy = mouth_sy - self.eating_fruit_sy
                dist = math.hypot(dx, dy)
                step = FRUIT_PULL_SPEED * dt
                if dist <= FRUIT_ARRIVE_PX or step >= dist:
                    self.eating_fruit_sx, self.eating_fruit_sy = mouth_sx, mouth_sy
                    self.eating_fruit_arrived = True
                else:
                    self.eating_fruit_sx += dx / dist * step
                    self.eating_fruit_sy += dy / dist * step
            else:
                self.eating_fruit_sx, self.eating_fruit_sy = mouth_sx, mouth_sy

            finished, chomps = self.eat_anim.update(dt)
            for bite in chomps:
                if self.eating_fruit_kind is not None:
                    spawn_bite_crumbs(
                        self.eat_crumbs,
                        self.head_x,
                        self.head_y,
                        self.eating_fruit_kind,
                        bite,
                        cam_deg,
                        self.heading_deg,
                        self.move_speed,
                        focus_x,
                        focus_y,
                    )
            if finished:
                self.mouth_state = MouthState.CLOSED
                idx = self.eating_fruit_index
                self.eating_fruit_index = None
                self.eating_fruit_kind = None
                self.eating_fruit_arrived = False
                self._eating_shrink_elapsed = 0.0
                self._start_digest()
                return idx
            return None

        nearest_i, nearest_dist, fruit_sx, fruit_sy = self._nearest_fruit(
            fruits, focus_x, focus_y, cam_deg, claimed
        )
        if nearest_i is None:
            self.mouth_state = MouthState.CLOSED
            return None

        if nearest_dist <= EAT_RADIUS:
            fruit = fruits[nearest_i]
            self.mouth_state = MouthState.EATING
            self.eating_fruit_index = nearest_i
            self.eating_fruit_kind = fruit.kind
            self.eating_fruit_sx, self.eating_fruit_sy = fruit_sx, fruit_sy
            self.eating_fruit_arrived = False
            mouth_sx, mouth_sy = mouth_screen_pos(
                self.head_x, self.head_y, self.heading_deg, focus_x, focus_y, cam_deg
            )
            pull_dist = math.hypot(mouth_sx - fruit_sx, mouth_sy - fruit_sy)
            pull_time = pull_dist / FRUIT_PULL_SPEED if pull_dist > 0.001 else 0.0
            self._eating_shrink_duration = pull_time + EatAnimation.total_duration()
            self._eating_shrink_elapsed = 0.0
            self.eat_anim.start()
            return None

        if nearest_dist <= EAT_RADIUS + MOUTH_OPEN_BEFORE:
            self.mouth_state = MouthState.APPROACH
        else:
            self.mouth_state = MouthState.CLOSED

        return None

    def mouth_open(self) -> bool:
        if self.mouth_state == MouthState.EATING:
            return self.eat_anim.is_open
        if self.mouth_state == MouthState.APPROACH:
            return True
        return False

    def eating_fruit_scale(self) -> float:
        if self.mouth_state != MouthState.EATING:
            return 1.0
        t = min(1.0, self._eating_shrink_elapsed / max(self._eating_shrink_duration, 0.001))
        return 1.0 + (EAT_FRUIT_SCALE_END - 1.0) * t

    def eating_fruit_draw(self) -> tuple[float, float, int, float] | None:
        if self.mouth_state == MouthState.EATING and self.eating_fruit_kind is not None:
            return self.eating_fruit_sx, self.eating_fruit_sy, self.eating_fruit_kind, self.eating_fruit_scale()
        return None
