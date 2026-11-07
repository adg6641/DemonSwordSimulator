"""준비된 8개 배경과 지면, 주인공을 따라가는 카메라."""

import json
from math import ceil, exp

from animation import load_pixel_image


class Camera:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.x, self.y = 0.0, -160.0
        self.zoom = 1.0
        self.vx=self.vy=self.vz=0.0
        self.anchor=self.anchor_velocity=self.look=self.look_velocity=0.0

    @staticmethod
    def damp(value,target,velocity,dt,omega,limit):
        """급히 목표를 쫓지 않고, 속도를 가진 채 부드럽게 다가간다."""
        if dt<=0:return value,velocity
        offset=value-target;decay=exp(-omega*dt)
        change=(velocity+omega*offset)*dt
        new=target+(offset+change)*decay
        new_velocity=(velocity-omega*change)*decay
        delta=max(-limit*dt,min(limit*dt,new-value))
        if abs(delta-(new-value))>1e-7:new_velocity=delta/dt
        return value+delta,new_velocity

    def settle(self,x,y,zoom,world_width,dt):
        self.zoom,self.vz=self.damp(self.zoom,zoom,self.vz,dt,2.5,.065)
        x=max(0,min(max(0,world_width-self.width/self.zoom),x(self.zoom)))
        y=y(self.zoom)
        self.x,self.vx=self.damp(self.x,x,self.vx,dt,4.2,620)
        self.y,self.vy=self.damp(self.y,y,self.vy,dt,3.6,360)

    def project(self, x, y):
        return (x-self.x)*self.zoom, 720-(720-y+self.y)*self.zoom

    def focus(self, x, y, world_width, dt, zoom=1.18):
        """월드의 두 인물을 향해 이동한다. UI와 말풍선은 확대하지 않는다."""
        self.anchor,self.anchor_velocity=self.damp(self.anchor,max(0,y),self.anchor_velocity,dt,3.0,300)
        self.settle(lambda z:x-self.width/(2*z),lambda z:y-720+(720-315)/z,
                    max(.94,min(1.12,zoom)),world_width,dt)

    def follow(self, player, world_width, dt=0.0, *, snap=False, combat_wide=False):
        # 이동 방향을 조금 더 보여 주고, 낮은 점프에는 화면이 덜 흔들리게 한다.
        anchor_y = max(0, player.floor_y, player.y-130)
        if snap:
            self.anchor=anchor_y;self.anchor_velocity=self.vx=self.vy=self.vz=0
            self.look=self.look_velocity=0
        else:
            self.anchor,self.anchor_velocity=self.damp(self.anchor,anchor_y,self.anchor_velocity,dt,3.2,360)
            goal=player.facing*60 if getattr(player,'previous_direction',0) else 0
            self.look,self.look_velocity=self.damp(self.look,goal,self.look_velocity,dt,2.8,90)
        height=max(0,min(1,(self.anchor-120)/620));height=height*height*(3-2*height)
        tension=max(0,min(1,float(combat_wide)));tension=tension*tension*(3-2*tension)
        desired_zoom=min(1-.12*height,1-.08*tension)
        feet_screen=160+min(65,self.anchor*.11)
        center=self.x+self.width/(2*self.zoom)
        focus=player.x+self.look
        # 작은 좌우 전환과 점프에는 화면을 그대로 두는 여유 구간을 둔다.
        delta=focus-center
        center+=max(0,delta-80) if delta>0 else min(0,delta+80)
        if snap:
            self.zoom=desired_zoom
            self.x=max(0,min(world_width-self.width/self.zoom,player.x-self.width/(2*self.zoom)))
            self.y=self.anchor-720+(720-feet_screen)/self.zoom
        else:
            self.settle(lambda z:center-self.width/(2*z),lambda z:self.anchor-720+(720-feet_screen)/z,
                        desired_zoom,world_width,dt)


class World:
    BACKGROUND_SCALE = 1.0
    STAGE_WIDTH_SCALE = 2.0

    def __init__(self, folder, screen_width):
        self.folder = folder
        self.screen_width = screen_width
        self.stages = json.loads(
            (folder / 'asset_manifest.json').read_text(encoding='utf-8')
        )['stages']
        self.set_stage(0)

    def set_stage(self, index):
        if index == getattr(self, 'index', None):
            return
        self.index = index
        self.stage = self.stages[index]
        self.background = load_pixel_image(self.folder / self.stage['bg']['file'])
        self.ground = load_pixel_image(self.folder / self.stage['ground']['file'])
        self.width = round(self.background.w * self.STAGE_WIDTH_SCALE)
        # 지면은 확대하지 않는다. 그림의 발판 높이만 충돌 바닥 y=0에 맞춘다.
        self.ground_height = self.ground.h
        self.ground_top = self.stage['ground']['surfaceY']

    def change_stage(self, player):
        if player.x >= self.width - 96 and self.index < len(self.stages) - 1:
            self.set_stage(self.index + 1)
            player.x = 180.0
            return True
        if player.x <= 96 and self.index > 0:
            self.set_stage(self.index - 1)
            player.x = self.width - 180.0
            return True
        player.x = max(96.0, min(self.width - 96.0, player.x))
        return False

    def draw(self, camera):
        view_width,view_height=camera.width/camera.zoom,camera.height/camera.zoom
        factor=max(1.0,view_height/self.background.h)
        bg_width = round(self.background.w*factor)
        bg_height = round(self.background.h*factor)
        # 원경은 지면보다 천천히 이동한다. 양 끝에서도 빈 화면이 생기지 않는다.
        progress = max(0,min(1,camera.x/max(1,self.width-view_width)))
        bg_scroll = progress*(bg_width-view_width)
        # 그리기 좌표만 픽셀에 맞춘다. 실제 이동과 카메라 계산은 실수로 유지한다.
        # 원본 배경을 1:1로 사용한다. 점프의 세로 시차는 여분 높이 안에서만 움직인다.
        space=max(0,bg_height-view_height)
        bottom=round(720-view_height-max(0,min(space,space/2+(camera.y+160)*.04)))
        left = round(-bg_scroll)
        self.background.draw(left + bg_width / 2, bottom + bg_height / 2, bg_width, bg_height)
        bottom = round(self.ground_top - self.ground_height - camera.y)
        first = max(0, int(camera.x) // self.ground.w)
        last = min(ceil(self.width / self.ground.w),
                   ceil((camera.x + view_width) / self.ground.w))
        # 원본 픽셀 크기로 이어 붙이고, 번갈아 뒤집어 양쪽 경계를 맞춘다.
        for tile in range(first, last):
            left = round(tile * self.ground.w - camera.x)
            self.ground.composite_draw(
                0, 'h' if tile % 2 else '',
                left + self.ground.w / 2, bottom + self.ground_height / 2,
                self.ground.w, self.ground_height,
            )
