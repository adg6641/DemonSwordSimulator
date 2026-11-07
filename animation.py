"""동작 정보에 맞춰 스프라이트 시트의 한 칸을 그린다."""

import json
from bisect import bisect_right
from itertools import accumulate
from math import cos, sin, pi
from collections import OrderedDict

from pico2d import load_image, SDL_SetTextureScaleMode, SDL_ScaleModeNearest, SDL_ScaleModeLinear


def load_pixel_image(path, *, smooth=False):
    image = load_image(str(path))
    # 확대할 때 이웃 픽셀의 색을 섞지 않아 지면과 스프라이트가 흐려지지 않는다.
    SDL_SetTextureScaleMode(image.texture, SDL_ScaleModeLinear if smooth else SDL_ScaleModeNearest)
    return image


class Animation:
    def __init__(self, folder):
        self.folder = folder
        data = json.loads((folder / 'animations.json').read_text(encoding='utf-8'))
        self.clips = {clip['id']: clip for clip in data['clips']}
        self.weapon = data.get('weapon')
        self.images = OrderedDict()
        self.name = ''
        self.serial = 0
        self.play('idle_breathe')

    def add_story_clips(self, assets):
        for key, clip in assets.clips.items():
            if key.startswith('adv/hero_'):
                self.clips[key] = dict(clip, file=clip['path'])

    def play(self, name, *, fps=None, once=False, start_frame=None):
        previous_name, previous_frame = self.name, self.frame if self.name else 0
        self.name = name
        self.serial += 1
        self.clip = self.clips[name]
        self.fps = fps or self.clip['fps']
        durations=self.clip.get('frameDurations') if fps is None else None
        self.frame_ends=list(accumulate(durations)) if durations else None
        self.loop = self.clip['playback'] == 'loop' and not once
        if start_frame is None:
            entries=self.clip.get('entryFrames',{}).get(previous_name,[])
            start_frame=entries[min(previous_frame,len(entries)-1)] if entries else 0
        start_frame=max(0,min(self.clip['frameCount']-1,start_frame))
        self.elapsed=(self.frame_ends[start_frame-1]*self.clip['fps']/self.fps if start_frame and self.frame_ends else start_frame/self.fps)
        self.started_at=self.elapsed

    @property
    def progress(self):
        return max(0,min(1,(self.elapsed-self.started_at)/max(.001,self.duration-self.started_at)))

    @property
    def frame(self):
        count = self.clip['frameCount']
        if self.frame_ends:
            time=(self.elapsed%self.duration if self.loop else self.elapsed)*self.fps/self.clip['fps']
            return min(count-1,bisect_right(self.frame_ends,time))
        frame = int(self.elapsed * self.fps)
        return frame % count if self.loop else min(frame, count - 1)

    @property
    def duration(self):
        return self.frame_ends[-1]*self.clip['fps']/self.fps if self.frame_ends else self.clip['frameCount'] / self.fps

    @property
    def pose_time(self):
        """현재 자세 번호와 그 자세 안에서 흘러간 비율. 검기 판정도 같은 시계를 쓴다."""
        if not self.frame_ends:return self.elapsed*self.fps
        i=self.frame;start=self.frame_ends[i-1] if i else 0
        phase=max(0,min(1,(self.elapsed*self.fps/self.clip['fps']-start)/(self.frame_ends[i]-start)))
        return i+phase

    @property
    def finished(self):
        return not self.loop and self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    def image(self,path):
        if path not in self.images:self.images[path]=load_pixel_image(path,smooth=True)
        self.images.move_to_end(path)
        while len(self.images)>10:self.images.popitem(last=False)
        return self.images[path]

    @property
    def weapon_pose(self):
        """손은 현재 그림에 고정하고, 검은 길이를 바꾸지 않은 채 회전한다."""
        if not self.weapon:
            return None
        frames=self.clip['frames'];cell=frames[self.frame];point=cell.get('weapon')
        if not point or point.get('hidden'):
            return None
        following=frames[(self.frame+1)%len(frames)] if self.loop or self.frame+1<len(frames) else cell
        angle=point['angle'];next_angle=following.get('weapon',point)['angle']
        turn=(next_angle-angle+pi)%(2*pi)-pi
        angle+=turn*(self.pose_time%1)
        factor=cell.get('renderScale',1);pivot=self.clip['pivot']
        hand=tuple((point['hand'][i]-pivot[k])*factor for i,k in enumerate(('x','y')))
        length=self.weapon['handToTip']
        tip=(hand[0]+cos(angle)*length,hand[1]+sin(angle)*length)
        return dict(hand=hand,tip=tip,angle=angle,length=length)

    def draw(self, x, y, facing, camera, scale=1.0):
        from pathlib import Path
        sheet_path=self.folder/self.clip['file']
        path=str(sheet_path.parent/self.clip['bodyFile'] if self.clip.get('bodyFile') else sheet_path)
        body=self.image(path)
        frame = self.frame
        cell = self.clip['frames'][frame]
        width, height = cell['width'], cell['height']
        pivot = self.clip['pivot']
        # 큰 프레임만 같은 비율로 축소한다. 발 기준점과 팔다리 비율은 유지한다.
        scale *= cell.get('renderScale', 1.0)
        draw_width, draw_height = round(width * scale), round(height * scale)
        pivot_x = pivot['x'] if facing > 0 else width - pivot['x']
        left = round(x - camera.x - pivot_x * scale)
        bottom = round(y - camera.y - (height - pivot['y']) * scale)
        body.clip_composite_draw(
            cell['x'], cell['pico2dY'], width, height,
            0, 'h' if facing < 0 else '',
            left + draw_width / 2, bottom + draw_height / 2,
            draw_width, draw_height,
        )
        pose=self.weapon_pose
        if pose:
            sword_path=str(self.folder/self.weapon['file'])
            extra=scale/cell.get('renderScale',1)
            image=self.image(sword_path);grip=self.weapon['grip'];s=self.weapon['scale']*extra
            dx,dy=(image.w/2-grip['x'])*s,(image.h/2-grip['y'])*s
            angle=pose['angle'];cx=pose['hand'][0]*extra+dx*cos(angle)-dy*sin(angle);cy=pose['hand'][1]*extra+dx*sin(angle)+dy*cos(angle)
            image.composite_draw(-angle*facing,'h' if facing<0 else '',
                x-camera.x+facing*cx,y-camera.y-cy,image.w*s,image.h*s)
            # 검 손잡이 앞에 같은 원화의 손·손목만 다시 그려 자연스럽게 쥔다.
            hand_file=self.clip.get('handFile')
            if hand_file:
                hand_path=str(sheet_path.parent/hand_file)
                hand=self.image(hand_path);p=cell['weapon']['patch'];w,h=p['width'],p['height']
                cx=x-camera.x+facing*(p['left']+w/2-pivot['x'])*scale
                cy=y-camera.y+(pivot['y']-p['top']-h/2)*scale
                hand.clip_composite_draw(p['x'],p['pico2dY'],w,h,0,'h' if facing<0 else '',cx,cy,w*scale,h*scale)
