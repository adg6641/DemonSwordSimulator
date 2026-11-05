"""별도 파일 없이 짧은 효과음만 만든다. 음성·배경음악은 사용하지 않는다."""
from ctypes import c_char_p, c_void_p, cast
from io import BytesIO
from math import sin, pi
import random
import struct
import wave
import pico2d.pico2d as engine
from pico2d import (SDL_RWFromConstMem, Mix_LoadWAV_RW, Mix_PlayChannel, Mix_VolumeChunk,
                    Mix_FreeChunk, Mix_HaltChannel)


class Sounds:
    def __init__(self):
        self.chunks = {}
        if not engine.audio_on:
            return
        # 짧게 사라지는 음을 써서 공격·방어·획득의 타이밍만 알려 준다.
        for name, duration, f0, f1, noise in [
            ('slash', .12, 420, 90, .7), ('hit', .1, 180, 55, .75),
            ('dash', .16, 240, 70, .65), ('jump', .12, 240, 460, .05),
            ('guard', .2, 1100, 680, .15), ('pickup', .24, 530, 950, .02),
            ('level', .4, 440, 1100, .01), ('select', .07, 620, 510, .01),
            ('death', .48, 190, 45, .1), ('magic', .3, 310, 730, .08),
        ]:
            rng, rate = random.Random(name), 22050
            pcm = bytearray()
            for i in range(int(rate*duration)):
                t, u = i/rate, i/(rate*duration)
                phase = 2*pi*(f0*t+(f1-f0)*t*t/(2*duration))
                sample = ((1-noise)*sin(phase)+noise*rng.uniform(-1, 1))*(1-u)**2*min(1, u*35)*.28
                pcm.extend(struct.pack('<h', round(sample*32767)))
            buffer = BytesIO()
            with wave.open(buffer, 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(pcm)
            data = buffer.getvalue()
            memory = SDL_RWFromConstMem(cast(c_char_p(data), c_void_p), len(data))
            chunk = Mix_LoadWAV_RW(memory, 1)
            if chunk:
                Mix_VolumeChunk(chunk, 38)
                self.chunks[name] = chunk

    def play(self, name):
        if name in self.chunks:
            Mix_PlayChannel(-1, self.chunks[name], 0)

    def close(self):
        if self.chunks:
            Mix_HaltChannel(-1)
            for chunk in self.chunks.values():
                Mix_FreeChunk(chunk)
            self.chunks.clear()
