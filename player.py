"""키 입력, 주인공의 상태 전환과 지면 위 이동."""

from collections import deque
from math import pi, sin

from pico2d import (
    SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN,
    SDLK_LSHIFT, SDLK_RSHIFT, SDLK_c, SDLK_x, SDLK_z,
)

from animation import Animation
from effects import CombatEffects


SHIFT = {SDLK_LSHIFT, SDLK_RSHIFT}
LANDING = {'land_soft', 'land_hard', 'air_attack_land', 'land_run', 'land_walk'}
MOVING_LANDINGS = {'land_run', 'land_walk'}
CROUCH_GAITS = {'crouch_idle', 'crouch_walk'}
CROUCH_POSES = CROUCH_GAITS | {'crouch_down', 'crouch_slash', 'crouch_attack_recovery'}
GAIT_STRIDE = {'walk': 116, 'run': 188, 'crouch_walk': 89}
MOVE_TRANSITIONS = {
    ('idle_breathe', 'walk'): 'idle_to_walk',
    ('idle_breathe', 'run'): 'run_start',
    ('walk', 'idle_breathe'): 'walk_to_idle',
    ('walk', 'run'): 'walk_to_run',
    ('run', 'walk'): 'run_to_walk',
    ('run', 'idle_breathe'): 'run_stop',
}


