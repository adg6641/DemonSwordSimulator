"""1초 대기 → 인트로 → 시작 화면 → 조작 설명 또는 본 게임."""

import pico2d.pico2d as engine
from pico2d import (
    SDL_QUIT, SDL_KEYDOWN, SDL_KEYUP, SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN,
    SDL_BUTTON_LEFT, SDLK_ESCAPE, SDLK_RETURN, SDLK_SPACE, SDLK_UP, SDLK_DOWN,
    SDLK_1, SDLK_8, SDLK_F1, SDLK_F7, load_music,
)

from interface import Interface, fill
from player import Player
from video import IntroVideo
from world import Camera, World


class GameApplication:
    def __init__(self, root):
        self.assets = root / 'assets'
        self.ui = Interface(self.assets)
        self.video = IntroVideo(self.assets / 'cinematic/intro.mp4')
        self.music = load_music(str(self.assets / 'cinematic/intro.ogg')) if engine.audio_on else None
        if self.music:
            self.music.set_volume(72)
        self.state, self.elapsed = 'boot', 0.0
        self.running, self.selected = True, 0
        self.player = self.world = self.camera = None
        self.keys = set()

    def _menu(self):
        if self.video:
            self.video.close()
            self.video = None
        if self.music:
            self.music.stop()
        self.state, self.selected, self.elapsed = 'menu', 0, 0.0
        self.keys.clear()

    def _start(self):
        self.world = World(self.assets / 'world', 1280)
        self.player = Player(self.assets / 'hero')
        self.camera = Camera(1280, 720)
        self.camera.follow(self.player, self.world.width, snap=True)
        self.state = 'game'
        self.keys.clear()

    def _choose(self):
        if self.selected == 0:
            self._start()
        elif self.selected == 1:
            self.state = 'controls'
        else:
            self.running = False

    def handle(self, event):
        if event.type == SDL_QUIT:
            self.running = False
            return
        if self.state == 'boot':
            return
        if self.state == 'intro':
            if event.type == SDL_KEYDOWN and event.key in {SDLK_RETURN, SDLK_SPACE, SDLK_ESCAPE}:
                self._menu()
            return
        if self.state == 'controls':
            if event.type == SDL_KEYDOWN and event.key == SDLK_ESCAPE:
                self.state = 'menu'
            elif event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
                if 520 <= event.x <= 760 and 659 <= event.y <= 702:
                    self.state = 'menu'
            return
        if self.state == 'menu':
            if event.type in {SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN}:
                hit = self.ui.hit(event.x, 720 - event.y)
                if hit is not None:
                    self.selected = hit
                    if event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
                        self._choose()
            elif event.type == SDL_KEYDOWN:
                if event.key in {SDLK_UP, SDLK_DOWN}:
                    self.selected = (self.selected + (1 if event.key == SDLK_DOWN else -1)) % 3
                elif event.key in {SDLK_RETURN, SDLK_SPACE}:
                    self._choose()
                elif event.key == SDLK_ESCAPE:
                    self.running = False
            return
        if event.type == SDL_KEYUP:
            self.keys.discard(event.key)
        elif event.type == SDL_KEYDOWN:
            if event.key == SDLK_ESCAPE:
                self._menu()
            elif SDLK_1 <= event.key <= SDLK_8:
                level = self.player.effects.level
                self.world.set_stage(event.key - SDLK_1)
                self.player = Player(self.assets / 'hero')
                self.player.effects.level = level
                self.camera.follow(self.player, self.world.width, snap=True)
                self.keys.clear()
            elif SDLK_F1 <= event.key <= SDLK_F7:
                self.player.effects.level = event.key - SDLK_F1 + 1
            elif event.key not in self.keys:
                self.keys.add(event.key)
                self.player.press(event.key, self.keys)

    def update(self, dt):
        self.ui.update(dt)
        if self.state == 'boot':
            self.elapsed += dt
            if self.elapsed >= 1.0:
                self.state = 'intro'
                if self.music:
                    self.music.play()
        elif self.state == 'intro':
            self.video.update(dt)
            if self.video.finished:
                self._menu()
        elif self.state == 'menu':
            self.elapsed += dt
        elif self.state == 'game':
            self.player.update(dt, self.keys)
            changed = self.world.change_stage(self.player)
            self.camera.follow(self.player, self.world.width, dt, snap=changed)

    def draw(self):
        if self.state == 'boot':
            fill(0, 0, 1280, 720, (0, 0, 0, 255))
        elif self.state == 'intro':
            self.video.draw()
            self.ui.text('Enter · 건너뛰기', 1122, 28, 16, (180, 176, 187))
        elif self.state == 'menu':
            self.ui.draw_menu(self.selected)
            if self.elapsed < .7:
                fill(0, 0, 1280, 720, (0, 0, 0, round(255 * (1 - self.elapsed / .7))))
        elif self.state == 'controls':
            self.ui.draw_controls()
        else:
            self.world.draw(self.camera)
            self.player.draw(self.camera)
            self.ui.draw_hud(self.player)

    def close(self):
        if self.video:
            self.video.close()
            self.video = None
        if self.music:
            self.music.stop()
            self.music = None
        # SDL 화면을 닫기 전에 그 화면에 속한 이미지도 함께 정리한다.
        self.player = self.world = self.ui = None
