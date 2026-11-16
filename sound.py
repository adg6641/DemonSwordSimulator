"""WAV 효과음을 미리 읽고 장면별 환경음과 함께 섞는다."""
from ctypes import c_char_p, c_void_p, cast
from pathlib import Path
import json

import pico2d.pico2d as engine
from pico2d import SDL_RWFromConstMem
from sdl2.sdlmixer import (
    Mix_AllocateChannels, Mix_FreeChunk, Mix_HaltChannel, Mix_LoadWAV_RW,
    Mix_PlayChannel, Mix_Playing, Mix_SetPanning, Mix_Volume,
)


# 환경음 두 채널로 이전 장면과 다음 장면을 겹쳐 잇는다.
# 발소리와 주변 몹이 늘어나도 공격·경고·선택음은 자기 채널을 쓴다.
CHANNELS = {
    'steps': range(3, 7), 'player': range(7, 13), 'world': range(13, 21),
    'ui': range(21, 24), 'critical': range(24, 29),
}


class Sounds:
    def __init__(self, folder=None):
        self.catalog = {}
        self.chunks = {}
        self.last = {}
        self.variants = {}
        self.started = {}
        self.ambience = [None, None, None]
        self.elapsed = 0.0
        self.scene = None
        self.camp = False
        self.duck = self.duck_target = 1.0
        if not engine.audio_on:
            return
        folder = Path(folder) if folder else Path(__file__).parent / 'assets/audio'
        try:
            self.catalog = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        except OSError:
            return
        Mix_AllocateChannels(29)
        for name, cue in self.catalog.items():
            takes = []
            for file in cue['files']:
                try:
                    data = (folder / file).read_bytes()
                except OSError:
                    continue
                memory = SDL_RWFromConstMem(cast(c_char_p(data), c_void_p), len(data))
                if memory:
                    chunk = Mix_LoadWAV_RW(memory, 1)
                    if chunk:
                        takes.append(chunk)
            if takes:
                self.chunks[name] = takes

    @staticmethod
    def _volume(channel, gain):
        Mix_Volume(channel, round(128 * min(1, max(0, gain))))

    def play(self, name, *, gain=1.0, pan=0.0):
        takes = self.chunks.get(name)
        if not takes or gain <= 0:
            return
        cue = self.catalog[name]
        channels = CHANNELS.get(cue['bus'])
        if channels is None or self.elapsed - self.last.get(name, -10) < cue['cooldown']:
            return
        channel = next((c for c in channels if not Mix_Playing(c)), None)
        if channel is None:
            # 채널이 꽉 차면 중요도가 낮고 먼저 시작한 소리부터 양보한다.
            channel = min(channels, key=lambda c: self.started[c])
            if self.started[channel][0] > cue['priority']:
                return
        index = self.variants.get(name, 0)
        self._volume(channel, gain * cue['gain'] * .88)
        if Mix_PlayChannel(channel, takes[index], 0) < 0:
            return
        left = round(255 * (1 - max(0, min(1, pan))))
        right = round(255 * (1 - max(0, min(1, -pan))))
        Mix_SetPanning(channel, left, right)
        self.started[channel] = cue['priority'], self.elapsed
        self.variants[name] = (index + 1) % len(takes)
        self.last[name] = self.elapsed
        return channel

    def at(self, name, dx, dy, *, gain=1.0):
        distance = (dx * dx + (dy * 1.25) ** 2) ** .5
        if distance < 1100:
            gain *= 1 - max(0, distance - 90) / 1010
            return self.play(name, gain=gain, pan=max(-.78, min(.78, dx / 630)))

    def _loop(self, channel, name):
        takes = self.chunks.get(name)
        if takes:
            self._volume(channel, 0)
            if Mix_PlayChannel(channel, takes[0], -1) >= 0:
                self.ambience[channel] = [name, 0.0]

    def set_scene(self, scene):
        if self.scene == scene:
            return
        self.scene = scene
        name = 'amb_' + scene
        if not any(slot and slot[0] == name for slot in self.ambience[:2]):
            channel = min(range(2), key=lambda c: self.ambience[c][1] if self.ambience[c] else -1)
            self._loop(channel, name)

    def set_context(self, *, quiet=False, camp=False):
        self.duck_target = .58 if quiet else 1.0
        self.camp = camp
        if camp and not self.ambience[2]:
            self._loop(2, 'amb_camp')

    def clear_scene_events(self):
        if self.chunks:
            for bus in ('steps', 'player', 'world'):
                for channel in CHANNELS[bus]:
                    Mix_HaltChannel(channel)
        self.set_context()

    def update(self, dt):
        self.elapsed += dt
        self.duck += (self.duck_target - self.duck) * min(1, dt * 5)
        for channel, slot in enumerate(self.ambience):
            if not slot:
                continue
            name, volume = slot
            active = self.camp if channel == 2 else name == 'amb_' + self.scene
            volume = min(1.0, volume + dt * 1.5) if active else max(0.0, volume - dt * 1.5)
            if not active and not volume:
                Mix_HaltChannel(channel)
                self.ambience[channel] = None
            else:
                slot[1] = volume
                self._volume(channel, volume * self.catalog[name]['gain'] * (1 if channel == 2 else self.duck))

    def close(self):
        if self.chunks:
            Mix_HaltChannel(-1)
            for takes in self.chunks.values():
                for chunk in takes:
                    Mix_FreeChunk(chunk)
            self.chunks.clear()
        self.ambience = [None, None, None]
