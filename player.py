"""키 입력, 주인공의 상태 전환과 지면 위 이동."""

from collections import deque

from pico2d import (
    SDLK_LEFT, SDLK_RIGHT, SDLK_SPACE, SDLK_LCTRL, SDLK_RCTRL,
    SDLK_LSHIFT, SDLK_RSHIFT, SDLK_c, SDLK_x, SDLK_z,
)

from animation import Animation


CTRL = {SDLK_LCTRL, SDLK_RCTRL}
SHIFT = {SDLK_LSHIFT, SDLK_RSHIFT}
MOVE_TRANSITIONS = {
    ('idle_breathe', 'walk'): 'idle_to_walk',
    ('walk', 'idle_breathe'): 'walk_to_idle',
    ('walk', 'run'): 'walk_to_run',
    ('run', 'walk'): 'run_to_walk',
    ('run', 'idle_breathe'): 'run_stop',
    ('idle_breathe', 'crouch_idle'): 'crouch_down',
    ('walk', 'crouch_walk'): 'crouch_down',
    ('run', 'crouch_walk'): 'crouch_down',
    ('crouch_idle', 'idle_breathe'): 'crouch_up',
    ('crouch_walk', 'walk'): 'crouch_up',
    ('crouch_walk', 'run'): 'crouch_up',
}


