"""인트로·시작 화면·이어하기·완결 가능한 한 판을 연결한다."""
from pathlib import Path
import pico2d.pico2d as engine
from pico2d import (
    SDL_QUIT, SDL_KEYDOWN, SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT,
    SDLK_ESCAPE, SDLK_RETURN, SDLK_SPACE, SDLK_UP, SDLK_DOWN, SDLK_n, load_music,
)
from interface import Interface, fill
from video import IntroVideo
from progress import SaveStore
from campaign import Campaign
from transitions import FrameBlend


class GameApplication:
    def __init__(self, root, skip_intro=False):
        self.root = Path(root)
        self.assets = self.root / 'assets'
        self.ui = Interface(self.assets)
        self.store = SaveStore(self.root)
        self.video = None if skip_intro else IntroVideo(self.assets / 'cinematic/intro.mp4')
        self.music = load_music(str(self.assets / 'cinematic/intro.ogg')) if engine.audio_on and not skip_intro else None
        if self.music:
            self.music.set_volume(72)
            self.music.play()
        self.state = 'menu' if skip_intro else 'intro'
        self.running, self.selected, self.elapsed = True, 0, 0.0
        self.keys = set()
        self.game = None
        self.new_selected = 1
        self.blend=FrameBlend()

    @property
    def player(self):
        return self.game.player if self.game else None

    def _menu(self):
        if self.video:
            self.video.close()
            self.video = None
        if self.music:
            self.music.stop()
        if self.game:
            self.game.close()
        self.game = None
        self.state, self.selected, self.elapsed = 'menu', 0, 0.0
        self.keys = set()

    def _start(self, resume=None):
        if self.game:
            self.game.close()
        self.game = Campaign(self.root, self.ui, self.store, bool(self.store.checkpoint) if resume is None else resume)
        self.keys = self.game.keys
        self.state = 'game'

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
        if self.state == 'intro':
            if event.type == SDL_KEYDOWN and event.key in {SDLK_RETURN, SDLK_SPACE, SDLK_ESCAPE}:
                self._menu()
        elif self.state == 'controls':
            if event.type == SDL_KEYDOWN and event.key == SDLK_ESCAPE:
                self.state = 'menu'
            elif event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
                if 520 <= event.x <= 760 and 659 <= event.y <= 702:
                    self.state = 'menu'
        elif self.state == 'confirm_new':
            if event.type == SDL_KEYDOWN:
                if event.key in {SDLK_UP, SDLK_DOWN}:
                    self.new_selected = 1-self.new_selected
                elif event.key in {SDLK_RETURN, SDLK_SPACE}:
                    if self.new_selected == 0:
                        self._start(resume=False)
                    else:
                        self.state = 'menu'
                elif event.key == SDLK_ESCAPE:
                    self.state = 'menu'
        elif self.state == 'menu':
            if event.type in {SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN}:
                hit = self.ui.hit(event.x, 720-event.y)
                if hit is not None:
                    self.selected = hit
                    if event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
                        self._choose()
            elif event.type == SDL_KEYDOWN:
                if event.key in {SDLK_UP, SDLK_DOWN}:
                    self.selected = (self.selected+(1 if event.key == SDLK_DOWN else -1))%3
                elif event.key in {SDLK_RETURN, SDLK_SPACE}:
                    self._choose()
                elif event.key == SDLK_n:
                    if self.store.checkpoint:
                        self.state, self.new_selected = 'confirm_new', 1
                    else:
                        self._start(resume=False)
                elif event.key == SDLK_ESCAPE:
                    self.running = False
        else:
            self.game.handle(event)

    def update(self, dt):
        self.blend.update(dt)
        self.ui.update(dt)
        if self.state == 'intro':
            self.video.update(dt)
            if self.video.finished:
                self._menu()
        elif self.state in {'menu', 'confirm_new'}:
            self.elapsed += dt
        elif self.state == 'game':
            self.game.update(dt)
            if self.game.request == 'menu':
                self._menu()
            elif self.game.request == 'new':
                self._start(resume=False)

    def draw(self):
        s=self.game
        key=(self.state,id(s),(s.run.stage,s.run.page) if s else (-1,-1),s.ui_serial if s else 0,
             s.journal_page if s and s.modal and s.modal['kind']=='journal' else -1,s.run.ending if s else '')
        self.blend.draw(self.draw_content,key)

    def draw_content(self):
        if self.state == 'intro':
            self.video.draw()
        elif self.state in {'menu', 'confirm_new'}:
            self.ui.BUTTONS = ('이어하기' if self.store.checkpoint else '게임 시작', '조작 설명', '종료')
            self.ui.draw_menu(self.selected)
            self.ui.text('N · 새로운 세계선 시작', 122, 52, 16, (185, 180, 196))
            if self.state == 'confirm_new':
                fill(200, 170, 880, 350, (8, 15, 24, 248))
                self.ui.text('새 모험을 시작할까요?', 640, 455, 34, center=True)
                self.ui.text('이전 완결 기록은 남고, 진행 중인 저장 지점은 새 모험으로 바뀝니다.', 640, 396, 20, center=True)
                for i, text in enumerate(['새로운 세계선 시작', '돌아가기']):
                    self.ui.text(('▶ ' if self.new_selected==i else '   ')+text, 640, 310-i*65, 26, center=True)
            elif self.elapsed < .7:
                fill(0, 0, 1280, 720, (0, 0, 0, round(255*(1-self.elapsed/.7))))
            if self.store.error:
                self.ui.text(self.store.error, 640, 20, 16, (235, 154, 154), True)
        elif self.state == 'controls':
            self.ui.draw_controls()
        else:
            self.game.draw()

    def close(self):
        self.blend.close()
        if self.video:
            self.video.close()
            self.video = None
        if self.music:
            self.music.stop()
            self.music = None
        if self.game:
            self.game.close()
        self.game = self.ui = None
