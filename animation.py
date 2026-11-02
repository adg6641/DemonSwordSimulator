"""동작 정보에 맞춰 스프라이트 시트의 한 칸을 그린다."""

import json

from pico2d import load_image


class Animation:
    def __init__(self, folder):
        self.folder = folder
        data = json.loads((folder / 'animations.json').read_text(encoding='utf-8'))
        self.clips = {clip['id']: clip for clip in data['clips']}
        self.images = {}
        self.name = ''
        self.play('idle_breathe')

    def play(self, name, *, fps=None, once=False):
        self.name = name
        self.clip = self.clips[name]
        self.fps = fps or self.clip['fps']
        self.loop = self.clip['playback'] == 'loop' and not once
        self.elapsed = 0.0

    @property
    def duration(self):
        return self.clip['frameCount'] / self.fps

    @property
    def finished(self):
        return not self.loop and self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    def draw(self, x, y, facing, camera, scale=1.0):
        if self.name not in self.images:
            self.images[self.name] = load_image(str(self.folder / self.clip['file']))
        count = self.clip['frameCount']
        frame = int(self.elapsed * self.fps)
        frame = frame % count if self.loop else min(frame, count - 1)
        cell = self.clip['frames'][frame]
        width, height = cell['width'], cell['height']
        pivot = self.clip['pivot']
        # 모든 동작에서 발 기준점을 같은 월드 좌표에 놓는다.
        center_x = x - camera.x + facing * (width / 2 - pivot['x']) * scale
        center_y = y - camera.y + (pivot['y'] - height / 2) * scale
        self.images[self.name].clip_composite_draw(
            cell['x'], cell['pico2dY'], width, height,
            0, 'h' if facing < 0 else '',
            center_x, center_y, width * scale, height * scale,
        )