class Player:
    WALK_SPEED = 170.0
    RUN_SPEED = 330.0
    CROUCH_SPEED = 85.0
    AIR_SPEED = 285.0
    DASH_SPEED = 850.0
    JUMP_SPEED = 850.0
    GRAVITY = 2200.0

    def __init__(self, sprite_folder):
        self.animation = Animation(sprite_folder)
        self.x, self.y, self.vy = 220.0, 0.0, 0.0
        self.facing = 1
        self.mode = 'free'
        self.followups = deque()
        self.gait = 'idle_breathe'
        self.move_time = 0.0
        self.previous_direction = 0
        self.combo_step = 0
        self.combo_queued = False
        self.air_dash_ready = True
        self.jump_launched = False

    @property
    def grounded(self):
        return self.y <= 0.0 and self.vy <= 0.0

    def _action(self, clip, *followups):
        self.mode = 'action'
        self.gait = None
        self.combo_queued = False
        self.followups = deque(followups)
        self.animation.play(clip)

    def press(self, key, keys):
        direction = int(SDLK_RIGHT in keys) - int(SDLK_LEFT in keys)
        if self.mode == 'free' and direction:
            self.facing = direction
        if key == SDLK_c:
            if self.mode == 'combo':
                self.combo_queued = self.combo_step < 3
            elif self.mode == 'dash':
                self._action('dash_slash', 'dash_attack_recovery')
            elif self.mode == 'free':
                if not self.grounded:
                    self._action('air_slash')
                elif keys & CTRL:
                    self._action('crouch_slash', 'crouch_attack_recovery')
                else:
                    self.mode, self.gait = 'combo', None
                    self.combo_step, self.combo_queued = 1, False
                    self.animation.play('slash_1')
        elif key == SDLK_SPACE:
            landing = self.animation.name in {'land_soft', 'land_hard', 'air_attack_land'}
            if self.grounded and (self.mode == 'free' or landing):
                self.mode, self.gait = 'jump', None
                self.jump_launched = False
                self.animation.play('jump_takeoff', fps=64)
        elif key in SHIFT and self.mode == 'free':
            if self.grounded or self.air_dash_ready:
                self.mode, self.gait = 'dash', None
                if self.grounded:
                    self.animation.play('dash_start', fps=64)
                else:
                    self.air_dash_ready = False
                    self.vy = 0.0
                    self.animation.play('dash_air', fps=40, once=True)
        elif key == SDLK_z and self.mode == 'free' and self.grounded:
            self.mode, self.gait = 'magic', None
            self.animation.play('magic_charge')

    def _finish_combo(self):
        name = self.animation.name
        if name.startswith('combo_'):
            self.combo_step += 1
            self.animation.play(f'slash_{self.combo_step}')
        elif self.combo_queued and self.combo_step < 3:
            self.combo_queued = False
            self.animation.play(f'combo_{self.combo_step}_to_{self.combo_step + 1}')
        else:
            recovery = {1: 'attack_recovery', 2: 'slash_2_recovery', 3: 'slash_3_recovery'}
            self._action(recovery[self.combo_step])

    def _update_action(self, keys):
        anim = self.animation
        if self.mode == 'jump':
            # 짧은 준비 자세를 보여 준 다음 발을 지면에서 떼어 낸다.
            if not self.jump_launched and anim.elapsed >= 2 / 64:
                self.vy = self.JUMP_SPEED
                self.jump_launched = True
            if anim.finished:
                self.mode = 'free'
        elif self.mode == 'combo' and anim.finished:
            self._finish_combo()
        elif self.mode == 'action' and anim.finished:
            if self.followups:
                anim.play(self.followups.popleft())
            else:
                self.mode = 'free'
        elif self.mode == 'dash' and anim.finished:
            if anim.name == 'dash_start':
                anim.play('dash_ground', fps=40, once=True)
            elif anim.name == 'dash_ground':
                anim.play('dash_end', fps=64)
            elif anim.name == 'dash_air':
                anim.play('air_dash_recovery')
            else:
                self.mode = 'free'
        elif self.mode == 'magic':
            if anim.finished and SDLK_z not in keys:
                self._action('magic_release', 'magic_recovery')
        elif self.mode == 'guard':
            if SDLK_x not in keys and anim.name != 'guard_lower':
                anim.play('guard_lower')
            elif anim.finished:
                if anim.name == 'guard_raise':
                    anim.play('guard_idle')
                elif anim.name == 'guard_lower':
                    self.mode = 'free'

        if self.mode == 'free' and self.grounded and SDLK_x in keys:
            self.mode, self.gait = 'guard', None
            anim.play('guard_raise')

    def _locomotion(self, direction, keys):
        if not self.grounded:
            target = 'jump_rise' if self.vy > 100 else 'jump_apex' if self.vy > -100 else 'fall'
        elif keys & CTRL:
            target = 'crouch_walk' if direction else 'crouch_idle'
        elif direction:
            target = 'run' if self.move_time >= 0.55 else 'walk'
        else:
            target = 'idle_breathe'

        if target != self.gait:
            transition = MOVE_TRANSITIONS.get((self.gait, target))
            self.gait = target
            self.animation.play(transition or target)
        elif self.animation.name != target and self.animation.finished:
            self.animation.play(target)

    def update(self, dt, keys):
        self.animation.update(dt)
        direction = int(SDLK_RIGHT in keys) - int(SDLK_LEFT in keys)
        if direction and direction == self.previous_direction:
            self.move_time += dt
        else:
            self.move_time = 0.0
        self.previous_direction = direction
        self._update_action(keys)

        speed = 0.0
        if self.mode in {'free', 'jump'}:
            if direction:
                self.facing = direction
            if not self.grounded:
                speed = direction * self.AIR_SPEED
            elif keys & CTRL:
                speed = direction * self.CROUCH_SPEED
            else:
                speed = direction * (self.RUN_SPEED if self.move_time >= 0.55 else self.WALK_SPEED)
            if self.mode == 'free':
                self._locomotion(direction, keys)
        elif self.mode == 'dash':
            name = self.animation.name
            dash_speed = self.DASH_SPEED if name in {'dash_ground', 'dash_air'} else 120.0
            speed = self.facing * dash_speed
        elif self.mode == 'action':
            if self.animation.name == 'dash_slash':
                speed = self.facing * 420.0
            elif self.y > 0:
                speed = direction * self.AIR_SPEED
        self.x += speed * dt

        airborne = not self.grounded
        floating_dash = self.mode == 'dash' and self.animation.name == 'dash_air'
        if airborne and not floating_dash:
            self.y += self.vy * dt - self.GRAVITY * dt * dt / 2
            self.vy -= self.GRAVITY * dt
        if self.y <= 0:
            self.y, self.vy = 0.0, 0.0
            self.air_dash_ready = True
            if airborne:
                landing = 'air_attack_land' if self.animation.name == 'air_slash' else 'land_soft'
                self._action(landing)

    def draw(self, camera):
        self.animation.draw(self.x, self.y, self.facing, camera)
