import random
from enum import Enum, auto

from bubble import Bubble, BubblePhase, BUBBLE_FRUIT_HP, BUBBLE_FRUIT_HP_WEAK
from sprites import bob_y_offset
from world import spawn_fruit_room, spawn_uniform_pos

INITIAL_FRUIT_COUNT = 3
FRUIT_RESPAWN_PER_EAT = 1
FRUITS_TO_BUBBLE_PHASE = 5
EMPTY_BUBBLE_TARGET = 10
STAGGER_WINDOW = 1.0


class GamePhase(Enum):
    FRUIT = auto()
    BUBBLE = auto()
    BUBBLE_CHAIN_POP = auto()


def _stagger_interval(count: int) -> float:
    if count <= 0:
        return STAGGER_WINDOW
    return STAGGER_WINDOW / count


class GameMaster:
    """Tracks player progress and drives the fruit ↔ bubble cycle."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng if rng is not None else random
        self.phase = GamePhase.FRUIT
        self.fruits_eaten = 0
        self._chain_timer = 0.0
        self._chain_interval = STAGGER_WINDOW
        self._empty_spawn_remaining = 0
        self._empty_spawn_timer = 0.0
        self._empty_spawn_interval = STAGGER_WINDOW
        self._fruit_spawn_remaining = 0
        self._fruit_spawn_timer = 0.0
        self._fruit_spawn_interval = STAGGER_WINDOW

    @staticmethod
    def _occupied(player, fruits: list, bubbles: list) -> list[tuple[float, float]]:
        occ = list(player.positions())
        occ.extend((f.wx, f.wy) for f in fruits)
        occ.extend((b.wx, b.wy) for b in bubbles if b.is_active())
        return occ

    def _spawn_one_fruit(self, player, fruits: list, bubbles: list) -> None:
        occupied = self._occupied(player, fruits, bubbles)
        fruits.append(spawn_fruit_room(occupied, self.rng))

    def _begin_fruit_spawn_batch(self, count: int) -> None:
        self._fruit_spawn_remaining = count
        self._fruit_spawn_interval = _stagger_interval(count)
        self._fruit_spawn_timer = 0.0

    def _tick_fruit_spawn(self, dt: float, player, fruits: list, bubbles: list) -> None:
        if self._fruit_spawn_remaining <= 0:
            return
        self._fruit_spawn_timer -= dt
        if self._fruit_spawn_timer > 0.0:
            return
        self._spawn_one_fruit(player, fruits, bubbles)
        self._fruit_spawn_remaining -= 1
        self._fruit_spawn_timer = self._fruit_spawn_interval

    def _spawn_fruits(self, player, fruits: list, bubbles: list, count: int) -> None:
        if count <= 0:
            return
        if count == 1:
            self._spawn_one_fruit(player, fruits, bubbles)
        else:
            self._begin_fruit_spawn_batch(count)

    def _spawn_one_empty_bubble(self, player, fruits: list, bubbles: list) -> None:
        occupied = self._occupied(player, fruits, bubbles)
        wx, wy = spawn_uniform_pos(occupied, self.rng)
        bubble = Bubble(wx, wy, fruit_kind=None, rng=self.rng)
        bubble.begin_spawn()
        bubbles.append(bubble)

    def _begin_empty_spawn_batch(self, count: int) -> None:
        self._empty_spawn_remaining = count
        self._empty_spawn_interval = _stagger_interval(count)
        self._empty_spawn_timer = 0.0

    def _tick_empty_spawn(self, dt: float, player, fruits: list, bubbles: list) -> None:
        if self._empty_spawn_remaining <= 0:
            return
        self._empty_spawn_timer -= dt
        if self._empty_spawn_timer > 0.0:
            return
        self._spawn_one_empty_bubble(player, fruits, bubbles)
        self._empty_spawn_remaining -= 1
        self._empty_spawn_timer = self._empty_spawn_interval

    @staticmethod
    def _empty_bubble_count(bubbles: list) -> int:
        return sum(1 for b in bubbles if b.is_active() and b.fruit_kind is None)

    def _maintain_empty_bubbles(self, player, fruits: list, bubbles: list) -> None:
        if self._empty_spawn_remaining > 0:
            return
        missing = EMPTY_BUBBLE_TARGET - self._empty_bubble_count(bubbles)
        if missing <= 0:
            return
        if missing == 1:
            self._spawn_one_empty_bubble(player, fruits, bubbles)
        else:
            self._begin_empty_spawn_batch(missing)

    def start_game(self, player, fruits: list, bubbles: list) -> None:
        fruits.clear()
        bubbles.clear()
        self.phase = GamePhase.FRUIT
        self.fruits_eaten = 0
        self._chain_timer = 0.0
        self._empty_spawn_remaining = 0
        self._empty_spawn_timer = 0.0
        self._fruit_spawn_remaining = 0
        self._fruit_spawn_timer = 0.0
        self._begin_fruit_spawn_batch(INITIAL_FRUIT_COUNT)

    def on_fruit_eaten(self, player, fruits: list, bubbles: list) -> None:
        if self.phase != GamePhase.FRUIT:
            return
        self.fruits_eaten += 1
        self._spawn_fruits(player, fruits, bubbles, FRUIT_RESPAWN_PER_EAT)
        if self.fruits_eaten >= FRUITS_TO_BUBBLE_PHASE:
            self._begin_bubble_phase(player, fruits, bubbles)

    def _begin_bubble_phase(self, player, fruits: list, bubbles: list) -> None:
        fruit_list = list(fruits)
        tough_idx = self.rng.randrange(len(fruit_list)) if fruit_list else 0
        for i, fruit in enumerate(fruit_list):
            hp = BUBBLE_FRUIT_HP if i == tough_idx else BUBBLE_FRUIT_HP_WEAK
            bubble = Bubble(fruit.wx, fruit.wy, fruit_kind=fruit.kind, rng=self.rng, hp=hp)
            bubble.begin_spawn()
            bubbles.append(bubble)
        fruits.clear()
        self._fruit_spawn_remaining = 0
        self._begin_empty_spawn_batch(EMPTY_BUBBLE_TARGET)
        self.phase = GamePhase.BUBBLE
        self.fruits_eaten = 0

    def _begin_fruit_phase(self, player, fruits: list, bubbles: list) -> None:
        self.phase = GamePhase.FRUIT
        self.fruits_eaten = 0
        self._chain_timer = 0.0
        self._empty_spawn_remaining = 0
        self._empty_spawn_timer = 0.0
        self._begin_fruit_spawn_batch(INITIAL_FRUIT_COUNT)

    @staticmethod
    def _has_fruit_bubbles(bubbles: list) -> bool:
        return any(b.is_active() and b.fruit_kind is not None for b in bubbles)

    @staticmethod
    def _ready_for_chain_pop(bubbles: list, fruits: list) -> bool:
        if GameMaster._has_fruit_bubbles(bubbles):
            return False
        return len(fruits) == 0

    @staticmethod
    def _active_bubble_count(bubbles: list) -> int:
        return sum(1 for b in bubbles if b.is_active())

    def update(self, dt: float, player, fruits: list, bubbles: list, anim_t: float = 0.0) -> None:
        if self.phase == GamePhase.FRUIT:
            self._tick_fruit_spawn(dt, player, fruits, bubbles)
            return

        if self.phase == GamePhase.BUBBLE:
            self._tick_empty_spawn(dt, player, fruits, bubbles)
            if self._ready_for_chain_pop(bubbles, fruits):
                remaining = self._active_bubble_count(bubbles)
                self._chain_interval = _stagger_interval(remaining)
                self.phase = GamePhase.BUBBLE_CHAIN_POP
                self._chain_timer = 0.0
            elif self._empty_spawn_remaining <= 0:
                self._maintain_empty_bubbles(player, fruits, bubbles)
            return

        if self.phase != GamePhase.BUBBLE_CHAIN_POP:
            return

        if not any(b.is_active() for b in bubbles):
            self._begin_fruit_phase(player, fruits, bubbles)
            return

        self._chain_timer -= dt
        if self._chain_timer > 0.0:
            return

        for bubble in bubbles:
            if bubble.is_active():
                bob = bob_y_offset(anim_t) if bubble.phase == BubblePhase.IDLE else 0.0
                bubble.force_pop(bob)
                break
        self._chain_timer = self._chain_interval
