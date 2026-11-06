"""직전 화면을 GPU에 보관해 메뉴·대화·지역 변경을 짧게 교차 전환한다."""
import pico2d.pico2d as engine
from pico2d import (SDL_CreateTexture,SDL_DestroyTexture,SDL_SetRenderTarget,
    SDL_RenderCopy,SDL_SetTextureAlphaMod,SDL_SetTextureBlendMode,SDL_BLENDMODE_BLEND,
    SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,SDL_SetRenderDrawColor,SDL_RenderClear)

class FrameBlend:
    def __init__(self):
        self.textures=[];self.key=None;self.age=1;self.duration=.4;self.available=True

    def update(self,dt):self.age+=dt

    def draw(self,draw,key):
        if not self.available:
            draw();return
        if not self.textures:
            for _ in range(3):
                tex=SDL_CreateTexture(engine.renderer,SDL_PIXELFORMAT_RGBA8888,SDL_TEXTUREACCESS_TARGET,1280,720)
                if not tex:
                    self.close();self.available=False;draw();return
                SDL_SetTextureBlendMode(tex,SDL_BLENDMODE_BLEND);self.textures.append(tex)
        if key!=self.key:
            if self.key is not None:
                # 빠르게 다음 대화를 열어도 바로 전의 '합쳐진 화면'에서 이어진다.
                SDL_SetRenderTarget(engine.renderer,self.textures[1])
                SDL_RenderCopy(engine.renderer,self.textures[2],None,None)
                self.age=0
                self.duration=.65 if key[:3]!=self.key[:3] else .34
            self.key=key
        SDL_SetRenderTarget(engine.renderer,self.textures[0])
        SDL_SetRenderDrawColor(engine.renderer,4,8,14,255);SDL_RenderClear(engine.renderer)
        try:draw()
        finally:SDL_SetRenderTarget(engine.renderer,None)
        SDL_SetRenderTarget(engine.renderer,self.textures[2])
        SDL_RenderCopy(engine.renderer,self.textures[0],None,None)
        if self.age<self.duration:
            t=self.age/self.duration;t=t*t*(3-2*t)
            previous=self.textures[1]
            SDL_SetTextureAlphaMod(previous,round(255*(1-t)))
            SDL_RenderCopy(engine.renderer,previous,None,None)
            SDL_SetTextureAlphaMod(previous,255)
        SDL_SetRenderTarget(engine.renderer,None)
        SDL_RenderCopy(engine.renderer,self.textures[2],None,None)

    def close(self):
        for tex in self.textures:SDL_DestroyTexture(tex)
        self.textures=[]
