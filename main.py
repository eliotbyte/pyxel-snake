import random
import time

import pyxel

import iso
from bubble import Bubble, BubblePhase
from camera import cam_target_deg, lead_point, update_camera
from controls import player_turn_input
from gamemaster import GameMaster
from iso import iter_screen_positions, movement_screen_dir
from snake import Snake
from sprites import (
    FRUIT_HOVER_LIFT,
    SHADOW_BIG,
    bob_y_offset,
    draw_tail,
    draw_bubble,
    draw_fruit,
    draw_fruit_quarter,
    draw_head,
    draw_shadow,
    hover_y,
    shadow_for_bob,
)
from world import SPAWN_CX, SPAWN_CY, fruit_drop_shadow

BG_COLOR = 3


class App:
    def __init__(self):
        pyxel.init(256, 200, title="Iso Snake", fps=60)
        pyxel.load("assets/snake.pyxres")
        from sprites import init_atlas

        init_atlas("assets/snake.manifest.json")
        iso.init_screen_center(pyxel.width, pyxel.height)

        self.last_time = time.perf_counter()
        self.anim_time = 0.0

        self.player = Snake(SPAWN_CX, SPAWN_CY, heading_deg=45.0)
        self.fruits: list = []
        self.bubbles: list = []
        self.gm = GameMaster(random)
        self.gm.start_game(self.player, self.fruits, self.bubbles)

        self.cam_x, self.cam_y = lead_point(self.player.head_x, self.player.head_y, self.player.heading_deg)
        self.cam_deg = cam_target_deg(self.player.heading_deg)
        self.cam_rot_vel = 0.0

        pyxel.run(self.update, self.draw)

    def update(self):
        now = time.perf_counter()
        dt = min(now - self.last_time, 0.05)
        self.last_time = now

        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        self.anim_time += dt

        turn = player_turn_input()
        claimed = set()
        if self.player.eating_fruit_index is not None:
            claimed.add(self.player.eating_fruit_index)

        removed = self.player.update(dt, self.fruits, self.cam_x, self.cam_y, self.cam_deg, turn, claimed)
        if removed is not None and 0 <= removed < len(self.fruits):
            self.fruits.pop(removed)
            self.gm.on_fruit_eaten(self.player, self.fruits, self.bubbles)

        for bubble in self.bubbles:
            bubble.try_hit(self.player.head_x, self.player.head_y, self.player.heading_deg, self.player.move_speed)
            bubble.update(dt, anim_t=self.anim_time)
            released = bubble.take_released_fruit()
            if released is not None:
                self.fruits.append(released)
        self.bubbles = [b for b in self.bubbles if b.is_active()]

        for fruit in self.fruits:
            fruit.update(dt)

        self.gm.update(dt, self.player, self.fruits, self.bubbles, self.anim_time)

        self.cam_x, self.cam_y, self.cam_deg, self.cam_rot_vel = update_camera(
            self.cam_x,
            self.cam_y,
            self.cam_deg,
            self.cam_rot_vel,
            self.player.head_x,
            self.player.head_y,
            self.player.heading_deg,
            dt,
        )

    def _draw_snake(
        self,
        snake: Snake,
        drawables: list,
        focus_x: float,
        focus_y: float,
        cam: float,
        sw: int,
        sh: int,
    ) -> None:
        for seg_i, (wx, wy) in enumerate(snake.segments):
            tail_idx = snake.segment_tail_index(seg_i)
            seg_index = seg_i + 1
            for sx, sy in iter_screen_positions(wx, wy, focus_x, focus_y, cam, screen_w=sw, screen_h=sh):
                bob = snake.wave_bob_offset(seg_index)
                if snake.segment_draws_shadow(seg_i):
                    drawables.append((sy, "shadow", (sx, sy, snake.segment_shadow(seg_i, bob)), None))
                drawables.append((sy, "tail", (sx, snake.hover_screen_y(sy, seg_index), tail_idx), None))

        dir_idx = movement_screen_dir(snake.heading_deg, cam)
        hox, hoy = snake.serpentine_world_offset(0)
        head_bob = snake.wave_bob_offset(0)
        for sx, sy in iter_screen_positions(
            snake.head_x + hox, snake.head_y + hoy, focus_x, focus_y, cam, screen_w=sw, screen_h=sh
        ):
            drawables.append((sy, "shadow", (sx, sy, shadow_for_bob(SHADOW_BIG, head_bob)), None))
            drawables.append((sy, "head", (sx, snake.hover_screen_y(sy, 0), dir_idx, snake.mouth_open()), None))

        eating = snake.eating_fruit_draw()
        if eating is not None:
            esx, esy, ekind, escale = eating
            drawables.append((esy, "fruit", (esx, esy, ekind, escale), None))

    def draw(self):
        pyxel.cls(BG_COLOR)

        focus_x = self.cam_x
        focus_y = self.cam_y
        cam = self.cam_deg
        sw, sh = pyxel.width, pyxel.height
        t = self.anim_time
        eating_idx = self.player.eating_fruit_index

        drawables: list[tuple[float, str, tuple, None]] = []

        for i, fruit in enumerate(self.fruits):
            if i == eating_idx:
                continue
            for sx, sy in iter_screen_positions(fruit.wx, fruit.wy, focus_x, focus_y, cam, screen_w=sw, screen_h=sh):
                fscale = fruit.visual_scale()
                if fruit.is_airborne_drop():
                    drop_z = fruit.drop_z()
                    fsy = sy - drop_z
                    shadow = fruit_drop_shadow(drop_z)
                else:
                    bob = bob_y_offset(t)
                    fsy = hover_y(sy, t, lift=FRUIT_HOVER_LIFT)
                    shadow = fruit.shadow_idx(bob)
                drawables.append((sy, "shadow", (sx, sy, shadow), None))
                drawables.append((fsy, "fruit", (sx, fsy, fruit.kind, fscale), None))

        for bubble in self.bubbles:
            if not bubble.is_active():
                continue
            bob = bob_y_offset(t) if bubble.phase == BubblePhase.IDLE else 0.0
            lift = bubble.screen_lift(t)
            y_off = bubble.draw_y_offset()
            shadow = bubble.shadow_idx(bob)
            sprite = bubble.sprite_idx()
            bscale = bubble.visual_scale()
            for sx, sy in iter_screen_positions(bubble.wx, bubble.wy, focus_x, focus_y, cam, screen_w=sw, screen_h=sh):
                if bubble.draws_shadow():
                    drawables.append((sy, "shadow", (sx, sy, shadow), None))
                if bubble.contains_fruit():
                    fsy = sy - lift + y_off
                    drawables.append(
                        (fsy, "fruit", (sx, fsy, bubble.fruit_kind, bubble.fruit_inside_scale()), None)
                    )
                drawables.append((sy, "bubble", (sx, sy - lift + y_off, sprite, bscale), None))

        self._draw_snake(self.player, drawables, focus_x, focus_y, cam, sw, sh)

        for crumb in self.player.eat_crumbs:
            jump_z = crumb.jump_z()
            for sx, sy in iter_screen_positions(crumb.wx, crumb.wy, focus_x, focus_y, cam, screen_w=sw, screen_h=sh):
                fsy = sy - jump_z
                drawables.append((sy + jump_z, "crumb", (sx, fsy, crumb.kind, crumb.quarter, crumb.scale), None))

        drawables.sort(key=lambda item: item[0])

        for _, kind, args, _ in drawables:
            if kind == "shadow":
                draw_shadow(args[0], args[1], args[2])
            elif kind == "bubble":
                scale = args[3] if len(args) > 3 else 1.0
                draw_bubble(args[0], args[1], args[2], scale)
            elif kind == "tail":
                draw_tail(args[0], args[1], args[2])
            elif kind == "head":
                draw_head(args[0], args[1], args[2], args[3])
            elif kind == "fruit":
                scale = args[3] if len(args) > 3 else 1.0
                draw_fruit(args[0], args[1], args[2], scale)
            elif kind == "crumb":
                scale = args[4] if len(args) > 4 else 1.0
                draw_fruit_quarter(args[0], args[1], args[2], args[3], scale)

        pyxel.text(4, 4, "arrows: turn  Q: quit", 7)


App()