class Player:
    WALK_SPEED = 170.0
    RUN_SPEED = 330.0
    CROUCH_SPEED = 85.0
    AIR_SPEED = 285.0
    DASH_DISTANCE = 166.0
    DASH_DURATION = .32
    DASH_PHASES = {'dash_start': (0,.065), 'dash_ground': (.065,.255), 'dash_end': (.255,.32),
                   'dash_air': (0,.32)}
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
        self.dash_elapsed = 0.0
        self.land_distance = 0.0
        self.jump_launched = False
        self.horizontal_speed = self.brake_speed = 0.0
        self.attack_pending = False
        self.step_serial, self.step_progress = -1, 0.0

    @property
    def grounded(self):
        return self.y <= self.floor_y + .01 and self.vy <= 0.0

    @property
    def landing(self):
        return self.grounded and self.mode == 'action' and self.animation.name in LANDING

    @property
    def collision_height(self):
        if self.animation.name in CROUCH_POSES or self.animation.name == 'crouch_up':
            return self.animation.clip['frames'][self.animation.frame].get('bodyHeight',126)
        return self.BODY_HEIGHT

    def _action(self, clip, *followups, start_frame=None):
        self.attack_pending=False
        self.brake_speed=0.0
        self.mode = 'action'
        self.gait = None
        self.combo_queued = False
        self.followups = deque(followups)
        self.animation.play(clip,start_frame=start_frame)

    def land(self, direction):
        if self.animation.name=='air_slash':
            self._action('air_attack_land')
        elif direction and not self.crouching:
            self.land_distance = 0.0
            self._action('land_run' if self.move_time >= .55 else 'land_walk')
        else:
            self._action('land_soft')

    def take_damage(self, amount):
        if self.mode == 'dead' or self.invulnerable > 0:
            return 0
        damage_was_guarded = self.mode == 'guard'
        damage = max(1, round(amount * .25)) if damage_was_guarded else max(0, round(amount))
        self.hp = max(0, self.hp - damage)
        self.invulnerable = .65
        self.effects.buff_remaining = 0.0
        self.dash_attack_remaining = 0.0
        self.followups.clear()
        self.attack_pending=False
        self.mode, self.gait = ('dead' if self.hp == 0 else 'hurt'), None
        clip = 'death' if self.hp == 0 else 'guard_impact' if damage_was_guarded else 'hurt'
        self.animation.play(clip)
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
        if (self.mode == 'free' or self.landing) and direction:
            self.facing = direction
        if key == SDLK_c:
            if (self.dash_unlocked and self.dash_attack_remaining > 0 and SDLK_DOWN not in keys
                    and (self.mode in {'free', 'dash'} or self.landing)):
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
            elif self.mode == 'free' or self.landing:
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
            if self.grounded and (self.mode == 'free' or self.landing):
                self.dash_attack_remaining = 0.0
                self.mode, self.gait = 'jump', None
                self.jump_launched = False
                moving = direction and abs(self.horizontal_speed) > 80
                self.animation.play('running_takeoff' if moving else 'jump_takeoff', start_frame=0)
        elif key in SHIFT and (self.mode == 'free' or self.landing or self.mode == 'jump' and not self.grounded):
            if self.grounded or self.air_dash_ready:
                self.dash_attack_remaining = 0.0
                self.dash_elapsed = 0.0
                self.mode, self.gait = 'dash', None
                if self.grounded:
                    self.play_dash('dash_start')
                else:
                    self.air_dash_ready = False
                    self.vy = 0.0
                    self.play_dash('dash_air')

        elif key == SDLK_z and self.magic_unlocked and self.grounded and (self.mode == 'free' or self.landing):
            self.dash_attack_remaining = 0.0
            self.mode, self.gait = 'magic', None
            self.animation.play('magic_charge')

    def play_dash(self, name):
        start,end=self.DASH_PHASES[name]
        self.animation.play(name, fps=self.animation.clips[name]['frameCount']/(end-start),
                            once=True,start_frame=0)
        self.animation.elapsed=max(0,self.dash_elapsed-start)

    def dash_step(self, dt):
        """지상과 공중 대시가 같은 시간과 가속 곡선을 쓴다."""
        if self.mode != 'dash' or self.animation.name not in self.DASH_PHASES:
            return 0.0
        start=self.dash_elapsed/self.DASH_DURATION
        self.dash_elapsed=min(self.DASH_DURATION,self.dash_elapsed+dt)
        end=self.dash_elapsed/self.DASH_DURATION
        return self.facing*self.DASH_DISTANCE*(end*end*(3-2*end)-start*start*(3-2*start))

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
            if not self.jump_launched and anim.elapsed >= anim.duration * .44:
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
        elif self.mode == 'dash':
            if anim.name in self.DASH_PHASES and self.dash_elapsed >= self.DASH_DURATION:
                self.dash_attack_remaining = self.DASH_ATTACK_GRACE
                if anim.name=='dash_air':
                    anim.play('air_dash_recovery')
                else:
                    self.mode = 'free'
                    direction = int(SDLK_RIGHT in keys) - int(SDLK_LEFT in keys)
                    if direction == self.facing and SDLK_DOWN not in keys:
                        self.gait = 'run' if self.move_time >= .55 else 'walk'
                        anim.play('dash_run_out' if self.gait == 'run' else 'dash_walk_out')
                    else:
                        self.gait = 'idle_breathe'
                        anim.play('dash_stop_out')
            elif anim.name in {'dash_start','dash_ground','dash_end'}:
                name = next(name for name in ('dash_start','dash_ground','dash_end')
                            if self.dash_elapsed < self.DASH_PHASES[name][1])
                if anim.name!=name:
                    self.play_dash(name)
            elif anim.finished:
                self.mode = 'free'
        elif self.mode == 'magic':
            if anim.finished:
                # 집중을 마치면 5초 동안 기본 베기마다 마검파를 발사한다.
                self.effects.activate()
                self._action('magic_release','magic_recovery')
        elif self.mode == 'hurt' and anim.finished:
            if self.forced_crouch:
                self.mode = 'free'
            elif anim.name == 'guard_impact':
                self.mode = 'guard'
                anim.play('guard_idle' if SDLK_x in keys else 'guard_lower')
            else:
                self._action('hurt_recovery')
        elif self.mode == 'guard':
            if SDLK_x not in keys and anim.name != 'guard_lower':
                if anim.name == 'guard_raise':
                    release = anim.clips['guard_lower']['frameCount']-1
                    release_frame = round(release*(1-anim.progress))
                else:
                    release_frame = 0
                anim.play('guard_lower', start_frame=release_frame)
            elif anim.finished:
                if anim.name in {'guard_raise', 'guard_impact'}:
                    anim.play('guard_idle')
                elif anim.name == 'guard_lower':
                    self.mode = 'free'

        if self.mode == 'free' and self.grounded and SDLK_x in keys and not self.forced_crouch:
            self.dash_attack_remaining = 0.0
            self.mode, self.gait = 'guard', None
            anim.play('guard_raise')

    def _locomotion(self, direction, keys):
        if not self.grounded:
            target = 'jump_rise' if self.vy > 160 else 'jump_apex' if self.vy > -160 else 'fall'
        elif SDLK_DOWN in keys:
            target = 'crouch_walk' if direction else 'crouch_idle'
        elif direction:
            target = 'run' if self.move_time >= 0.55 else 'walk'
        else:
            target = 'idle_breathe'

        anim = self.animation
        if self.grounded:
            wants_crouch = target in CROUCH_GAITS
            if anim.name in {'crouch_down', 'crouch_up'} and not anim.finished:
                lowering = anim.name == 'crouch_down'
                if wants_crouch != lowering:
                    fraction = anim.clip_time / anim.duration
                    name = 'crouch_down' if wants_crouch else 'crouch_up'
                    count = anim.clips[name]['frameCount']
                    anim.play(name, start_frame=round((1 - fraction) * (count - 1)))
                self.gait = target
                return
            was_crouching = anim.name in CROUCH_POSES
            if wants_crouch != was_crouching:
                self.gait = target
                anim.play('crouch_down' if wants_crouch else 'crouch_up')
                return

        if target != self.gait:
            prior = self.gait or 'idle_breathe'
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
        time = animation.pose_time * 8 / animation.clip['frameCount']
        start, end = ((1.55, 5.45), (1.35, 5.35), (1.80, 6.05))[self.combo_step-1]
        chain = animation.clip.get('chainFrame', animation.clip['frameCount'])
        end = min(end, chain * 8 / animation.clip['frameCount'])
        phase = max(0, min(1, (time-start) / (end-start)))
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
        dashing = self.mode == 'dash'
        dash_advance = self.dash_step(dt)
        keys=keys|{SDLK_DOWN} if self.forced_crouch else keys
        self.crouching=(SDLK_DOWN in keys and self.grounded and (self.mode=='free' or self.landing)) or self.animation.name in CROUCH_POSES
        self.drop_timer=max(0,self.drop_timer-dt)
        # Shift를 누르는 동안 대시 후 C 연결을 유지하고, 놓아도 잠깐의 여유를 준다.
        if not keys & SHIFT:
            self.dash_attack_remaining = max(0.0, self.dash_attack_remaining - dt)
        self.invulnerable = max(0.0, self.invulnerable - dt)
        # 지상 보행은 시간 대신 실제 이동 거리로 한 번만 진행한다.
        if self.animation.name not in MOVING_LANDINGS and (self.mode != 'free' or self.animation.name not in GAIT_STRIDE):
            self.animation.update(dt)
        combo_advance=self._combo_advance(keys)
        direction = int(SDLK_RIGHT in keys) - int(SDLK_LEFT in keys)
        if direction and direction == self.previous_direction:
            self.move_time += dt
        else:
            self.move_time = 0.0
        self.previous_direction = direction
        if self.landing and self.animation.name in MOVING_LANDINGS and (not direction or self.crouching):
            self._action('land_soft',start_frame=3)
        elif (self.landing and direction and not self.crouching and self.animation.name not in MOVING_LANDINGS
              and (self.animation.name!='air_attack_land' or self.animation.progress>=.24)):
            self.land(direction)
        if self.landing and self.animation.name in MOVING_LANDINGS and self.animation.finished:
            self.gait = 'run' if self.animation.name == 'land_run' else 'walk'
            self.mode = 'free'
            self.animation.play(self.gait)
        self._update_action(keys)

        speed = 0.0
        if self.mode in {'free', 'jump'} and not dashing:
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
                if self.grounded:
                    name = self.animation.name
                    phase = self.animation.progress
                    easing = phase*phase*(3-2*phase)
                    if not direction and name in {'run_stop','walk_to_idle'}:
                        speed=self.brake_speed*(1-phase)**2
                    elif name == 'idle_to_walk':
                        speed *= .62+.38*easing
                    elif name in {'walk_to_run','run_start'}:
                        speed=direction*(self.WALK_SPEED+(self.RUN_SPEED-self.WALK_SPEED)*easing)
                    elif name in {'dash_run_out','dash_walk_out'}:
                        speed *= .70 + .30*easing
        elif self.mode == 'action':
            if self.attack_pending:
                speed=self.brake_speed*(1-self.animation.progress)**2
            elif self.animation.name == 'dash_slash':
                phase=self.animation.pose_time/self.animation.clip['frameCount']
                speed = self.facing * self.DASH_ATTACK_SPEED * sin(pi*(phase-.16)/.52)**.86 if .16<phase<.68 else 0
            elif self.landing:
                if direction:
                    self.facing = direction
                speed = direction * (self.CROUCH_SPEED if SDLK_DOWN in keys else
                                     self.RUN_SPEED if self.move_time >= .55 else self.WALK_SPEED)
            elif not self.grounded:
                speed = direction * self.AIR_SPEED
        self.x += speed * dt + combo_advance + dash_advance
        self.horizontal_speed=dash_advance/dt if dashing and dt else speed
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
                self.land(direction)

        self.effects.update(dt, self)

    def advance_gait(self, distance):
        if self.animation.name in MOVING_LANDINGS:
            # A wall can stop the player's position even while a direction is held.
            if abs(distance)<.01:
                self.mode = 'free'
                self.gait = 'idle_breathe'
                self.animation.play('idle_breathe')
                return
            self.land_distance += abs(distance)
            stride = 61 if self.animation.name == 'land_run' else 39
            self.animation.elapsed = self.animation.duration*min(1,self.land_distance/stride)
            return
        stride = GAIT_STRIDE.get(self.animation.name)
        if stride and self.mode == 'free':
            self.animation.update(abs(distance) / stride * self.animation.duration)

    def draw(self, camera):
        self.animation.draw(self.x, self.y, self.facing, camera)
        self.effects.draw_aura(self, camera)
        self.effects.draw(self, camera)
