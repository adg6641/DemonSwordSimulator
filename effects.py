"""검날을 따라가는 검기, 검은 재 오라와 독립적으로 날아가는 마검파."""

import json
from math import atan2, ceil, cos, hypot, sin, pi

import pico2d.pico2d as engine
from pico2d import SDL_Rect, SDL_RenderSetClipRect, SDL_SetTextureColorMod

from animation import draw_region, load_pixel_image
from hit_geometry import effect_hits, blade_hits, sweep_ages


def clamp(value):
    return max(0.0, min(1.0, value))


def smooth(value):
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


class CombatEffects:
    ATTACKS = {'slash_1': 'slash_1', 'slash_2': 'slash_2', 'slash_3': 'slash_3',
               'dash_slash': 'dash', 'air_slash': 'slash_2', 'crouch_slash': 'slash_1'}

    def __init__(self, folder):
        self.folder = folder
        data = json.loads((folder / 'effects.json').read_text(encoding='utf8'))
        self.clips = {c['id']: c for c in data['clips']}
        self.settings = data['preview']
        self.hit_masks = {name:self.settings['hitMasks'][source] for name,source in self.settings['hitMaskSources'].items()}
        self.images, self.radii = {}, {}
        self.level = 1
        self.time = self.buff_remaining = 0.0
        self.buff_duration = 5.0
        self.reach_scale = 1.0
        self.waves = []
        self.bursts = []
        self.serial, self.fired = -1, False
        self.trail=None
        self.last_hit_state = None
        for name, frames in self.settings['effectGeometry'].items():
            self.radii[name] = max(4.0, *(hypot(x - f['origin'][0], y - f['origin'][1])
                for f in frames for x in (f['bounds'][0], f['bounds'][2])
                for y in (f['bounds'][1], f['bounds'][3])))
        self.wave_heights = {name: max(f['bounds'][3]-f['bounds'][1] for f in frames[2:-2])
                             for name, frames in self.settings['effectGeometry'].items() if name.startswith('wave_')}

    def activate(self):
        self.buff_remaining = self.buff_duration

    def burst(self, name, x, y, facing=1):
        clip = self.clips['hero_'+name]
        self.bursts.append((clip['id'], x, y, facing, 0.0))
        self.bursts = self.bursts[-16:]

    def timing(self, animation, motion):
        return self.settings.get('clipTiming',{}).get(animation.name,self.settings['strikeTiming'][motion])

    def blade(self, animation):
        rigid=getattr(animation,'weapon_pose',None)
        if rigid:
            return rigid
        track = self.settings['swordTracks'].get(animation.name)
        if not track:
            return None
        frame = animation.frame
        points = track[min(frame, len(track) - 1)]
        if points is None:
            return None
        scale = animation.clip['frames'][frame].get('renderScale', 1.0)
        pivot = animation.clip['pivot']
        # 원화 프레임 사이에서도 검기와 검의 오라는 같은 손잡이/검끝 경로를 따라간다.
        following=track[(frame+1)%len(track)] if animation.loop or frame+1<len(track) else points
        phase=animation.pose_time%1
        if following is None:following=points
        hand, tip = ((tuple(((point[i]*(1-phase)+nxt[i]*phase) - pivot[axis]) * scale
                      for i, axis in enumerate(('x', 'y'))))
                     for point,nxt in zip((points['hand'],points['tip']),(following['hand'],following['tip'])))
        return {'hand': hand, 'tip': tip, 'angle': atan2(tip[1] - hand[1], tip[0] - hand[0]),
                'length': hypot(tip[0] - hand[0], tip[1] - hand[1])}

    def update(self, dt, player):
        self.time += dt
        self.buff_remaining = max(0.0, self.buff_remaining - dt)
        for wave in self.waves:
            wave['age'] += dt
        self.bursts = [(name,x,y,facing,age+dt) for name,x,y,facing,age in self.bursts
                       if age+dt < self.clips[name]['frameCount']/self.clips[name]['fps']]
        lifetime = self.settings['waveMotion']['lifetime']
        self.waves = [wave for wave in self.waves if wave['age'] < lifetime]
        animation = player.animation
        if self.serial != animation.serial and animation.name == 'dash_ground':
            self.burst('dash_wake', player.x - player.facing * 8, player.y, player.facing)
        if self.serial != animation.serial and animation.name == 'magic_release':
            pose = self.blade(animation)
            if pose:
                self.burst('release',player.x+player.facing*pose['hand'][0],
                           player.y-pose['hand'][1],player.facing)
        if self.trail:
            self.trail['age']+=dt
            if self.trail['age']>.18:self.trail=None
        g=self.strike_geometry(player)
        if g:
            self.trail=dict(geometry=g,anchor=(player.x,player.y),facing=player.facing,age=0,
                            serial=animation.serial,name=animation.name)
        if animation.serial != self.serial:
            self.serial, self.fired = animation.serial, False
        motion = self.ATTACKS.get(animation.name)
        if not motion or motion == 'dash' or self.fired or self.buff_remaining <= 0:
            return
        timing = self.timing(animation,motion)
        time = animation.pose_time * 8 / animation.clip['frameCount']
        if time >= timing['fire']:
            pose = self.blade(animation)
            if pose:
                self.waves.append({'x': player.x + player.facing * pose['tip'][0],
                    'y': player.y - pose['tip'][1], 'angle': pose['angle'],
                    'facing': player.facing, 'level': self.level, 'age': 0.0})
            self.fired = True

    def _image(self, name):
        path=self.clips[name]['file']
        if path not in self.images:
            self.images[path] = load_pixel_image(self.folder / path,smooth=True)
        return self.images[path]

    def preload(self):
        # 레벨별 그림은 같은 파일을 공유한다. 첫 공격에서 PNG를 읽지 않는다.
        files = {clip['file']: name for name, clip in self.clips.items()}
        for name in files.values():
            self._image(name)

    def _paint(self, name, frame, anchor, camera, x=0, y=0, scale=1, angle=0,
               facing=1, opacity=1, origin=None):
        clip = self.clips[name]
        image = self._image(name)
        w, h = clip['frameWidth'], clip['frameHeight']
        origin = origin or (w / 2, h / 2)
        # 원점이 이미지 중앙이 아니어도 검끝을 기준으로 정확히 회전한다.
        dx, dy = (w / 2 - origin[0]) * scale, (h / 2 - origin[1]) * scale
        center_x = x + dx * cos(angle) - dy * sin(angle)
        center_y = y + dx * sin(angle) + dy * cos(angle)
        image.opacify(clamp(opacity))
        SDL_SetTextureColorMod(image.texture,*clip.get('tint',[255,255,255]))
        rect = (frame % clip['columns'] * w, frame // clip['columns'] * h, w, h)
        draw_region(image, rect, anchor[0] - camera.x + facing * center_x,
                    anchor[1] - camera.y - center_y, scale, facing, angle * facing)
        image.opacify(1.0)
        SDL_SetTextureColorMod(image.texture,255,255,255)

    def draw_aura(self, player, camera):
        pose = self.blade(player.animation)
        if not pose or player.mode == 'dead':
            return
        style = self.settings['swordAura']
        clip = self.clips[style['clip']]
        count = max(5, ceil(pose['length'] / style['spacing']))
        phase = int(self.time * clip['fps'])
        for i in range(count):
            u = .07 + .93 * i / (count - 1)
            x, y = (pose['hand'][axis] + (pose['tip'][axis] - pose['hand'][axis]) * u for axis in (0, 1))
            scale = style['spriteScale'] * (.94 + .06 * sin(i * 1.7))
            self._paint(clip['id'], (phase + i * 2) % clip['frameCount'], (player.x, player.y), camera,
                x, y, scale, facing=player.facing, opacity=style['opacity'],
                origin=(clip['emitter']['x'], clip['emitter']['y']))

    def strike_geometry(self, player):
        """그리기와 타격 판정이 함께 쓰는 현재 검기의 실제 위치·회전·크기."""
        animation = player.animation
        motion = self.ATTACKS.get(animation.name)
        if not motion:
            return
        timing = self.timing(animation,motion)
        time = animation.pose_time * 8 / animation.clip['frameCount']
        if not timing['start'] < time < timing['end']:
            return
        pose = self.blade(animation)
        if not pose:
            return
        name = f'{motion}_lv{self.level}'
        count=self.clips[name]['frameCount'];middle=(count-1)*.46
        progress = ((time - timing['start']) / (timing['peak'] - timing['start']) * middle
                    if time <= timing['peak'] else middle + (time - timing['peak']) / (timing['end'] - timing['peak']) * (count-middle-.01))
        frame = min(count-1, int(progress))
        geometry = self.settings['effectGeometry'][name][frame]
        origin = geometry['origin']
        lead = geometry['ccw' if timing['direction'] == 'ccw' else 'cw']
        style = self.settings['effectStyle']
        radius = (pose['length'] + 4) * (1 + (self.level - 1) * (.2 if motion == 'dash' else .16))
        scale = radius * style['scale'] / self.radii[name] * self.reach_scale
        reach = (pose['length'] + 4) * (1 + (self.level - 1) * .13) * self.reach_scale
        shift = reach - hypot(lead[0] - origin[0], lead[1] - origin[1]) * scale
        x = pose['hand'][0] + cos(pose['angle']) * shift
        y = pose['hand'][1] + sin(pose['angle']) * shift
        if motion == 'dash':
            x += self.settings['dashForwardOffset']
        angle = pose['angle'] - atan2(lead[1] - origin[1], lead[0] - origin[0])
        alpha = smooth((time - timing['start']) / .6) * smooth((timing['end'] - time) / 1.4)
        alpha *= (.64 + (self.level - 1) * .05) * style['opacity']
        return dict(name=name, frame=frame, x=x, y=y, scale=scale, angle=angle,
                    alpha=alpha, origin=origin, bounds=geometry['bounds'])

    @staticmethod
    def world_bounds(g, x, y, facing):
        points = []
        for px in (g['bounds'][0], g['bounds'][2]):
            for py in (g['bounds'][1], g['bounds'][3]):
                dx, dy = (px-g['origin'][0])*g['scale'], (py-g['origin'][1])*g['scale']
                rx = g['x']+dx*cos(g['angle'])-dy*sin(g['angle'])
                ry = g['y']+dx*sin(g['angle'])+dy*cos(g['angle'])
                points.append((x+facing*rx, y-ry))
        return min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)

    def strike_bounds(self, player):
        g = self.strike_geometry(player)
        return self.world_bounds(g, player.x, player.y, player.facing) if g else None

    def strike_state(self, player):
        """현재 보이는 검기와 잔상을 타격 판정에도 같은 위치로 전달한다."""
        current = self.strike_geometry(player)
        if current:
            state=dict(geometry=current,anchor=(player.x,player.y),facing=player.facing,
                       serial=player.animation.serial,name=player.animation.name,blade=self.blade(player.animation))
            self.trail=dict(state,age=0)
            return state
        if self.trail and player.mode not in {'hurt','dead'}:
            state=dict(self.trail);geometry=dict(state['geometry'])
            geometry['alpha'] *= 1-smooth(state['age']/.18)
            state.update(geometry=geometry,blade=None)
            return state if geometry['alpha'] >= .025 else None

    def melee_hits(self, state, target):
        if effect_hits(state['geometry'],state['anchor'],state['facing'],target,self.hit_masks):
            return True
        pose=state.get('blade')
        if not pose:
            return False
        previous=self.last_hit_state
        if (not previous or previous['serial'] != state['serial']
                or previous['facing'] != state['facing'] or not previous.get('blade')):
            previous = state
        old=previous['blade'];facing=state['facing']
        turn=(pose['angle']-old['angle']+pi)%(2*pi)-pi
        distance=hypot(state['anchor'][0]-previous['anchor'][0],state['anchor'][1]-previous['anchor'][1])+abs(turn)*pose['length']+hypot(pose['hand'][0]-old['hand'][0],pose['hand'][1]-old['hand'][1])
        for t in sweep_ages(0,1,distance):
            angle=old['angle']+turn*t
            anchor=tuple(a+(b-a)*t for a,b in zip(previous['anchor'],state['anchor']))
            hand=tuple(a+(b-a)*t for a,b in zip(old['hand'],pose['hand']))
            start=(anchor[0]+facing*hand[0],anchor[1]-hand[1])
            tip=(start[0]+facing*cos(angle)*pose['length'],start[1]-sin(angle)*pose['length'])
            if blade_hits(start,tip,target):return True
        return False

    def wave_geometry(self, wave):
        style = self.settings['waveMotion']
        age, level = wave['age'], wave['level']
        name = f'wave_lv{level}'
        # 마검파의 순환 시트를 반복하고 수명 끝에는 알파만 천천히 줄인다.
        count=self.clips[name]['frameCount']
        frame = int(age*style['fps'])%count
        bounds = self.settings['effectGeometry'][name][frame]['bounds']
        origin = (bounds[0]+(bounds[2]-bounds[0])*.12, (bounds[1]+bounds[3])/2)
        height = style['heightByLevel'][level-1]
        scale = height/self.wave_heights[name]*(.55+.45*smooth(age/style['growDuration']))*wave.get('size',1)
        return dict(name=name, frame=frame, bounds=bounds, origin=origin, scale=scale,
                    x=age*(240+level*20)*style['speedMultiplier'], y=0,
                    angle=wave['angle']*(1-smooth(age/style['straightenDuration'])),
                    alpha=clamp((style['lifetime']-age)/style['fadeDuration'])*self.settings['effectStyle']['opacity'])

    def wave_samples(self, wave, start_age):
        speed = (240+wave['level']*20)*self.settings['waveMotion']['speedMultiplier']
        return [self.wave_geometry(dict(wave, age=age))
                for age in sweep_ages(start_age, wave['age'], speed)]

    def wave_hits(self, wave, target, start_age=0, *, samples=None):
        if samples is None:
            samples = self.wave_samples(wave, start_age)
        anchor = wave['x'], wave['y']
        return any(effect_hits(geometry, anchor, wave['facing'], target, self.hit_masks)
                   for geometry in samples)

    def _draw_geometry(self, g, anchor, camera, facing):
        if g:
            self._paint(g['name'], g['frame'], anchor, camera, g['x'], g['y'], g['scale'],
                        g['angle'], facing, g['alpha'], g['origin'])

    def _concentrate(self, player, camera, pose):
        animation = player.animation
        active = animation.name != 'magic_charge'
        if active and self.buff_remaining <= 0:
            return
        if not active:
            cell = animation.clip['frames'][animation.frame]
            point = cell.get('chargePalm', self.settings['chargePalm'][animation.frame])
            pivot = animation.clip['pivot']
            factor = cell.get('renderScale', 1.0)
            x, y = (point[0] - pivot['x']) * factor, (point[1] - pivot['y']) * factor
        else:
            x, y = (pose['hand'][i] + (pose['tip'][i] - pose['hand'][i]) * .3 for i in (0, 1))
        name = f'charge_lv{self.level}'
        diameter = 28 + self.level * 3 if active else 42 + self.level * 6
        count=self.clips[name]['frameCount']
        frame = 5 + int(self.time * 12) % max(1,count-9) if active else min(count-1,int(animation.frame/animation.clip['frameCount']*count))
        style = self.settings['effectStyle']
        clip=self.clips[name]
        emitter=clip['emitter']
        self._paint(name, frame, (player.x, player.y), camera, x, y,
            diameter / clip['peakSize'] * style['scale'], facing=player.facing,
            opacity=(.18 if active else .85) * style['opacity'],origin=(emitter['x'],emitter['y']))

    def draw(self, player, camera):
        # 검기가 지면 속으로 파고들지 않도록 실제 바닥 아래만 가린다.
        zoom=getattr(camera,'zoom',1)
        bottom = round(camera.height + camera.y)
        SDL_RenderSetClipRect(engine.renderer, SDL_Rect(0, 0, round(camera.width/zoom), max(0, bottom)))
        pose = self.blade(player.animation)
        if pose and player.mode != 'dead':
            self._concentrate(player, camera, pose)
            state=self.strike_state(player)
            if state:self._draw_geometry(state['geometry'],state['anchor'],camera,state['facing'])
        for wave in self.waves:
            self._draw_geometry(self.wave_geometry(wave), (wave['x'], wave['y']), camera, wave['facing'])
        for name,x,y,facing,age in self.bursts:
            clip=self.clips[name]
            frame=min(clip['frameCount']-1,int(age*clip['fps']))
            origin=clip['emitter']
            fade=min(1,(clip['frameCount']-frame)/5)
            self._paint(name,frame,(x,y),camera,scale=clip['displayScale'],facing=facing,
                        opacity=.87*fade,origin=(origin['x'],origin['y']))
        SDL_RenderSetClipRect(engine.renderer, None)
