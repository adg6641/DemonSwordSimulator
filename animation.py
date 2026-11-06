"""동작 정보에 맞춰 스프라이트 시트의 한 칸을 그린다."""

import json
from bisect import bisect_right
from itertools import accumulate

from pico2d import load_image, SDL_SetTextureScaleMode, SDL_ScaleModeNearest, SDL_ScaleModeLinear


def load_pixel_image(path, *, smooth=False):
    image = load_image(str(path))
    # 확대할 때 이웃 픽셀의 색을 섞지 않아 지면과 스프라이트가 흐려지지 않는다.
    SDL_SetTextureScaleMode(image.texture, SDL_ScaleModeLinear if smooth else SDL_ScaleModeNearest)
    return image


class Animation:
    def __init__(self, folder):
        self.folder = folder
        data = json.loads((folder / 'animations.json').read_text(encoding='utf-8'))
        self.clips = {clip['id']: clip for clip in data['clips']}
        self.images = {}
        self.name = ''
        self.serial = 0
        self.play('idle_breathe')

    def add_story_clips(self, assets):
        for key, clip in assets.clips.items():
            if key.startswith('adv/hero_'):
                self.clips[key] = dict(clip, file=clip['path'])

    def play(self, name, *, fps=None, once=False):
        self.name = name
        self.serial += 1
        self.clip = self.clips[name]
        self.fps = fps or self.clip['fps']
        durations=self.clip.get('frameDurations') if fps is None else None
        self.frame_ends=list(accumulate(durations)) if durations else None
        self.loop = self.clip['playback'] == 'loop' and not once
        self.elapsed = 0.0

    @property
    def frame(self):
        count = self.clip['frameCount']
        if self.frame_ends:
            time=(self.elapsed%self.duration if self.loop else self.elapsed)*self.fps/self.clip['fps']
            return min(count-1,bisect_right(self.frame_ends,time))
        frame = int(self.elapsed * self.fps)
        return frame % count if self.loop else min(frame, count - 1)

    @property
    def duration(self):
        return self.frame_ends[-1]*self.clip['fps']/self.fps if self.frame_ends else self.clip['frameCount'] / self.fps

    @property
    def pose_time(self):
        """현재 자세 번호와 그 자세 안에서 흘러간 비율. 검기 판정도 같은 시계를 쓴다."""
        if not self.frame_ends:return self.elapsed*self.fps
        i=self.frame;start=self.frame_ends[i-1] if i else 0
        phase=max(0,min(1,(self.elapsed*self.fps/self.clip['fps']-start)/(self.frame_ends[i]-start)))
        return i+phase

    @property
    def finished(self):
        return not self.loop and self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    def draw(self, x, y, facing, camera, scale=1.0):
        path=str(self.folder/self.clip['file'])
        if path not in self.images:
            self.images[path] = load_pixel_image(path,smooth=True)
        frame = self.frame
        cell = self.clip['frames'][frame]
        width, height = cell['width'], cell['height']
        pivot = self.clip['pivot']
        # 큰 프레임만 같은 비율로 축소한다. 발 기준점과 팔다리 비율은 유지한다.
        scale *= cell.get('renderScale', 1.0)
        draw_width, draw_height = round(width * scale), round(height * scale)
        pivot_x = pivot['x'] if facing > 0 else width - pivot['x']
        left = round(x - camera.x - pivot_x * scale)
        bottom = round(y - camera.y - (height - pivot['y']) * scale)
        self.images[path].clip_composite_draw(
            cell['x'], cell['pico2dY'], width, height,
            0, 'h' if facing < 0 else '',
            left + draw_width / 2, bottom + draw_height / 2,
            draw_width, draw_height,
        )
