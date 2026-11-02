"""준비된 8개 배경과 지면, 주인공을 따라가는 카메라."""

import json
from math import exp

from animation import load_pixel_image


class Camera:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.x, self.y = 0.0, -160.0

    def follow(self, player, world_width, dt=0.0, *, snap=False):
        # 이동 방향을 조금 더 보여 주고, 낮은 점프에는 화면이 덜 흔들리게 한다.
        target_x = player.x + player.facing * 80 - self.width / 2
        target_x = max(0.0, min(world_width - self.width, target_x))
        target_y = -160.0 + max(0.0, player.y - 80.0) * 0.65
        weight = 1.0 if snap else 1.0 - exp(-8.0 * dt)
        self.x += (target_x - self.x) * weight
        self.y += (target_y - self.y) * weight


class World:
    BACKGROUND_SCALE = 1.5
    GROUND_SCALE = 2.0

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
        self.width = round(self.ground.w * self.GROUND_SCALE)
        preview = self.stage['preview']
        # 미리보기의 지면 상단을 실제 그림 크기로 환산한다. 충돌 바닥은 y=0.
        top = preview['approximateWalkingY'] - preview['groundTopOffset']
        source_top = top / preview['groundSize'][1] * self.ground.h
        self.ground_height = round(self.ground.h * self.GROUND_SCALE)
        self.ground_top = source_top * self.GROUND_SCALE

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
        bg_bottom = -bg_height * (1.0 - 560.0 / 720.0)
        # 그리기 좌표만 픽셀에 맞춘다. 실제 이동과 카메라 계산은 실수로 유지한다.
        left, bottom = round(-bg_scroll), round(bg_bottom - camera.y)
        self.background.draw(left + bg_width / 2, bottom + bg_height / 2, bg_width, bg_height)
        left = round(-camera.x)
        bottom = round(self.ground_top - self.ground_height - camera.y)
        self.ground.draw(
            left + self.width / 2, bottom + self.ground_height / 2,
            self.width, self.ground_height,
        )
