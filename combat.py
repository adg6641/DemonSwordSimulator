"""적의 예고→공격→빈틈, 독립 투사체, 뒤따르는 루네아."""
from dataclasses import dataclass, field
from math import sin, hypot
from game_assets import Motion
from navigation import waypoint
from player import Player


@dataclass
class Shot:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    key: str
    friendly: bool = False
    life: float = 3.0
    radius: float = 20
    age: float = 0
    pierce: int = 1
    hit: set = field(default_factory=set)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt

    @property
    def dead(self):
        return self.age >= self.life


class Enemy:
    def __init__(self, assets, number, x, stage, uid, rng):
        self.assets, self.number, self.uid = assets, number, uid
        self.actor = assets.actors[f'enemy_{number:02d}']
        self.boss = self.actor['boss']
        self.x, self.home = x, x
        self.y = 75.0 if not self.actor['grounded'] else 0.0
        self.perch = None
        self.facing = -1
        self.scale = (1.12 if number >= 16 else .78 if number >= 13 else .73)
        self.max_hp = (1000 if number == 20 else 230 + stage*55 if self.boss else 33 + stage*12 + (35 if number >= 13 else 0))
        self.hp = self.max_hp
        self.damage = 8 + stage*2 + (5 if self.boss else 0)
        self.speed = 56 + stage*7 + rng.uniform(-8, 8)
        self.motion = Motion(assets, self.key('idle'))
        self.state, self.age, self.cooldown = 'idle', 0.0, rng.uniform(.4, 1.4)
        self.attack_index = 0
        self.did_hit = False
        self.defeated = False
        self.rewarded = False
        self.slow = 0.0
        self.marked = 0.0
        self.target_x = x
        self.pattern = 'melee'
        self.attack_key = self.key('attack_a')

    def key(self, state):
        return f'enemy/enemy_{self.number:02d}_{state}'

    def keep_on_perch(self):
        if self.perch:
            left,right,_=self.perch
            self.x=max(left,min(right,self.x))

    @property
    def alive(self):
        return self.hp > 0

    def hurtbox(self):
        clip = self.assets.clips[self.key('idle')]
        box = self.assets.bodies.get(f'enemy_{self.number:02d}', (90, 50, 294, 320))
        pivot, s = clip['pivot'], self.scale
        x0, y0, x1, y1 = box
        if self.facing != (-1 if clip.get('facing')=='left' else 1):
            x0, x1 = 2*pivot['x']-x1, 2*pivot['x']-x0
        return (self.x+(x0-pivot['x'])*s, self.y+(pivot['y']-y1)*s,
                self.x+(x1-pivot['x'])*s, self.y+(pivot['y']-y0)*s)

    def change(self, state, clip=None):
        self.state, self.age = state, 0.0
        if clip:
            self.motion.play(clip, restart=True)

    def hurt(self, damage, direction, scene):
        if not self.alive:
            return False
        self.hp = max(0, self.hp - damage)
        if self.hp == 0:
            self.change('dead', self.key('defeat'))
            self.defeated = True
        elif not self.boss:
            self.x = max(90, min(scene.world.width-90, self.x + direction*9))
            self.keep_on_perch()
            self.change('hurt', self.key('hurt'))
        scene.feedback(self.x, self.y+85, round(damage), 'hit_impacts__hit_metal' if self.number in {2, 8, 9, 11, 14, 17, 18, 20} else 'hit_impacts__hit_soft')
        return True

    def patterns(self):
        if self.number == 20:
            return ['charge', 'slam', 'night']
        if self.number == 16:
            return ['melee', 'root', 'charge']
        if self.number == 17:
            return ['seal', 'paper', 'slam']
        if self.number == 18:
            return ['charge', 'melee', 'needle']
        if self.number == 19:
            return ['slam', 'night', 'charge']
        return {2: ['charge', 'melee'], 3: ['spore', 'melee'], 4: ['needle', 'melee'],
                5: ['root', 'charge'], 7: ['melee', 'slam'], 9: ['melee', 'slam'],
                10: ['paper', 'seal'], 12: ['charge', 'slam'], 13: ['melee', 'charge', 'melee'],
                14: ['slam', 'charge', 'melee'], 15: ['needle', 'seal', 'melee']}.get(self.number, ['melee', 'charge'])

    def start_attack(self, scene):
        patterns = self.patterns()
        index = self.attack_index % len(patterns)
        self.pattern = patterns[index]
        self.attack_index += 1
        suffix = chr(ord('a') + min(index, 2))
        self.attack_key = self.key('attack_'+suffix)
        if self.attack_key not in self.assets.clips:
            self.attack_key = self.key('attack_a')
        if self.number == 20 and self.pattern == 'charge':
            self.attack_key = 'adv/king_charge__king_charge'
        self.target_x = scene.player.x
        self.facing = 1 if self.target_x > self.x else -1
        self.did_hit = False
        self.change('windup', self.attack_key)

    def update(self, dt, scene):
        self.motion.update(dt)
        self.age += dt
        self.cooldown = max(0, self.cooldown-dt)
        self.slow = max(0, self.slow-dt)
        self.marked = max(0, self.marked-dt)
        if self.state == 'dead':
            return
        if self.state == 'hurt':
            if self.age > (.9 if self.boss else .3):
                self.change('idle', self.key('idle'))
                self.cooldown = .35
            return
        p = scene.player
        distance = abs(p.x-self.x)
        if not self.actor['grounded']:
            self.y = (self.perch[2] if self.perch else 0) + 75 + sin(scene.time*2+self.home)*12
        if self.state == 'windup':
            self.motion.age = 0
            delay = (.75 if self.boss else .5) + (.25 if self.marked > 0 else 0)
            if self.age >= delay:
                self.change('attack', self.attack_key)
            return
        if self.state == 'attack':
            length = self.assets.duration(self.attack_key)
            fraction = self.motion.age / length
            if self.pattern == 'charge' and .25 < fraction < .76:
                self.x += self.facing * (520 if self.boss else 340) * dt * (.6 if self.slow else 1)
                self.x = max(100, min(scene.world.width-100, self.x))
                self.keep_on_perch()
                if abs(p.x-self.x) < (110 if self.boss else 65) and abs(p.y-self.y) < 125:
                    scene.damage_player(self.damage*1.15, self.x)
            if not self.did_hit and fraction >= .45:
                self.did_hit = True
                self.strike(scene)
            if self.motion.finished:
                self.change('recover', self.key('idle'))
                self.cooldown = 1.0 if self.boss else .85
            return
        if self.state == 'recover':
            if self.age >= (.65 if self.boss else .4):
                self.change('idle', self.key('idle'))
            return
        if p.hp <= 0 or distance > (600 if self.boss else 640) or abs(p.y-self.y)>170:
            self.motion.play(self.key('idle'))
            return
        if self.number == 20 and scene.run.hidden_entry is None:
            scene.run.hidden_entry = scene.run.all_magic()
        self.facing = 1 if p.x > self.x else -1
        ranged = self.patterns()[self.attack_index % len(self.patterns())] in {'spore', 'paper', 'needle', 'night', 'seal', 'root', 'charge'}
        reach = 480 if ranged else (170 if self.boss else 100)
        if distance <= reach and self.cooldown <= 0:
            self.start_attack(scene)
        elif distance > reach*.78:
            self.motion.play(self.key('move'))
            self.x += self.facing*self.speed*dt*(.55 if self.slow else 1)
            self.keep_on_perch()
        else:
            self.motion.play(self.key('idle'))

    def strike(self, scene):
        p = scene.player
        if self.pattern in {'spore', 'paper', 'needle', 'night'}:
            kinds = {'spore': 'spore_fly', 'paper': 'paper_fly', 'needle': 'needle_fly', 'night': 'night_orb'}
            dx, dy = p.x-self.x, p.y+65-(self.y+85)
            length = max(1, hypot(dx, dy))
            speed = 280 if self.pattern == 'spore' else 370 if self.boss else 330
            for spread in ([-.2, 0, .2] if self.boss and self.hp < self.max_hp*.5 else [0]):
                scene.shots.append(Shot(self.x+self.facing*55, self.y+85, dx/length*speed, dy/length*speed+spread*180, self.damage, 'adv/projectiles__'+kinds[self.pattern], radius=24 if self.boss else 16))
        elif self.pattern in {'seal', 'root'}:
            scene.hazards.append(dict(x=self.target_x, y=p.floor_y, age=0, wait=.75, life=1.6, hit=False, kind=self.pattern, damage=self.damage, radius=95))
        elif self.pattern == 'slam':
            scene.burst('adv/hit_impacts__hit_metal', self.x+self.facing*105, self.y+30, .75)
            if abs(p.x-(self.x+self.facing*90)) < (190 if self.boss else 100) and abs(p.y-self.y)<90:
                scene.damage_player(self.damage*1.3, self.x)
        elif self.pattern == 'melee':
            if abs(p.x-(self.x+self.facing*55)) < (150 if self.boss else 85) and abs(p.y-self.y) < 140:
                scene.damage_player(self.damage, self.x)

    def draw(self, scene):
        if self.state == 'dead' and self.age > 1.2:
            return
        alpha = max(0, 1-(self.age-.6)/.6) if self.state == 'dead' else 1
        self.motion.draw(self.x, self.y, scene.camera, self.scale, self.facing, alpha)
        if self.state == 'windup':
            scene.assets.draw('adv/seal_warning__seal_telegraph', self.x, self.y, scene.camera, .38 if not self.boss else .65, self.age)


