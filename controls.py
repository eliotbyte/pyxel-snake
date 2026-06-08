import math

import pyxel

from world import toroidal_delta, toroidal_dist


def _angle_diff(from_deg: float, to_deg: float) -> float:
    return (to_deg - from_deg + 180.0) % 360.0 - 180.0


def player_turn_input() -> float:
    turn = 0.0
    if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
        turn -= 1.0
    if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
        turn += 1.0
    return turn


def assign_ai_fruit_targets(ai_snakes: list, fruits: list, skip_indices: set[int]) -> list[int | None]:
    claimed = set(skip_indices)
    targets: list[int | None] = []
    for snake in ai_snakes:
        best_i: int | None = None
        best_dist = float("inf")
        for i, fruit in enumerate(fruits):
            if i in claimed:
                continue
            d = toroidal_dist(snake.head_x, snake.head_y, fruit.wx, fruit.wy)
            if d < best_dist:
                best_dist = d
                best_i = i
        if best_i is not None:
            claimed.add(best_i)
        targets.append(best_i)
    return targets


def ai_turn_toward_fruit_target(
    head_x: float,
    head_y: float,
    heading_deg: float,
    fruits: list,
    fruit_index: int | None,
) -> float:
    if fruit_index is None or fruit_index < 0 or fruit_index >= len(fruits):
        return 0.0

    fruit = fruits[fruit_index]
    dx = toroidal_delta(fruit.wx, head_x)
    dy = toroidal_delta(fruit.wy, head_y)
    target = math.degrees(math.atan2(dy, dx)) % 360
    diff = _angle_diff(heading_deg, target)
    if abs(diff) < 4.0:
        return 0.0
    return 1.0 if diff > 0 else -1.0
