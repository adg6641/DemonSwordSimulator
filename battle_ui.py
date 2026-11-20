"""생성한 숫자 이미지와 절제된 피격 표시."""
import json
from animation import load_pixel_image
from interface import fill


class BattleArt:
    def __init__(self, assets):
        folder=assets/'ui/battle'
        self.numbers=load_pixel_image(folder/'numbers.png',smooth=True)
        self.rects=json.loads((folder/'numbers.json').read_text(encoding='utf8'))
        self.frame=load_pixel_image(folder/'hud.png',smooth=True)

    def damage(self, number, x, y, age, hurt=False):
        text=str(number).replace('-','−')
        height=24
        gap=2
        boxes=[self.rects[('hurt_' if hurt else 'hit_')+digit] for digit in text]
        widths=[height*w/h for _,_,w,h in boxes]
        x-= (sum(widths)+gap*(len(widths)-1))/2
        alpha=min(1,max(0,(.8-age)/.25))
        self.numbers.opacify(alpha)
        for rect,width in zip(boxes,widths):
            left,top,w,h=rect
            self.numbers.clip_draw(left,self.numbers.h-top-h,w,h,round(x+width/2),
                                   round(y+min(1,age/.35)*27),round(width),height)
            x+=width+gap
        self.numbers.opacify(1)

    @staticmethod
    def hurt_border(remaining):
        strength=max(0,min(1,remaining/.32))
        for inset in range(0,36,6):
            alpha=round(65*strength*(1-inset/36)**2)
            color=(156,30,47,alpha)
            fill(inset,inset,1280-inset*2,6,color)
            fill(inset,714-inset,1280-inset*2,6,color)
            fill(inset,inset+6,6,708-inset*2,color)
            fill(1274-inset,inset+6,6,708-inset*2,color)
