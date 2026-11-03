"""마검사 시뮬레이터. 실행하면 인트로와 시작 화면이 먼저 나타난다."""

from pathlib import Path
from time import perf_counter

import pico2d.pico2d as engine
from pico2d import (open_canvas, close_canvas, hide_lattice, clear_canvas, update_canvas,
                    get_events, SDL_GetKeyboardFocus, SDL_SetWindowTitle)

from application import GameApplication


WIDTH, HEIGHT = 1280, 720
STEP = 1.0 / 120.0
ROOT = Path(__file__).resolve().parent


def main():
    open_canvas(WIDTH, HEIGHT, sync=True)
    hide_lattice()
    engine.SDL_SetRenderDrawColor(engine.renderer, 0, 0, 0, 255)
    engine.SDL_RenderClear(engine.renderer)
    update_canvas()
    app = None
    try:
        app = GameApplication(ROOT)
        previous, accumulated = perf_counter(), 0.0
        while app.running:
            now = perf_counter()
            accumulated += min(now - previous, .1)
            previous = now
            for event in get_events():
                app.handle(event)
            if not app.running:
                break
            SDL_SetWindowTitle(engine.window, '마검사 시뮬레이터'.encode('utf8'))
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
        close_canvas()


if __name__ == '__main__':
    main()