class Companion:
    SCALE = .56
    BODY_HEIGHT = 165
    JUMP_SPEED = Player.JUMP_SPEED
    GRAVITY = Player.GRAVITY
    def __init__(self, assets, x):
        self.assets = assets
        self.x, self.y, self.vy = x, 0.0, 0.0
        self.floor_y = 0.0
        self.facing = 1
        self.motion = Motion(assets, 'lunea/idle_breathe')
        self.cooldown = 2.0
        self.skill = 0.0
        self.crouched = False
        self.gait_phase = 0.0
        self.ground_speed = 0.0
        self.running = False
        self.nav_target = None

    @property
    def grounded(self):
        return self.y <= self.floor_y+.5 and self.vy <= 0

    def update(self, dt, scene, cinematic=False):
        self.motion.update(dt)
        self.cooldown = max(0, self.cooldown-dt)
        p = scene.player
        target = p.x-p.facing*105
        # 주인공이 밟은 발판 안으로 목표점을 잡아 가장자리 밖에서 허공을 밟지 않는다.
        for o in scene.solid_platforms():
            if abs(p.y-o['y']) < 2:
                left, right = scene.platform_span(o)
                if left <= p.x <= right:
                    target = max(left+18, min(right-18, target))
        target = max(80, min(scene.world.width-80, target))
        target_y=p.floor_y
        if not self.grounded and self.nav_target:
            target,target_y=self.nav_target
        elif target_y>self.y+25:
            target,target_y=waypoint(scene,self,target,target_y)
            self.nav_target=(target,target_y)
        else:
            self.nav_target=None
        if abs(self.x-p.x) > 1050:
            self.x, self.y, self.vy = target, p.floor_y, 0
            self.ground_speed = 0.0
        self.floor_y = scene.floor_beneath(self)
        dx = target-self.x
        from pico2d import SDLK_DOWN
        crouch = (SDLK_DOWN in scene.keys or scene.under_root(self.x,self.y)
                  or scene.near_crawl(self.x,self.y,padding=44) is not None
                  and scene.under_root(p.x,p.y))
        speed = min(410, max(0, (abs(dx)-10)*3.1)) if not crouch else min(80, max(0, (abs(dx)-10)*3.1))
        if target_y>self.floor_y+18 and not crouch:
            speed = max(330, speed)
        old_x, old_y = self.x, self.y
        was_grounded = self.grounded and self.vy == 0
        launched = False
        # 발판과 낮은 엄폐물에 앞서 점프. 주인공과 같은 중력·착지 판정을 쓴다.
        direction = 1 if dx > 0 else -1
        obstacle = any(o['kind'] == 'cover' and abs(o['x']-self.x)<140 and (o['x']-self.x)*direction>0 for o in scene.objects)
        following_jump=self.nav_target is None and p.y>self.y+75 and p.floor_y<=self.floor_y+165
        if self.grounded and not crouch and abs(dx)<300 and (target_y>self.y+18 or following_jump or obstacle):
            self.vy = self.JUMP_SPEED
            launched = True
            self.motion.play('lunea/jump_takeoff')
            if not cinematic:
                p.effects.burst('lunea_takeoff', self.x, self.y, direction)
        if self.skill > 0:
            self.ground_speed = 0.0
        else:
            desired = direction*speed
            change = max(-1900*dt, min(1900*dt, desired-self.ground_speed))
            self.ground_speed += change
            self.x += max(-abs(dx), min(abs(dx), self.ground_speed*dt))
        if self.vy or self.y>self.floor_y:
            self.y += self.vy*dt-self.GRAVITY*dt*dt/2
            self.vy -= self.GRAVITY*dt
        scene.platforms(old_y, self)
        scene.blockers(old_x, self, crouch)
        if self.y <= self.floor_y and self.vy <= 0:
            self.y, self.vy = self.floor_y, 0
            if not was_grounded and not launched:
                if self.motion.key != 'lunea/land_soft':
                    self.motion.play('lunea/land_soft')
                if not cinematic:
                    p.effects.burst('lunea_land', self.x, self.y, direction)
        moved = abs(self.x-old_x)
        moving = moved > 23*dt
        if moving:
            self.facing = 1 if self.x > old_x else -1
        if not self.grounded:
            # 이륙 첫 자세를 짧게 보여 준 뒤 공중 모션으로 잇는다.
            if self.motion.key != 'lunea/jump_takeoff' or self.motion.age > .1:
                self.motion.play('lunea/jump_air')
            return
        if self.skill > 0:
            self.skill = max(0, self.skill-dt)
            name = 'skill_charge' if self.skill > .65 else 'skill_release' if self.skill > .2 else 'skill_recover'
            self.motion.play('lunea/'+name)
            return
        if self.motion.key in {'adv/lunea_camp__lunea_stand_up', 'adv/lunea_rescue__lunea_freed'} and not self.motion.finished:
            return
        if self.motion.key in {'lunea/land_soft', 'lunea/move_start', 'lunea/crouch_down', 'lunea/crouch_up'} and not self.motion.finished:
            return
        if self.motion.key == 'lunea/move_stop' and not moving and not self.motion.finished:
            return
        if crouch != self.crouched:
            self.crouched = crouch
            self.gait_phase = 0.0
            self.motion.play('lunea/crouch_down' if crouch else 'lunea/crouch_up')
        elif crouch:
            if moving:
                self.walk_cycle('adv/lunea_crouch_walk__lunea_crouch_walk', moved, 118)
            else:
                self.motion.play('lunea/crouch_idle')
        elif moving:
            if self.motion.key == 'lunea/idle_breathe':
                self.gait_phase = 0.0
                self.motion.play('lunea/move_start')
            else:
                self.running = moved/dt > (208 if self.running else 245)
                phase = self.gait_phase
                stride = 245 if self.running else 145
                self.walk_cycle('lunea/run' if self.running else 'lunea/walk', moved, stride)
                if not cinematic and self.running and int(phase * 2) != int((phase + moved / stride) * 2):
                    foot = 9 if self.gait_phase < .5 else -8
                    p.effects.burst('lunea_step', self.x + self.facing * foot, self.y, self.facing)
        elif self.motion.key in {'lunea/run', 'lunea/walk'}:
            stop = self.assets.clips['lunea/move_stop']
            previous = self.assets.frame(self.motion.key, self.motion.age)
            start = stop['entryFrames'][self.motion.key][previous]
            self.motion.play('lunea/move_stop', phase=start/stop['frameCount'])
        else:
            self.motion.play('lunea/idle_breathe')
        enemy = next((e for e in scene.enemies if e.alive and abs(e.x-p.x)<500 and e.state=='windup'), None)
        if enemy and self.cooldown <= 0 and not cinematic:
            self.support(scene, enemy)

    def walk_cycle(self, key, distance, stride):
        # 걷기↔달리기에서 이전에 디딘 발의 순서를 이어 받는다.
        self.gait_phase = (self.gait_phase + distance/stride) % 1
        self.motion.play(key)
        self.motion.age = self.gait_phase*self.assets.duration(key)

    def support(self, scene, enemy=None):
        if self.cooldown > 0:
            scene.notify(f'달빛 지원 준비 중 · {self.cooldown:.0f}초')
            return False
        self.cooldown, self.skill = 12, 1.15
        if enemy:
            enemy.marked, enemy.slow = 4.0, 2.0
            scene.burst('lunea/fx_seal', enemy.x, 0, .6)
            scene.burst('lunea/fx_projectile', (enemy.x+self.x)/2, 95, .45)
        else:
            scene.shield = 3.0
            scene.burst('lunea/fx_barrier', scene.player.x, 0, .65)
        return True

    def draw(self, scene):
        self.motion.draw(self.x, self.y, scene.camera, self.SCALE, self.facing)
