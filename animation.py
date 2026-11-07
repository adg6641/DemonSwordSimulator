"""동작 정보에 맞춰 스프라이트 시트의 한 칸을 그린다."""

import json
from bisect import bisect_right
from itertools import accumulate
from math import cos, sin, pi, degrees

import pico2d.pico2d as engine
from pico2d import (SDL_Rect, SDL_FRect, SDL_RenderCopyExF,
                    SDL_FLIP_HORIZONTAL, SDL_FLIP_NONE)

from pico2d import load_image, SDL_SetTextureScaleMode, SDL_ScaleModeNearest, SDL_ScaleModeLinear


def load_pixel_image(path, *, smooth=False):
    image = load_image(str(path))
    # 확대할 때 이웃 픽셀의 색을 섞지 않아 지면과 스프라이트가 흐려지지 않는다.
    SDL_SetTextureScaleMode(image.texture, SDL_ScaleModeLinear if smooth else SDL_ScaleModeNearest)
    return image


def draw_region(image, rect, x, y, scale, facing, angle=0, stretch_y=1):
    """몸과 검이 같은 실수 좌표를 쓴다. 부위별 반올림으로 벌어지지 않는다."""
    left, top, width, height = rect
    width_on_screen, height_on_screen = width * scale, height * scale * stretch_y
    source = SDL_Rect(left, top, width, height)
    dest = SDL_FRect(x-width_on_screen/2, engine.canvas_height-y-height_on_screen/2,
                     width_on_screen, height_on_screen)
    flip = SDL_FLIP_HORIZONTAL if facing < 0 else SDL_FLIP_NONE
    SDL_RenderCopyExF(engine.renderer, image.texture, source, dest, degrees(angle), None, flip)


class SpriteAtlas:
    def __init__(self, manifest):
        data = json.loads(manifest.read_text(encoding='utf8'))
        self.paths = [manifest.parent / page for page in data['pages']]
        self.clips = data['clips']
        self.density = data.get('density', 1)
        self.images = {}

    def preload(self):
        for index in range(len(self.paths)):
            self.image(index)

    def image(self, index):
        if index not in self.images:
            self.images[index] = load_pixel_image(self.paths[index], smooth=True)
        return self.images[index]

    def draw(self, region, x, y, scale, facing, alpha=1, stretch_y=1):
        if region:
            page, left, top, width, height, dx, dy = region
            image = self.image(page)
            scale /= self.density
            if alpha != 1:
                image.opacify(alpha)
            draw_region(image, (left, top, width, height),
                        x+facing*dx*scale, y-dy*scale*stretch_y, scale, facing,
                        stretch_y=stretch_y)
            if alpha != 1:
                image.opacify(1)


