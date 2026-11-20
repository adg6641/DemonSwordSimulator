"""마검사 시뮬레이터. 실행하면 인트로와 시작 화면이 먼저 나타난다."""

from pathlib import Path
from time import perf_counter
import argparse
import gc

import pico2d.pico2d as engine
from pico2d import (open_canvas, close_canvas, hide_lattice, clear_canvas, update_canvas,
                    Event, SDL_Event, SDL_PollEvent, SDL_QUIT, SDL_KEYDOWN, SDL_KEYUP,
                    SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN, SDL_MOUSEBUTTONUP, SDL_MOUSEWHEEL,
                    SDL_GetKeyboardFocus, SDL_SetWindowTitle, SDL_TEXTINPUT, SDL_TEXTEDITING)

from application import GameApplication


WIDTH, HEIGHT = 1280, 720
STEP = 1.0 / 120.0
ROOT = Path(__file__).resolve().parent


def events():
    # 입력을 읽을 때마다 창 제목을 바꾸거나 렌더 루프를 멈추지 않는다.
    raw = SDL_Event()
    while SDL_PollEvent(raw):
        event = Event(raw.type)
        if raw.type in (SDL_KEYDOWN, SDL_KEYUP):
            if raw.key.repeat:
                continue
            event.key = raw.key.keysym.sym
            event.mod = raw.key.keysym.mod
        elif raw.type == SDL_TEXTINPUT:
            event.text=bytes(raw.text.text).split(b'\0',1)[0].decode('utf8')
        elif raw.type == SDL_TEXTEDITING:
            event.text=bytes(raw.edit.text).split(b'\0',1)[0].decode('utf8')
        elif raw.type == SDL_MOUSEMOTION:
            event.x, event.y = raw.motion.x, raw.motion.y
        elif raw.type in (SDL_MOUSEBUTTONDOWN, SDL_MOUSEBUTTONUP):
            event.button, event.x, event.y = raw.button.button, raw.button.x, raw.button.y
        elif raw.type == SDL_MOUSEWHEEL:
            event.x, event.y = raw.wheel.x, raw.wheel.y
        elif raw.type != SDL_QUIT:
            continue
        yield event


def main():
    parser = argparse.ArgumentParser(description='마검사 시뮬레이터')
    parser.add_argument('--skip-intro', action='store_true', help='인트로를 건너뛰고 시작 화면 표시')
    options = parser.parse_args()
    open_canvas(WIDTH, HEIGHT, sync=True)
    hide_lattice()
    SDL_SetWindowTitle(engine.window, '마검사 시뮬레이터'.encode('utf8'))
    engine.SDL_SetRenderDrawColor(engine.renderer, 0, 0, 0, 255)
    engine.SDL_RenderClear(engine.renderer)
    update_canvas()
    app = None
    try:
        app = GameApplication(ROOT, skip_intro=options.skip_intro)
        previous, accumulated = perf_counter(), 0.0
        while app.running:
            now = perf_counter()
            accumulated += min(now - previous, .1)
            previous = now
            for event in events():
                app.handle(event)
            if not app.running:
                break
            if not SDL_GetKeyboardFocus():
                app.keys.clear()
            while accumulated >= STEP:
                app.update(STEP)
                accumulated -= STEP
            clear_canvas()
            app.draw()
            update_canvas()
    finally:
        if app:
            app.close()
        gc.collect()
        close_canvas()


if __name__ == '__main__':
    main()
