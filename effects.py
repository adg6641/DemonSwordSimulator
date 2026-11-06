"""검날을 따라가는 검기, 검은 재 오라와 독립적으로 날아가는 마검파."""

import json
from math import atan2, ceil, cos, hypot, sin

import pico2d.pico2d as engine
from pico2d import SDL_Rect, SDL_RenderSetClipRect, SDL_SetTextureColorMod

from animation import load_pixel_image


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
        self.images, self.radii = {}, {}
        self.level = 1
        self.time = self.buff_remaining = 0.0
        self.buff_duration = 5.0
        self.reach_scale = 1.0
        self.waves = []
        self.serial, self.fired = -1, False
        for name, frames in self.settings['effectGeometry'].items():
            self.radii[name] = max(4.0, *(hypot(x - f['origin'][0], y - f['origin'][1])
                for f in frames for x in (f['bounds'][0], f['bounds'][2])
                for y in (f['bounds'][1], f['bounds'][3])))

    def activate(self):
        self.buff_remaining = self.buff_duration

    def blade(self, animation):
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
        phase=animation.elapsed*animation.fps%1
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
        lifetime = self.settings['waveMotion']['lifetime']
        self.waves = [wave for wave in self.waves if wave['age'] < lifetime]
        animation = player.animation
        if animation.serial != self.serial:
            self.serial, self.fired = animation.serial, False
        motion = self.ATTACKS.get(animation.name)
        if not motion or motion == 'dash' or self.fired or self.buff_remaining <= 0:
            return
        timing = self.settings['strikeTiming'][motion]
        time = animation.elapsed * animation.fps * 8 / animation.clip['frameCount']
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
        image.clip_composite_draw(frame % clip['columns'] * w,
            image.h - (frame // clip['columns'] + 1) * h, w, h,
            -angle * facing, 'h' if facing < 0 else '',
            round(anchor[0] - camera.x + facing * center_x),
            round(anchor[1] - camera.y - center_y), round(w * scale), round(h * scale))
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
        pose = self.blade(animation)
        if not motion or not pose:
            return
        timing = self.settings['strikeTiming'][motion]
        time = animation.elapsed * animation.fps * 8 / animation.clip['frameCount']
        if not timing['start'] < time < timing['end']:
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
        reach = (pose['length'] + 4) * (1 + (self.level - 1) * .065)
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

    def wave_geometry(self, wave):
        style = self.settings['waveMotion']
        age, level = wave['age'], wave['level']
        name = f'wave_lv{level}'
        # 가운데의 안정된 12프레임을 반복하고 수명 끝에는 알파만 천천히 줄인다.
        count=self.clips[name]['frameCount']
        frame = 2+int(age*style['fps'])%max(1,count-4)
        bounds = self.settings['effectGeometry'][name][frame]['bounds']
        origin = (bounds[0]+(bounds[2]-bounds[0])*.12, (bounds[1]+bounds[3])/2)
        scale = (.32+.68*smooth(age/style['growDuration']))*self.settings['effectStyle']['scale']*wave.get('size', 1)
        return dict(name=name, frame=frame, bounds=bounds, origin=origin, scale=scale,
                    x=age*(240+level*20)*style['speedMultiplier'], y=0,
                    angle=wave['angle']*(1-smooth(age/style['straightenDuration'])),
                    alpha=clamp((style['lifetime']-age)/style['fadeDuration'])*self.settings['effectStyle']['opacity'])

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
            point = self.settings['chargePalm'][min(len(self.settings['chargePalm'])-1, animation.frame)]
            pivot = animation.clip['pivot']
            factor = animation.clip['frames'][animation.frame].get('renderScale', 1.0)
            x, y = (point[0] - pivot['x']) * factor, (point[1] - pivot['y']) * factor
        else:
            x, y = (pose['hand'][i] + (pose['tip'][i] - pose['hand'][i]) * .3 for i in (0, 1))
        name = f'charge_lv{self.level}'
        diameter = 28 + self.level * 3 if active else 42 + self.level * 6
        count=self.clips[name]['frameCount']
        frame = 5 + int(self.time * 12) % max(1,count-9) if active else min(count-1,int(animation.frame/animation.clip['frameCount']*count))
        style = self.settings['effectStyle']
        self._paint(name, frame, (player.x, player.y), camera, x, y,
            diameter / self.clips[name]['peakSize'] * style['scale'], facing=player.facing,
            opacity=(.18 if active else .85) * style['opacity'])

    def draw(self, player, camera):
        # 검기가 지면 속으로 파고들지 않도록 실제 바닥 아래만 가린다.
        zoom=getattr(camera,'zoom',1)
        bottom = round(camera.height + camera.y)
        SDL_RenderSetClipRect(engine.renderer, SDL_Rect(0, 0, round(camera.width/zoom), max(0, bottom)))
        pose = self.blade(player.animation)
        if pose and player.mode != 'dead':
            self._concentrate(player, camera, pose)
            self._draw_geometry(self.strike_geometry(player), (player.x, player.y), camera, player.facing)
        for wave in self.waves:
            self._draw_geometry(self.wave_geometry(wave), (wave['x'], wave['y']), camera, wave['facing'])
        SDL_RenderSetClipRect(engine.renderer, None)
