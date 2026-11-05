"""움직이는 시작 화면과 펼친 책 형태의 조작 설명."""

from ctypes import byref, c_int
import json
from pathlib import Path

import pico2d.pico2d as engine
from pico2d import (load_font, SDL_Rect, SDL_SetRenderDrawColor, SDL_RenderFillRect,
                    SDL_RenderDrawRect, SDL_SetRenderDrawBlendMode, SDL_BLENDMODE_BLEND, TTF_SizeUTF8, SDL_SetTextureColorMod)

from animation import load_pixel_image
from scene_layout import sword_layout, socket_layout
from aura_motion import smoke_draws


def fill(x, y, width, height, color):
    SDL_SetRenderDrawBlendMode(engine.renderer, SDL_BLENDMODE_BLEND)
    SDL_SetRenderDrawColor(engine.renderer, *color)
    SDL_RenderFillRect(engine.renderer, SDL_Rect(round(x), round(720 - y - height), round(width), round(height)))


class Interface:
    BUTTONS = ('게임 시작', '조작 설명', '종료')
    RECTS = ((120, 318, 360, 64), (120, 230, 360, 64), (120, 142, 360, 64))

    def __init__(self, assets):
        font = Path('C:/Windows/Fonts/malgun.ttf')
        bold = Path('C:/Windows/Fonts/malgunbd.ttf')
        self.fonts = {size: load_font(str(bold if size >= 30 else font), size) for size in (16, 18, 20, 22, 26, 34, 48, 76)}
        self.background = load_pixel_image(assets / 'ui/menu_background.png')
        self.book = load_pixel_image(assets / 'ui/controls_book.png')
        data = json.loads((assets / 'cinematic/cinematic.json').read_text(encoding='utf8'))
        self.layout = data['menuLayout']
        self.weapon = data['assets']['black_sword']
        self.socket = data['assets']['soil_socket']
        self.smoke = data['assets']['menu_smoke']
        self.sword_image = load_pixel_image(assets / 'cinematic' / self.weapon['file'])
        self.socket_image = load_pixel_image(assets / 'cinematic' / self.socket['file'])
        self.smoke_image = load_pixel_image(assets / 'ui' / self.smoke['file'])
        SDL_SetTextureColorMod(self.sword_image.texture, *self.layout['swordTint'])
        SDL_SetTextureColorMod(self.socket_image.texture, *self.layout['socketTint'])
        self.time = 0.0

    def text(self, value, x, y, size=22, color=(233, 229, 239), center=False):
        if size not in self.fonts:
            self.fonts[size] = load_font('C:/Windows/Fonts/malgun.ttf', size)
        font = self.fonts[size]
        if center:
            width, height = c_int(), c_int()
            TTF_SizeUTF8(font.font, value.encode('utf8'), byref(width), byref(height))
            x -= width.value / 2
        font.draw(round(x), round(y), value, color)

    def update(self, dt):
        self.time += dt

    @classmethod
    def hit(cls, x, y):
        for i, (left, bottom, w, h) in enumerate(cls.RECTS):
            if left <= x <= left + w and bottom <= y <= bottom + h:
                return i
        return None

    @staticmethod
    def _piece(image, geometry):
        x0, y0, x1, y1 = geometry['crop']
        image.clip_draw(round(x0), image.h - round(y1), round(x1 - x0), round(y1 - y0),
            round(geometry['left'] + geometry['width'] / 2),
            round(720 - geometry['top'] - geometry['height'] / 2),
            round(geometry['width']), round(geometry['height']))

    def _blade_smoke(self, geometry, front=False):
        for item in smoke_draws(geometry, self.layout, self.smoke, self.time, front):
            self.smoke_image.opacify(item['opacity'])
            self._piece(self.smoke_image, item['geometry'])
        self.smoke_image.opacify(1.0)

    def draw_menu(self, selected):
        self.background.draw(640, 360, 1280, 720)
        geometry = sword_layout(self.weapon, self.layout)
        self._piece(self.socket_image, socket_layout(self.socket, self.layout))
        self._blade_smoke(geometry)
        self._piece(self.sword_image, geometry)
        self._piece(self.socket_image, socket_layout(self.socket, self.layout, front=True))
        self._blade_smoke(geometry, front=True)
        for x in range(0, 660, 20):
            fill(x, 0, 20, 720, (5, 8, 16, round(85 * (1 - x / 660) ** 2)))
        self.text('DEMON SWORD', 122, 619, 18, (166, 151, 190))
        self.text('마검사', 116, 554, 76)
        self.text('시뮬레이터', 120, 476, 48, (201, 183, 224))
        fill(122, 435, 356, 1, (168, 140, 196, 150))
        self.text('당신의 선택이 마검사의 운명을 바꾼다', 122, 410, 18, (173, 176, 191))
        for i, (left, bottom, w, h) in enumerate(self.RECTS):
            active = i == selected
            fill(left, bottom, w, h, (48, 35, 66, 224) if active else (12, 15, 25, 210))
            SDL_SetRenderDrawColor(engine.renderer, *( (201, 169, 231, 245) if active else (84, 78, 105, 220) ))
            SDL_RenderDrawRect(engine.renderer, SDL_Rect(left, 720 - bottom - h, w, h))
            self.text(self.BUTTONS[i], left + w / 2, bottom + h / 2, 26, center=True)
        self.text('↑ ↓ 선택   Enter 확인   마우스 클릭', 122, 83, 16, (157, 157, 175))

    def draw_controls(self):
        self.book.draw(640, 360, 1280, 720)
        ink, faint = (55, 35, 25), (90, 60, 35)
        self.text('이동과 생존', 365, 587, 34, ink, True)
        self.text('마검의 힘', 922, 587, 34, ink, True)
        left = [('←  →', '걷기 · 계속 누르면 달리기'), ('↑', '점프'), ('↓', '웅크리기 · 웅크려 이동'),
                ('Shift', '지상 대시 · 공중 대시'), ('X', '방어 · 정확히 막으면 피해 0'), ('Esc', '일시 정지 · 저장 · 돌아가기')]
        right = [('C 연속 입력', '기본 베기 1 → 2 → 3'), ('대시 끝에서 C', '대시 베기 · 대시 중 입력은 무시'),
                 ('Z → C', '해금 후 집중 → 마검파'), ('E / H / Q', '상호작용 / 회복 / 동료 지원'), ('Tab / L / 1~8', '기록책 / 성장 / 열린 지역 이동'),
                 ('↑ ↓ / Enter', '선택창 선택 / 확인')]
        for x, rows in ((181, left), (738, right)):
            for i, (key, detail) in enumerate(rows):
                y = 517 - i * 58
                self.text(key, x, y, 22, ink)
                self.text(detail, x, y - 29, 18, faint)
        fill(520, 18, 240, 43, (18, 13, 15, 220))
        self.text('돌아가기 · Esc', 640, 40, 20, (228, 210, 174), True)

    def draw_hud(self, player):
        fill(22, 653, 306, 45, (9, 12, 22, 185))
        self.text('HP', 36, 677, 18)
        fill(74, 671, 150, 10, (57, 42, 53, 255))
        fill(74, 671, 150 * player.hp / 100, 10, (193, 102, 126, 255))
        self.text(f'{player.hp:3d}', 239, 677, 18)
        fill(22, 603, 306, 42, (9, 12, 22, 185))
        self.text(f'검기 {player.effects.level}단계', 36, 625, 18, (197, 179, 228))
        remain = player.effects.buff_remaining
        if remain > 0:
            self.text(f'마검파 {remain:.1f}초', 175, 625, 18, (187, 159, 233))
