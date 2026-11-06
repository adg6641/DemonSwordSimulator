"""준비된 8개 배경과 지면, 주인공을 따라가는 카메라."""

import json
from math import ceil, exp

from animation import load_pixel_image


class Camera:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.x, self.y = 0.0, -160.0
        self.zoom = 1.0

    def project(self, x, y):
        return (x-self.x)*self.zoom, 720-(720-y+self.y)*self.zoom

    def focus(self, x, y, world_width, dt):
        """월드의 두 인물을 향해 이동한다. UI와 말풍선은 확대하지 않는다."""
        weight = 1-exp(-4.0*dt)
        self.zoom += (1.18-self.zoom)*weight
        target_x = max(0, min(world_width-self.width/self.zoom, x-self.width/(2*self.zoom)))
        target_y = y-720+(720-315)/self.zoom
        self.x += (target_x-self.x)*weight
        self.y += (target_y-self.y)*weight

    def follow(self, player, world_width, dt=0.0, *, snap=False):
        # 이동 방향을 조금 더 보여 주고, 낮은 점프에는 화면이 덜 흔들리게 한다.
        target_x = player.x + player.facing * 80 - self.width / 2
        target_x = max(0.0, min(world_width - self.width, target_x))
        target_y = -160.0 + max(0.0, player.y - 80.0) * 0.65
        weight = 1.0 if snap else 1.0 - exp(-8.0 * dt)
        self.zoom += (1.0-self.zoom)*weight
        self.x += (target_x - self.x) * weight
        self.y += (target_y - self.y) * weight


class World:
    BACKGROUND_SCALE = 1.0
    STAGE_WIDTH_SCALE = 2.0

    def __init__(self, folder, screen_width):
        self.folder = folder
        self.screen_width = screen_width
        self.stages = json.loads(
            (folder / 'asset_manifest.json').read_text(encoding='utf-8')
        )['stages']
        self.set_stage(0)

    def set_stage(self, index):
        self.index = index
        self.stage = self.stages[index]
        self.background = load_pixel_image(self.folder / self.stage['bg']['file'])
        self.ground = load_pixel_image(self.folder / self.stage['ground']['file'])
        self.width = round(self.background.w * self.STAGE_WIDTH_SCALE)
        # 지면은 확대하지 않는다. 그림의 발판 높이만 충돌 바닥 y=0에 맞춘다.
        self.ground_height = self.ground.h
        self.ground_top = self.stage['ground']['surfaceY']

    def change_stage(self, player):
        if player.x >= self.width - 96 and self.index < len(self.stages) - 1:
            self.set_stage(self.index + 1)
            player.x = 180.0
            return True
        if player.x <= 96 and self.index > 0:
            self.set_stage(self.index - 1)
            player.x = self.width - 180.0
            return True
        player.x = max(96.0, min(self.width - 96.0, player.x))
        return False

    def draw(self, camera):
        bg_width = round(self.background.w * self.BACKGROUND_SCALE)
        bg_height = round(self.background.h * self.BACKGROUND_SCALE)
        # 원경은 지면보다 천천히 이동한다. 양 끝에서도 빈 화면이 생기지 않는다.
        progress = camera.x / max(1.0, self.width - self.screen_width)
        bg_scroll = progress * (bg_width - self.screen_width)
        # 그리기 좌표만 픽셀에 맞춘다. 실제 이동과 카메라 계산은 실수로 유지한다.
        # 원본 배경을 1:1로 사용한다. 점프의 세로 시차는 여분 높이 안에서만 움직인다.
        bottom = round(max(720-bg_height, min(0, (720-bg_height)/2-(camera.y+160)*.04)))
        left = round(-bg_scroll)
        self.background.draw(left + bg_width / 2, bottom + bg_height / 2, bg_width, bg_height)
        bottom = round(self.ground_top - self.ground_height - camera.y)
        first = max(0, int(camera.x) // self.ground.w)
        last = min(ceil(self.width / self.ground.w),
                   ceil((camera.x + self.screen_width) / self.ground.w))
        # 원본 픽셀 크기로 이어 붙이고, 번갈아 뒤집어 양쪽 경계를 맞춘다.
        for tile in range(first, last):
            left = round(tile * self.ground.w - camera.x)
            self.ground.composite_draw(
                0, 'h' if tile % 2 else '',
                left + self.ground.w / 2, bottom + self.ground_height / 2,
                self.ground.w, self.ground_height,
            )
