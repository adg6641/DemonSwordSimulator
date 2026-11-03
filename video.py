"""MP4를 한 프레임씩 읽어 재생한다. 전체 영상을 메모리에 올리지 않는다."""

from ctypes import c_char_p, cast, c_void_p

import imageio_ffmpeg
import pico2d.pico2d as engine
from pico2d import Image, SDL_CreateTexture, SDL_TEXTUREACCESS_STREAMING, SDL_PIXELFORMAT_RGB24, SDL_UpdateTexture


class IntroVideo:
    def __init__(self, path):
        self.reader = imageio_ffmpeg.read_frames(str(path), pix_fmt='rgb24')
        metadata = next(self.reader)
        self.width, self.height = metadata['size']
        self.fps, self.duration = metadata['fps'], metadata['duration']
        texture = SDL_CreateTexture(engine.renderer, SDL_PIXELFORMAT_RGB24,
                                    SDL_TEXTUREACCESS_STREAMING, self.width, self.height)
        if not texture:
            self.reader.close()
            raise RuntimeError('인트로 화면을 만들 수 없습니다.')
        self.image = Image(texture)
        self.elapsed = 0.0
        self.index = -1
        self.finished = False
        self._read()

    def _read(self):
        try:
            pixels = next(self.reader)
        except StopIteration:
            self.finished = True
            return
        result = SDL_UpdateTexture(self.image.texture, None, cast(c_char_p(pixels), c_void_p), self.width * 3)
        if result != 0:
            raise RuntimeError('인트로 프레임을 표시할 수 없습니다.')
        self.index += 1

    def update(self, dt):
        self.elapsed += dt
        target = int(self.elapsed * self.fps)
        while not self.finished and self.index < target:
            self._read()

    def draw(self):
        self.image.draw(640, 360, 1280, 720)

    def close(self):
        self.reader.close()
        self.image = None
