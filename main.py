"""마검사 시뮬레이터: 배경과 주인공 조작 프로토타입."""

from pathlib import Path
from time import perf_counter

from pico2d import (
    SDL_KEYDOWN, SDL_KEYUP, SDL_QUIT, SDL_GetKeyboardFocus, SDLK_ESCAPE,
    open_canvas, close_canvas, clear_canvas, update_canvas, get_events,
)

from player import Player
from world import Camera, World


WIDTH, HEIGHT = 1280, 720
STEP = 1.0 / 120.0
ROOT = Path(__file__).resolve().parent


def main():
    open_canvas(WIDTH, HEIGHT, sync=True)
    player = world = None
    try:
        world = World(ROOT / '배경이미지', WIDTH)
        player = Player(ROOT / '마검사_주인공_애니메이션')
        camera = Camera(WIDTH, HEIGHT)
        camera.follow(player, world.width, snap=True)
        keys = set()
        running = True
        previous = perf_counter()
        accumulated = 0.0

        while running:
            now = perf_counter()
            accumulated += min(now - previous, 0.1)
            previous = now
            for event in get_events():
                if event.type == SDL_QUIT:
                    running = False
                elif event.type == SDL_KEYDOWN:
                    if event.key == SDLK_ESCAPE:
                        running = False
                    else:
                        keys.add(event.key)
                        player.press(event.key, keys)
                elif event.type == SDL_KEYUP:
                    keys.discard(event.key)
            if not running:
                break
            if not SDL_GetKeyboardFocus():
                keys.clear()

            # 화면 주사율과 관계없이 이동과 점프를 같은 시간 간격으로 계산한다.
            while accumulated >= STEP:
                player.update(STEP, keys)
                changed = world.change_stage(player)
                camera.follow(player, world.width, STEP, snap=changed)
                accumulated -= STEP

            clear_canvas()
            world.draw(camera)
            player.draw(camera)
            update_canvas()
    finally:
        # pico2d의 렌더러를 닫기 전에 이미지 참조를 정리한다.
        player = world = None
        close_canvas()


if __name__ == '__main__':
    main()