class Animation:
    def __init__(self, folder):
        self.folder = folder
        data = json.loads((folder / 'animations.json').read_text(encoding='utf-8'))
        self.clips = {clip['id']: clip for clip in data['clips']}
        self.weapon = data.get('weapon')
        self.atlas = SpriteAtlas(folder / 'runtime.json')
        self.sword_image = None
        self.name = ''
        self.serial = 0
        self.play('idle_breathe')

    def preload(self):
        self.atlas.preload()
        self._sword_image()

    def _sword_image(self):
        if self.sword_image is None:
            self.sword_image = load_pixel_image(self.folder/self.weapon['file'], smooth=True)
        return self.sword_image

    def add_story_clips(self, assets):
        for key, clip in assets.clips.items():
            if key.startswith('adv/hero_'):
                self.clips[key] = dict(clip, file=clip['path'])

    def play(self, name, *, fps=None, once=False, start_frame=None):
        previous_name = self.name
        previous_frame = self.frame if self.name and self.name != 'idle_breathe' else 0
        self.name = name
        self.serial += 1
        self.clip = self.clips[name]
        self.fps = fps or self.clip['fps']
        durations=self.clip.get('frameDurations') if fps is None else None
        self.frame_ends=list(accumulate(durations)) if durations else None
        self.loop = self.clip['playback'] == 'loop' and not once
        if start_frame is None:
            entries=self.clip.get('entryFrames',{}).get(previous_name,[])
            start_frame=entries[min(previous_frame,len(entries)-1)] if entries else 0
        start_frame=max(0,min(self.clip['frameCount']-1,start_frame))
        self.elapsed = self.frame_start(start_frame)
        self.started_at=self.elapsed

    @property
    def progress(self):
        return max(0,min(1,(self.elapsed-self.started_at)/max(.001,self.duration-self.started_at)))

    def frame_start(self, frame):
        if self.frame_ends and frame:
            return self.frame_ends[frame-1]*self.clip['fps']/self.fps
        return frame/self.fps

    @property
    def clip_time(self):
        elapsed = max(0.0, self.elapsed)
        return elapsed % self.duration if self.loop else min(elapsed, self.duration)

    @property
    def frame(self):
        time = self.clip_time
        if self.frame_ends:
            frame = bisect_right(self.frame_ends, time*self.fps/self.clip['fps'] + 1e-9)
        else:
            frame = int(time*self.fps + 1e-9)
        return min(self.clip['frameCount']-1, frame)

    @property
    def duration(self):
        return self.frame_ends[-1]*self.clip['fps']/self.fps if self.frame_ends else self.clip['frameCount'] / self.fps

    @property
    def pose_time(self):
        """현재 자세 번호와 그 자세 안에서 흘러간 비율. 검기 판정도 같은 시계를 쓴다."""
        if not self.frame_ends:
            return self.clip_time*self.fps
        i = self.frame
        start = self.frame_ends[i-1] if i else 0
        elapsed = self.clip_time*self.fps/self.clip['fps']
        phase = max(0, min(1, (elapsed-start)/(self.frame_ends[i]-start)))
        return i+phase

    @property
    def finished(self):
        return not self.loop and self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    @property
    def breath(self):
        # 한 원화에서 바닥을 축으로 아주 얕게 숨을 쉰다. 발과 얼굴의 윤곽은 교체되지 않는다.
        return (1-cos(self.elapsed*pi))*.5 if self.name == 'idle_breathe' else 0.0

    @property
    def weapon_pose(self):
        """손은 현재 그림에 고정하고, 검은 길이를 바꾸지 않은 채 회전한다."""
        if not self.weapon:
            return None
        frames=self.clip['frames']
        neutral = self.name == 'idle_breathe'
        cell=frames[0 if neutral else self.frame];point=cell.get('weapon')
        if not point or point.get('hidden'):
            return None
        following=frames[(self.frame+1)%len(frames)] if not neutral and (self.loop or self.frame+1<len(frames)) else cell
        angle=point['angle'];next_angle=following.get('weapon',point)['angle']
        turn=(next_angle-angle+pi)%(2*pi)-pi
        angle+=turn*(self.pose_time%1)
        angle-=self.breath*.022
        factor=cell.get('renderScale',1);pivot=self.clip['pivot']
        dx, dy = cell.get('registration', (0, 0))
        hand = ((point['hand'][0]+dx-pivot['x'])*factor,
                (point['hand'][1]+dy-pivot['y'])*factor*(1+.007*self.breath))
        length=self.weapon['handToTip']
        tip=(hand[0]+cos(angle)*length,hand[1]+sin(angle)*length)
        return dict(hand=hand,tip=tip,angle=angle,length=length)

    def draw(self, x, y, facing, camera, scale=1.0):
        frame = 0 if self.name == 'idle_breathe' else self.frame
        cell = self.clip['frames'][frame]
        body, hand = self.atlas.clips[self.name][frame]
        x, y = x-camera.x, y-camera.y
        stretch = 1+.007*self.breath
        self.atlas.draw(body, x, y, cell.get('renderScale', 1)*scale, facing, stretch_y=stretch)
        pose = self.weapon_pose
        if pose:
            image = self._sword_image()
            grip = self.weapon['grip']
            blade_scale = self.weapon['scale']*scale
            dx, dy = (image.w/2-grip['x'])*blade_scale, (image.h/2-grip['y'])*blade_scale
            angle = pose['angle']
            cx = pose['hand'][0]*scale + dx*cos(angle) - dy*sin(angle)
            cy = pose['hand'][1]*scale + dx*sin(angle) + dy*cos(angle)
            draw_region(image, (0, 0, image.w, image.h), x+facing*cx, y-cy,
                        blade_scale, facing, angle*facing)
            self.atlas.draw(hand, x, y, cell.get('renderScale', 1)*scale, facing, stretch_y=stretch)
