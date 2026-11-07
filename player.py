"""키 입력, 주인공의 상태 전환과 지면 위 이동."""

from collections import deque
from math import sin, pi

from pico2d import (
    SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN,
    SDLK_LSHIFT, SDLK_RSHIFT, SDLK_c, SDLK_x, SDLK_z,
)

from animation import Animation
from effects import CombatEffects


SHIFT = {SDLK_LSHIFT, SDLK_RSHIFT}
MOVE_TRANSITIONS = {
    ('idle_breathe', 'walk'): 'idle_to_walk',
    ('idle_breathe', 'run'): 'run_start',
    ('idle_breathe', 'crouch_walk'): 'crouch_down',
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
    ('crouch_walk', 'idle_breathe'): 'crouch_up',
    ('crouch_idle', 'walk'): 'crouch_up',
    ('crouch_idle', 'run'): 'crouch_up',
}


class Player:
    WALK_SPEED = 170.0
    RUN_SPEED = 330.0
    CROUCH_SPEED = 85.0
    AIR_SPEED = 285.0
    DASH_SPEED = 730.0
    DASH_ATTACK_SPEED = 760.0
    BODY_HEIGHT = 180
    DASH_ATTACK_GRACE = 0.4
    # C의 1·2·3번째 베기에서 각각 앞으로 나아갈 거리.
    COMBO_STEP = (46.0, 54.0, 64.0)
    JUMP_SPEED = 850.0
    GRAVITY = 2200.0

    def __init__(self, sprite_folder):
        self.animation = Animation(sprite_folder)
        self.effects = CombatEffects(sprite_folder.parent / 'effects')
        self.hp = 100
        self.floor_y = 0.0
        self.drop_timer = 0.0
        self.forced_crouch=False
        self.crouching=False
        self.dash_unlocked = self.magic_unlocked = True
        self.invulnerable = 0.0
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
        self.dash_attack_remaining = 0.0
        self.jump_launched = False
        self.horizontal_speed = self.brake_speed = 0.0
        self.attack_pending = False
        self.step_serial, self.step_progress = -1, 0.0

    @property
    def grounded(self):
        return self.y <= self.floor_y + .01 and self.vy <= 0.0

    @property
    def collision_height(self):
        if self.animation.name in {'crouch_down','crouch_up','crouch_idle','crouch_walk','crouch_slash','crouch_attack_recovery'}:
            return self.animation.clip['frames'][self.animation.frame].get('bodyHeight',126)
        return self.BODY_HEIGHT

    def _action(self, clip, *followups):
        self.attack_pending=False
        self.brake_speed=0.0
        self.mode = 'action'
        self.gait = None
        self.combo_queued = False
        self.followups = deque(followups)
        self.animation.play(clip)

    def take_damage(self, amount):
        if self.mode == 'dead' or self.invulnerable > 0:
            return 0
        damage = max(1, round(amount * .25)) if self.mode == 'guard' else max(0, round(amount))
        self.hp = max(0, self.hp - damage)
        self.invulnerable = .65
        self.effects.buff_remaining = 0.0
        self.dash_attack_remaining = 0.0
        self.followups.clear()
        self.attack_pending=False
        self.mode, self.gait = ('dead' if self.hp == 0 else 'hurt'), None
        self.animation.play('death' if self.hp == 0 else 'hurt')
        if self.hp>0 and self.forced_crouch:
            self.animation.play('crouch_idle',fps=self.animation.clips['crouch_idle']['frameCount']/.28,once=True)
        return damage

    def press(self, key, keys):
        keys=keys|{SDLK_DOWN} if self.forced_crouch else keys
        if self.mode in {'hurt', 'dead'}:
            return
        if self.forced_crouch and (key in SHIFT or key in {SDLK_UP,SDLK_z}):
            return
        direction = int(SDLK_RIGHT in keys) - int(SDLK_LEFT in keys)
        if self.mode == 'free' and direction:
            self.facing = direction
        if key == SDLK_c:
            landing = self.mode == 'action' and self.animation.name in {
                'land_soft', 'land_hard', 'air_attack_land',
            }
            if self.dash_unlocked and self.dash_attack_remaining > 0 and (self.mode in {'free', 'dash'} or landing):
                entry=self.animation.clips['dash_slash'].get('dashEntryFrame',0) if self.mode=='dash' else 0
                self.dash_attack_remaining = 0.0
                self._action('dash_slash','dash_attack_recovery')
                if entry:self.animation.play('dash_slash',start_frame=entry)
            elif self.mode == 'combo':
                self.combo_queued = self.combo_step < 3
            elif self.attack_pending:
                self.combo_queued=True
            elif self.mode == 'dash':
                # 대시 이동 중에는 C를 무시하며 나중에 자동 발동하도록 저장하지 않는다.
                return
            elif self.mode == 'free':
                if not self.grounded:
                    self._action('air_slash')
                elif SDLK_DOWN in keys:
                    if self.animation.name=='crouch_down' and not self.animation.finished:
                        self.mode,self.gait='action',None
                        self.followups=deque(['crouch_slash','crouch_attack_recovery'])
                    elif self.animation.name in {'crouch_idle','crouch_walk','crouch_attack_recovery'}:
                        self._action('crouch_slash','crouch_attack_recovery')
                    else:
                        self._action('crouch_down','crouch_slash','crouch_attack_recovery')
                else:
                    moving=self.animation.name in {'run','walk','walk_to_run','idle_to_walk'}
                    if moving:
                        name='run_stop' if abs(self.horizontal_speed)>220 else 'walk_to_idle'
                        entries=self.animation.clips[name].get('entryFrames',{}).get(self.animation.name,[])
                        entry=entries[min(self.animation.frame,len(entries)-1)] if entries else 0
                        speed=self.horizontal_speed;self._action(name)
                        self.animation.play(name,fps=self.animation.clip['frameCount']/.12,start_frame=entry)
                        self.brake_speed=speed;self.attack_pending=True
                    else:
                        self.mode, self.gait = 'combo', None
                        self.combo_step, self.combo_queued = 1, False
                        self.animation.play('slash_1')
        elif key == SDLK_UP:
            if self.forced_crouch:return
            if self.grounded and self.floor_y>0 and SDLK_DOWN in keys:
                self.drop_timer=.28;self.floor_y=0;self.y-=5;self.vy=-90
                self.mode,self.gait='free',None
                return
            landing = self.animation.name in {'land_soft', 'land_hard', 'air_attack_land'}
            if self.grounded and (self.mode == 'free' or landing):
                self.dash_attack_remaining = 0.0
                self.mode, self.gait = 'jump', None
                self.jump_launched = False
                self.animation.play('jump_takeoff', fps=self.animation.clips['jump_takeoff']['frameCount']/.125)
        elif key in SHIFT and (self.mode == 'free' or self.mode == 'jump' and not self.grounded):
            if self.grounded or self.air_dash_ready:
                self.dash_attack_remaining = 0.0
                self.mode, self.gait = 'dash', None
                if self.grounded:
                    self.animation.play('dash_start', fps=self.animation.clips['dash_start']['frameCount']/.125)
                else:
                    self.air_dash_ready = False
                    self.vy = 0.0
                    self.animation.play('dash_air', fps=self.animation.clips['dash_air']['frameCount']/.3, once=True)
        elif key == SDLK_z and self.magic_unlocked and self.mode == 'free' and self.grounded:
            self.dash_attack_remaining = 0.0
            self.mode, self.gait = 'magic', None
            self.animation.play('magic_charge')

    def _finish_combo(self):
        name = self.animation.name
        if name.startswith('combo_'):
            self.combo_step += 1
            name=f'slash_{self.combo_step}'
            self.animation.play(name,start_frame=self.animation.clips[name].get('comboStartFrame',0))
        elif self.combo_queued and self.combo_step < 3:
            self.combo_queued = False
            self.animation.play(f'combo_{self.combo_step}_to_{self.combo_step+1}')
        elif self.combo_step==3:
            self._action('slash_3_recovery')
        else:
            self._action('attack_recovery' if self.combo_step==1 else 'slash_2_recovery')

    def _update_action(self, keys):
        anim = self.animation
        if self.mode == 'jump':
            # 짧은 준비 자세를 보여 준 다음 발을 지면에서 떼어 낸다.
            if not self.jump_launched and anim.elapsed >= 2 / 64:
                self.vy = self.JUMP_SPEED
                self.jump_launched = True
            if anim.finished:
                self.mode = 'free'
        elif self.mode == 'combo' and (anim.finished or self.combo_queued and anim.frame>=anim.clip.get('chainFrame',anim.clip['frameCount'])):
            self._finish_combo()
        elif self.mode == 'action' and anim.finished:
            if self.attack_pending:
                self.attack_pending=False;self.mode='combo';self.combo_step=1
                anim.play('slash_1',start_frame=anim.clips['slash_1'].get('movementEntryFrame',0))
            elif self.followups:
                anim.play(self.followups.popleft())
            else:
                self.mode = 'free'
        elif self.mode == 'dash' and anim.finished:
            if anim.name == 'dash_start':
                anim.play('dash_ground', fps=anim.clips['dash_ground']['frameCount']/.3, once=True)
            elif anim.name == 'dash_ground':
                self.dash_attack_remaining = self.DASH_ATTACK_GRACE
                anim.play('dash_end', fps=anim.clips['dash_end']['frameCount']/(8/48))
            elif anim.name == 'dash_air':
                self.dash_attack_remaining = self.DASH_ATTACK_GRACE
                anim.play('air_dash_recovery')
            else:
                self.mode = 'free'
        elif self.mode == 'magic':
            if anim.finished:
                # 집중을 마치면 5초 동안 기본 베기마다 마검파를 발사한다.
                self.effects.activate()
                self._action('magic_release','magic_recovery')
        elif self.mode == 'hurt' and anim.finished:
            if self.forced_crouch:
                self.mode = 'free'
            else:
                self._action('hurt_recovery')
        elif self.mode == 'guard':
            if SDLK_x not in keys and anim.name != 'guard_lower':
                anim.play('guard_lower')
            elif anim.finished:
                if anim.name == 'guard_raise':
                    anim.play('guard_idle')
                elif anim.name == 'guard_lower':
                    self.mode = 'free'

        if self.mode == 'free' and self.grounded and SDLK_x in keys and not self.forced_crouch:
            self.dash_attack_remaining = 0.0
            self.mode, self.gait = 'guard', None
            anim.play('guard_raise')

    def _locomotion(self, direction, keys):
        if not self.grounded:
            target = 'jump_rise' if self.vy > 100 else 'jump_apex' if self.vy > -100 else 'fall'
        elif SDLK_DOWN in keys:
            target = 'crouch_walk' if direction else 'crouch_idle'
        elif direction:
            target = 'run' if self.move_time >= 0.55 else 'walk'
        else:
            target = 'idle_breathe'

        if target != self.gait:
            prior=self.gait
            if prior is None and self.grounded:
                prior='crouch_idle' if self.animation.name in {'crouch_idle','crouch_walk','crouch_slash','crouch_attack_recovery'} else 'idle_breathe'
            transition = MOVE_TRANSITIONS.get((prior, target))
            self.gait = target
            name=transition or target
            entry=None
            if name in {'run_stop','walk_to_idle'}:
                entries=self.animation.clips[name].get('entryFrames',{}).get(self.animation.name,[])
                if entries:entry=entries[min(self.animation.frame,len(entries)-1)]
                self.brake_speed=self.horizontal_speed
            self.animation.play(name,start_frame=entry)
        elif self.animation.name != target and self.animation.finished:
            self.animation.play(target)

    def _combo_advance(self, keys):
        """한 번 베는 동안 정해진 거리만 전진한다. 준비·회수 때는 밀리지 않는다."""
        animation = self.animation
        if self.mode != 'combo' or animation.name not in {'slash_1', 'slash_2', 'slash_3'}:
            return 0.0
        if animation.serial != self.step_serial:
            self.step_serial, self.step_progress = animation.serial, 0.0
        timing = self.effects.timing(animation, self.effects.ATTACKS[animation.name])
        time = animation.pose_time * 8 / animation.clip['frameCount']
        phase = max(0, min(1, (time-timing['start']) / (timing['end']-timing['start'])))
        previous, self.step_progress = self.step_progress, phase
        direction = int(SDLK_RIGHT in keys) - int(SDLK_LEFT in keys)
        if direction and previous == 0:
            self.facing = direction
        if not self.grounded or SDLK_DOWN in keys:
            return 0.0
        # 출발과 도착은 천천히, 베는 중간 구간은 빠르게 전진한다.
        moved = phase*phase*(3-2*phase) - previous*previous*(3-2*previous)
        return self.facing * self.COMBO_STEP[self.combo_step-1] * max(0, moved)

    def update(self, dt, keys):
        keys=keys|{SDLK_DOWN} if self.forced_crouch else keys
        self.crouching=(SDLK_DOWN in keys and self.grounded and self.mode=='free') or self.animation.name in {
            'crouch_idle','crouch_walk','crouch_down','crouch_slash','crouch_attack_recovery'}
        self.drop_timer=max(0,self.drop_timer-dt)
        # Shift를 누르는 동안 대시 후 C 연결을 유지하고, 놓아도 잠깐의 여유를 준다.
        if not keys & SHIFT:
            self.dash_attack_remaining = max(0.0, self.dash_attack_remaining - dt)
        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.animation.update(dt)
        combo_advance=self._combo_advance(keys)
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
            elif SDLK_DOWN in keys:
                speed = direction * self.CROUCH_SPEED
            else:
                speed = direction * (self.RUN_SPEED if self.move_time >= 0.55 else self.WALK_SPEED)
            if self.mode == 'free':
                self._locomotion(direction, keys)
                if not direction and self.grounded and self.animation.name in {'run_stop','walk_to_idle'}:
                    speed=self.brake_speed*(1-self.animation.progress)**2
        elif self.mode == 'dash':
            name = self.animation.name
            dash_speed = self.DASH_SPEED if name in {'dash_ground', 'dash_air'} else 120.0
            speed = self.facing * dash_speed
        elif self.mode == 'action':
            if self.attack_pending:
                speed=self.brake_speed*(1-self.animation.progress)**2
            elif self.animation.name == 'dash_slash':
                phase=self.animation.pose_time/self.animation.clip['frameCount']
                speed = self.facing * self.DASH_ATTACK_SPEED * sin(pi*(phase-.18)/.42)**.7 if .18<phase<.60 else 0
            elif not self.grounded:
                speed = direction * self.AIR_SPEED
        self.x += speed * dt + combo_advance
        self.horizontal_speed=speed
        if self.mode=='free' and self.animation.name in {'walk','run','crouch_walk'} and speed:
            stride={'walk':160,'run':255,'crouch_walk':110}[self.animation.name]
            self.animation.elapsed+=abs(speed*dt)/stride*self.animation.duration-dt

        airborne = not self.grounded
        floating_dash = self.mode == 'dash' and self.animation.name == 'dash_air'
        if airborne and not floating_dash:
            self.y += self.vy * dt - self.GRAVITY * dt * dt / 2
            self.vy -= self.GRAVITY * dt
        if self.y <= self.floor_y:
            self.y, self.vy = self.floor_y, 0.0
            self.air_dash_ready = True
            keep_dash_attack = self.mode == 'action' and self.animation.name in {
                'dash_slash', 'dash_attack_recovery',
            }
            if airborne and not keep_dash_attack and self.mode not in {'hurt', 'dead'}:
                landing = 'air_attack_land' if self.animation.name == 'air_slash' else 'land_soft'
                self._action(landing)

        self.effects.update(dt, self)

    def draw(self, camera):
        self.animation.draw(self.x, self.y, self.facing, camera)
        self.effects.draw_aura(self, camera)
        self.effects.draw(self, camera)
