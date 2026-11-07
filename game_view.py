"""플레이 화면·선택창·성장창·기록책. 그림은 생성한 PNG, 글자는 선명한 글꼴로 표시한다."""
from math import sin
import pico2d.pico2d as engine
from pico2d import SDL_RenderSetScale, SDL_Rect, SDL_SetRenderDrawColor, SDL_RenderDrawRect
from interface import fill, speech_tail
from animation import load_pixel_image
from progress import Run, ENDINGS
from story import CHAPTERS, objective, choice_label
from combat import Companion

CREAM = (237, 228, 209)
MUTED = (170, 191, 187)
GOLD = (231, 194, 125)
TEAL = (151, 216, 198)
PANEL = (13, 22, 32, 246)
EDGE = (91, 111, 120, 215)
ACCENT = (208, 174, 107, 255)
BRIGHT = (246, 239, 222)

INTERACTIONS = {
    'event': ('살펴보기', 149), 'record': ('기록 읽기', 91), 'chest': ('상자 열기', 103),
    'camp': ('쉬기 · 저장', 100), 'lever': ('성문 열기', 121),
}


def panel(x, y, w, h, *, edge=EDGE, background=PANEL):
    fill(x, y, w, h, background)
    SDL_SetRenderDrawColor(engine.renderer, *edge)
    SDL_RenderDrawRect(engine.renderer, SDL_Rect(round(x),round(720-y-h),round(w),round(h)))


class CampaignView:
    def __init__(self, scene):
        self.s = scene
        self.a, self.ui = scene.assets, scene.ui
        self.wrap_cache = {}
        self.hud_icons = load_pixel_image(scene.root/'assets/ui/hud_icons.png', smooth=True)

    def icon(self, index, x, y, size=20):
        self.hud_icons.clip_draw(index*64, 0, 64, 64, round(x), round(y), size, size)

    def key(self, label, x, y, width=30, strong=False):
        panel(x, y, width, 26, edge=ACCENT if strong else EDGE,
              background=(70, 53, 29, 255) if strong else (25, 39, 50, 255))
        self.text(label, x+width/2, y+14, 15, GOLD if strong else BRIGHT, True)

    def text(self, value, x, y, size=20, color=CREAM, center=False):
        self.ui.text(str(value), x, y, size, color, center)

    def wrap(self, text, x, y, width, size=20, color=CREAM, spacing=1.55, max_lines=8):
        key = (str(text), width, size)
        lines = self.wrap_cache.get(key)
        if lines is None:
            lines = []
            for paragraph in str(text).split('\n'):
                line = ''
                for word in paragraph.split(' '):
                    trial = (line+' '+word).strip()
                    if line and self.ui.measure(trial,size)>width:
                        lines.append(line)
                        line = word
                    else:
                        line = trial
                lines.append(line)
            if len(self.wrap_cache)>350: self.wrap_cache.clear()
            self.wrap_cache[key] = lines
        for i, line in enumerate(lines[:max_lines]):
            self.text(line, x, y-i*size*spacing, size, color)
        return y-min(max_lines, len(lines))*size*spacing

    def object(self, o):
        s, a = self.s, self.a
        uid, kind = s.obj_uid(o), o['kind']
        key, age, scale, y, frame = 'adv/'+o.get('asset', ''), s.time, None, o['y'], None
        if abs(o['x']-s.camera.x-640)>1000:
            return
        if kind == 'platform':
            if s.time<o.get('disabled_until',0):return
            key = o['visual']
            scale = o['w']/a.clips[key]['frameWidth']
            if o.get('motion')=='crumble' and o.get('stepped',0)>.3:
                a.draw(key,o['x'],y,s.camera,scale,alpha=.35 if int(s.time*18)%2 else 1)
                return
        elif kind=='crystal':
            if uid in s.run.taken:return
            a.draw('v3/crystal',o['x'],y+sin(s.time*2+o['x'])*4,s.camera,.22,s.time)
            return
        elif kind=='spring':
            a.draw('v3/spring',o['x'],y,s.camera,.45,s.time)
            return
        elif kind in {'crate', 'barrier', 'pillar'}:
            scale = .43 if kind == 'crate' else .62 if kind == 'pillar' else .5
            if uid in s.run.broken:
                age = s.time-o.get('broken_time', -100)
            else:
                frame = 0
        elif kind == 'chest':
            scale = .43
            if uid in s.run.taken:
                age = s.time-o.get('opened', -100)
            else:
                frame = 0
        elif kind == 'gate':
            scale = 1
            if s.run.has('gate_open'):
                age = s.time-o.get('opened', -100)
            else:
                frame = 0
        elif kind == 'camp':
            scale = .38
        elif kind == 'cover':
            scale = o['w']/a.clips[key]['frameWidth']
        elif kind == 'crawl':
            key='v3/vine_tunnel'
            scale=None
        elif kind == 'record':
            if o['record'] in s.run.records:
                a.draw(key, o['x'], y, s.camera, age=age, alpha=.4)
                return
        elif kind == 'hazard':
            # 낙석 본체는 공격 경고 후에만 나타난다.
            return
        elif kind == 'lever':
            key = 'adv/story_props__switch_down' if s.run.has('gate_open') else key
        if kind == 'event':
            event = o['event']
            if o.get('npc'):
                override = s.actor_actions.get(o['id'])
                if override:
                    key, started = override
                    a.draw(key, o['x'], 0, s.camera, .72, s.time-started)
                else:
                    # 제자리에 서 있는 NPC에게 이동용 시트를 재생하지 않는다.
                    facing = 1 if s.player.x>o['x'] else -1
                    a.draw('adv/'+o['npc']+'__idle', o['x'], 0, s.camera, .72, s.time, facing)
                return
            if event == 'rescue':
                a.draw(key, o['x'], 0, s.camera, .62, age)
                if not s.run.companion:
                    a.draw('adv/lunea_rescue__lunea_trapped', o['x']+35, 0, s.camera, Companion.SCALE, age)
                    for i, name in enumerate(['crescent', 'star', 'circle']):
                        a.draw('adv/seal_knots__'+name+('_active' if int(age*1.2)%3==i else '_dormant'), o['x']-90+i*90, 10, s.camera, .16)
                    if s.run.has('aid_marker'):
                        a.draw('adv/seal_knots__aid_mark', o['x']-160, 0, s.camera, .3)
                return
            if event == 'merchant':
                key = 'adv/merchant_cart__cart_repaired' if s.run.has('merchant_done') and not s.run.has('ward_taken') else key
                a.draw(key, o['x'], 0, s.camera, .55)
                override = s.actor_actions.get('merchant')
                if override:
                    a.draw(override[0], o['x']+190, 0, s.camera, .72, s.time-override[1])
                elif s.run.has('merchant_done') and not s.run.has('ward_taken'):
                    a.draw('adv/npc_merchant__idle', o['x']+190, 0, s.camera, .72, age)
                    if s.run.trust:
                        a.draw('adv/merchant_cart__cart_supplies', o['x']-440, 0, s.camera, .35)
                else:
                    a.draw('adv/merchant_event__merchant_injured', o['x']+190, 0, s.camera, .72, frame=7)
                a.draw('adv/story_props__ward_cracked' if s.run.has('ward_taken') else 'adv/story_props__ward_whole', o['x']+30, 90, s.camera, .18)
                return
            if event == 'altar' and s.run.has('altar_purified'):
                key = 'adv/altar_states__altar_purified'
            if event == 'memory':
                key = 'adv/story_props__charm_cracked' if s.run.fracture else 'adv/story_props__charm_restored' if 'memory' in s.run.pacts else 'adv/story_props__charm_whole'
                y = 70
                if not s.run.companion:
                    key = 'adv/seal_knots__moon_path'
            if event == 'side_seal' and s.run.has('side_seal_open'):
                key = 'adv/story_props__seal_cover_open'
        if key in a.clips:
            a.draw(key, o['x'], y, s.camera, scale, age, frame=frame)
        if kind == 'gate':
            a.draw('adv/story_props__chain_broken' if s.run.has('gate_open') else 'adv/story_props__chain_anchor', o['x']-130, 160, s.camera, .45)

    def world(self):
        s = self.s
        s.world.draw(s.camera)
        # 발판 뒤의 받침 구조는 원경과 인물 사이 깊이에 놓는다.
        for x in ((1700,2710) if s.run.stage<7 else ()):
            if abs(x-s.camera.x-640)<1100:
                s.assets.draw('v3/support_wood' if s.run.stage<3 else 'v3/support_stone',x,0,s.camera,alpha=.78)
        for o in s.objects:
            self.object(o)
        # 장식의 위치는 화면이 아니라 월드에 고정한다.
        for x in (510, 1770, 2930):
            if abs(x-s.camera.x-640)<820:
                if s.run.stage<3:
                    s.assets.draw('adv/grass_dust__grass_sway', x, 0, s.camera, .23, s.time+x*.001)
                s.assets.draw('adv/leaves_fireflies__fireflies', x+170, 200, s.camera, .35, s.time+x*.003, alpha=.3)
        for e in s.enemies:
            if abs(e.x-s.camera.x-640) < 980:
                e.draw(s)
                if e.alive and not e.boss and e.hp < e.max_hp:
                    x, y = e.x-s.camera.x, e.y-s.camera.y+155
                    fill(x-40, y, 80, 5, (15, 24, 27, 220))
                    fill(x-40, y, 80*e.hp/e.max_hp, 5, (170, 97, 102, 255))
        visual = s.modal.get('visual') if s.modal else None
        if visual == 'camp':
            age=s.camp_age
            hx,lx,y,facing=s.modal['camp_seats']
            t=min(1,age/.36)
            t=t*t*(3-2*t)
            s.player.animation.draw(s.player.x+(hx-s.player.x)*t,y,facing,s.camera)
            if s.companion:
                key='adv/lunea_camp__lunea_sit_down'
                s.assets.draw(key, lx, y, s.camera, Companion.SCALE, age, -facing)
        else:
            if s.companion:
                if visual == 'memory':
                    s.assets.draw('adv/lunea_ritual__lunea_memory_ritual', s.companion.x, s.companion.y, s.camera, Companion.SCALE, s.interaction_age)
                else:
                    s.companion.draw(s)
            if not (s.player.invulnerable>.05 and int(s.time*16)%2 and s.player.mode not in {'hurt', 'dead'}):
                s.player.draw(s.camera)
            if s.player.mode=='free' and s.player.previous_direction and s.player.grounded:
                s.assets.draw('adv/grass_dust__foot_dust', s.player.x-25*s.player.facing, s.player.y, s.camera, .18, s.time)
        for shot in s.shots:
            s.assets.draw(shot.key, shot.x, shot.y, s.camera, .25 if 'night_orb' not in shot.key else .38, shot.age, -1 if shot.vx<0 else 1)
        for hazard in s.hazards:
            if hazard['age'] < hazard['wait']:
                s.assets.draw('adv/seal_warning__seal_telegraph', hazard['x'], 0, s.camera, .6, hazard['age'])
            if hazard['kind'] == 'rock' and hazard['age']>=hazard['wait']:
                age = hazard['age']-hazard['wait']
                s.assets.draw('adv/falling_stone__stone_fall' if age<.5 else 'adv/falling_stone__stone_impact', hazard['x'], 0, s.camera, .55, age if age<.5 else age-.5)
        for b in s.bursts:
            s.assets.draw(b['key'], b['x'], b['y'], s.camera, b['scale'], b['age'])
        for n in s.numbers:
            self.text(n['text'], n['x']-s.camera.x, n['y']-s.camera.y+n['age']*65, 23, (241, 131, 136) if n['hurt'] else GOLD, True)

    def title_image(self, name, x, y, width=360, alpha=1):
        key = 'polish/title_'+name
        if key in self.a.clips:
            c = self.a.clips[key]
            # 작은 제목을 무리하게 늘리지 않는다.
            self.a.fit(key, x, y, min(width, c['width']*1.2), 90, alpha=alpha)

    def meter(self, x, y, w, label, value, maximum, color, icon):
        self.icon(icon,x+9,y+9,17)
        self.text(label,x+23,y+10,14,MUTED)
        bx=x+51
        fill(bx,y,w-51,18,(28,39,49,255))
        width=(w-51)*max(0,min(1,value/max(1,maximum)))
        fill(bx,y,width,18,color)
        if width>1:
            fill(bx,y+16,width,2,tuple(min(255,c+36) for c in color[:3])+(255,))
        self.text(f'{max(0,int(value))} / {maximum}',bx+(w-51)/2,y+9,14,BRIGHT,True)

    def hud(self):
        s,r,p=self.s,self.s.run,self.s.player
        panel(24,578,310,118)
        fill(25,693,308,2,ACCENT)
        panel(37,613,58,62, background=(22,35,47,255))
        self.a.fit('adv/portrait_hero__hero_focus',66,645,51,56)
        self.text(f'레벨 {r.level}',108,675,22,BRIGHT)
        path={'physical':'물리 특화','magic':'마력 특화','balance':'균형 성장'}.get(r.path,'마검사')
        self.text(path,216,675,15,GOLD)
        self.meter(108,639,210,'HP',p.hp,r.max_hp,(154,62,77,255),0)
        self.meter(108,614,210,'MP',s.mp,r.max_mp,(47,106,148,255),1)
        self.icon(2,47,597,16)
        self.text('경험치',61,597,13,MUTED)
        fill(108,593,210,7,(32,43,50,255))
        fill(108,593,210*min(1,r.xp/max(1,r.xp_needed)),7,(200,158,83,255))

        goal,gx=objective(s)
        panel(824,603,432,93)
        fill(825,693,430,2,ACCENT)
        self.icon(3,847,673,25)
        self.text(f'{r.stage+1:02d}장  {CHAPTERS[r.stage]}',871,672,18,GOLD)
        direction='→' if gx>p.x+80 else '←' if gx<p.x-80 else '◆'
        self.text(direction,849,639,22,GOLD,True)
        self.wrap(goal,871,640,365,20,BRIGHT,1.2,2)

        panel(24,22,420,62)
        actions=[('C','연속 베기',True),('Shift','대시 베기',r.skills.get('dash',0)>0),('Z','마검파',r.skills.get('wave',0)>0)]
        for i,(key,name,ready) in enumerate(actions):
            x=36+136*i
            if i:
                fill(x-8,34,1,37,(73,93,105,210))
            self.key(key,x,48,47 if i==1 else 30,strong=bool(ready))
            self.text(name,x+10,35,15,BRIGHT if ready else MUTED)
            if i:
                self.text(('끝에 C' if i==1 else '이후 C') if ready else '잠김',x+53,61,13,MUTED)
        panel(454,22,281 if s.companion else 129,62)
        self.key('H',464,39)
        self.text(f'회복 {r.shards}',499,52,16,BRIGHT)
        if s.companion:
            self.icon(5,604,52,20)
            cooldown=s.companion.cooldown
            self.text(f'Q  달빛 · {cooldown:.0f}초' if cooldown>0 else 'Q  달빛 준비',621,52,16,TEAL)
        if p.effects.buff_remaining>0:
            panel(562,84,156,30,edge=ACCENT)
            self.text(f'마검파 {p.effects.buff_remaining:.1f}초',640,99,15,TEAL,True)
        panel(1003,22,253,62)
        self.icon(4,1028,60,20)
        self.text('Tab 기록  ·  Esc 메뉴',1047,60,15,BRIGHT)
        if r.unspent or r.skill_points:
            panel(24,535,255,33,edge=ACCENT)
            self.text(f'L  성장 포인트 {r.unspent+r.skill_points}',37,552,16,GOLD)
        else:
            self.text('L 성장',1020,37,14,MUTED)
        hint = ('↓ + ↑   발판 아래로' if p.floor_y>0 else
                '↑   도약 문양 위에서 높이 점프' if any(o['kind']=='spring' and abs(o['x']-p.x)<110 for o in s.objects) else
                '↓   웅크려 지나가기' if any(o['kind']=='crawl' and abs(o['x']-p.x)<210 and p.y<o.get('roof',154) for o in s.objects)
                else '')
        if hint:
            panel(508,76,264,34)
            self.text(hint,640,93,16,BRIGHT,True)
        boss=next((e for e in s.enemies if e.boss and e.alive and abs(e.x-p.x)<900),None)
        if boss:
            panel(383,619,414,65,edge=(167,102,105,235))
            self.text(boss.actor['name'],590,665,20,GOLD,True)
            fill(401,638,378,11,(47,32,41,255))
            fill(401,638,378*max(0,boss.hp)/boss.max_hp,11,(180,73,91,255))
            if boss.state=='windup':
                self.text('공격 준비  ·  피하거나 막으세요',590,606,16,(255,187,156),True)
        self.interaction_markers(gx)
        if s.developer:
            self.text('연습 모드 · F9',1123,582,14,GOLD)

    def interaction_markers(self, goal_x):
        s,p,r=self.s,self.s.player,self.s.run
        near=s.nearest()
        for obj in s.objects:
            kind=obj['kind']
            if kind not in INTERACTIONS:
                continue
            if kind=='record' and obj['record'] in r.records or kind=='chest' and s.obj_uid(obj) in r.taken:
                continue
            if kind=='lever' and r.has('gate_open'):
                continue
            if kind=='event' and obj.get('event')=='rescue' and r.has('rescue_done'):
                continue
            label,height=INTERACTIONS[kind]
            if kind=='event' and obj.get('npc'):
                label='이야기하기'
            x,y=s.camera.project(obj['x'],obj['y']+height)
            if not 22<x<1258 or not 123<y<540:
                continue
            active=obj is near and p.grounded
            quest=abs(goal_x-obj['x'])<42
            hue=ACCENT if active or quest else (138,198,203,240)
            if active:
                card_x=max(22,min(1080,x-89))
                panel(card_x,y+19,176,40,edge=hue)
                self.key('E',card_x+8,y+26,30,strong=True)
                self.text(label,card_x+49,y+39,16,BRIGHT)
                fill(x-1,y+6,2,13,hue)
                # Target brackets pick the object out from the scenery at close range.
                left,right=x-29,x+29
                for px in (left,right):
                    fill(px,y-11,2,15,hue)
                fill(left,y+3,10,2,hue)
                fill(right-8,y+3,10,2,hue)
            else:
                bob=2*sin(s.time*2.6+obj['x']*.004)
                panel(x-13,y+bob-13,26,26,edge=hue)
                self.icon(3 if quest else 4 if kind=='record' else 2,x,y+bob,20)

    def story_dialogue(self):
        s,m=self.s,self.s.modal
        sx,sy=s.camera.project(m['speaker_x'],m['speaker_y'])
        show=min(1,s.interaction_age/.18)
        visible=m['text'] if m.get('revealed') else m['text'][:int(s.interaction_age*43)]
        camp=m.get('visual')=='camp'
        top=646 if m.get('cine') or camp else 663
        width=658 if camp else 730
        left=round(max(24,min(1256-width,sx-width/2))) if not m.get('cine') else (1280-width)//2
        if m['kind']=='boss' and m['speaker']=='바르켄':
            left=24
        panel(left,top-133,width,133,background=(13,22,32,round(248*show)))
        fill(left+1,top-3,width-2,2,ACCENT)
        self.text(m['speaker'],left+23,top-29,22,GOLD)
        self.wrap(visible,left+23,top-59,width-46,20,BRIGHT,1.27,3)
        if not m.get('cine') and not camp:
            tip=max(left+18,min(left+width-18,sx))
            if sy<top-149:
                speech_tail((tip-9,top-133),(tip+9,top-133),(tip,top-146))
        panel(24,16,1232,198,edge=EDGE,background=(12,21,31,248))
        self.icon(3,52,187,21)
        self.text(m['title'],72,187,22,BRIGHT)
        if m.get('emphasis'):
            self.title_image(m['emphasis'],1090,182,224)
        self.options(m,compact=True)
        self.text('↑ ↓ 선택   ·   Enter 확인   ·   마우스 클릭',640,29,14,MUTED,True)

    def options(self,m,compact=False):
        s=self.s
        start=s.selected//4*4
        for row,i in enumerate(range(start,min(start+4,len(m['options'])))):
            option=m['options'][i]
            disabled=len(option)>2 and bool(option[2])
            if compact:
                left,bottom,w,h=44+(row%2)*604,102-(row//2)*55,588,45
            else:
                left,bottom,w,h=105,312-row*62,1070,53
            selected=i==s.selected
            panel(left,bottom,w,h,edge=ACCENT if selected else EDGE,
                  background=(36,45,50,255) if selected else (17,30,42,255))
            color=(120,133,136) if disabled else GOLD if selected else CREAM
            icon=option[3] if len(option)>3 else None
            if icon and not compact:
                self.a.fit('adv/'+icon,left+30,bottom+27,30,30)
            self.wrap(f'{row+1:02d}   '+option[0],left+(58 if icon and not compact else 17),bottom+(31 if compact else 33),w-50,17 if compact else 18,color,1.05,2)
            s.hitboxes.append((left,bottom,w,h,i))
        if len(m['options'])>4:
            self.text(f'{start//4+1}/{(len(m["options"])+3)//4}  ↓ 다음 선택지',1050,180 if compact else 87,14,MUTED)

    def banner(self):
        b=self.s.banner
        if not b: return
        age,left=b['age'],b['duration']-b['age']
        alpha=min(1,age/.3,left/.45)
        y=530+10*(1-min(1,age/.4))
        panel(395,y-45,490,102,edge=(208,174,107,round(225*alpha)),
              background=(13,22,32,round(235*alpha)))
        self.title_image(b['image'],640,y+13,366,alpha)
        self.text(b['subtitle'],640,y-30,17,BRIGHT,True)

    def cinematic(self):
        s=self.s
        cine=s.modal.get('cine') if s.modal else s.cine_out
        if not cine:return
        age=s.interaction_age if s.modal else cine['age']
        alpha=1 if s.modal else max(0,1-age/.6)
        t=min(1,age/5);t=t*t*(3-2*t)
        start,end=cine.get('zoom',(1,1.05));z=start+(end-start)*t
        dx=cine.get('pan',(1-t)*10)
        if cine.get('shake') and age<.5:dx+=sin(age*56)*(1-age/.5)*7
        key='v3/rescue_'+cine['image']
        if s.modal and cine.get('previous'):
            self.a.cover('v3/rescue_'+cine['previous'],640+cine.get('previous_pan',0),360,1280,720,zoom=cine.get('previous_zoom',start))
            alpha=min(1,age/.4)
        self.a.cover(key,640+dx,360,1280,720,zoom=max(1,z),alpha=alpha)
        fill(0,696,1280,24,(3,7,14,230))
        if cine.get('fx') and s.modal:
            fx_x,fx_y=(710,450) if cine['image']=='pull' else (890,445)
            self.a.draw('v3/rescue_glow',fx_x,fx_y,None,.55,s.interaction_age,alpha=.25+.15*sin(age*2)**2)
            if cine['fx']=='break' and age<1.3:
                self.a.draw('v3/rescue_break',fx_x,fx_y,None,.85,age,alpha=max(0,1-age/1.3))

    def modal(self):
        s, m = self.s, self.s.modal
        if m['kind'] in {'dialogue','boss','final'}:
            self.story_dialogue()
            return
        if m['kind'] == 'journal':
            self.journal()
            return
        fill(0, 0, 1280, 720, (4, 10, 16, 185))
        panel(48,58,1184,618,edge=ACCENT)
        fill(72,610,1136,1,EDGE)
        if m['kind']=='path': self.title_image('growth',640,638,320)
        else: self.text(m['title'], 640, 638, 30, GOLD, True)
        if m['kind'] == 'path':
            self.wrap(m['text'], 100, 585, 1080, 19, MUTED, 1.45, 3)
            for i, path in enumerate(['physical', 'magic', 'balance']):
                left, bottom = 108+i*365, 115
                self.a.panel('adv/ui_controls__choice_focus' if i == s.selected else 'adv/ui_controls__choice_normal', left, bottom, 335, 350)
                self.a.fit('adv/growth_cards__path_'+path, left+168, 340, 290, 180)
                self.text(m['options'][i][0], left+168, 215, 27, (49, 38, 27), True)
                tips = ['검을 들고 파고드는 강한 근접 공격', '멀리 있는 적에게 검기를 발사', '대시 베기와 마검파를 함께 사용']
                self.wrap(tips[i], left+30, 170, 275, 17, (69, 54, 35), 1.4, 2)
                s.hitboxes.append((left, bottom, 335, 350, i))
        else:
            if m.get('portrait'):
                self.a.fit('adv/'+m['portrait'], 196, 493, 230, 224)
                text_x, width = 342, 820
            else:
                text_x, width = 104, 1070
            self.wrap(m['text'], text_x, 576, width, 20, CREAM, 1.55, 5)
            self.options(m)
        self.text('방향키 선택  ·  Enter 확인  ·  클릭 가능  ·  선택 중 전투 정지', 640, 37, 16, MUTED, True)

    def journal(self):
        s, r = self.s, self.s.run
        fill(0, 0, 1280, 720, (5, 12, 18, 235))
        panel(30,65,1220,625,edge=ACCENT)
        labels = ['현재 모험', '세계선 비교', '아홉 결말', '이미지 도감']
        for i, label in enumerate(labels):
            self.a.panel('adv/ui_controls__tab_active' if i==s.journal_page else 'adv/ui_controls__tab_normal', 80+i*286, 620, 260, 48)
            self.text(label, 210+i*286, 645, 21, (51, 38, 28) if i==s.journal_page else CREAM, True)
        if s.journal_page == 0:
            self.text('나의 성장',105,560,26,GOLD)
            self.text('이야기의 흔적',690,560,26,TEAL)
            left=[f'레벨 {r.level} · 검기 {r.tier}단계',f'공격력 {r.attack}     마력 {r.magic}',
                  f'최대 HP {r.max_hp}     최대 MP {r.max_mp}',
                  f'남은 능력치 {r.unspent}점 · 기술 {r.skill_points}점',
                  f'배분한 능력치: 공격 {r.spent["attack"]} · 마력 {r.spent["magic"]}',
                  f'생존 {r.spent["vitality"]} · 집중 {r.spent["focus"]}']
            right=[f'마을 신뢰 {r.trust}/2 · 어둠의 침식 {r.erosion}/3',
                   '기록: '+ '  '.join(('●' if key in r.records else '○')+name for key,name in [('night','밤'),('moon','달'),('return','귀환')]),
                   '루네아와 동행' if r.companion else '혼자 떠나는 세계선',
                   ('부적에 균열이 남아 있음' if r.fracture else '부적 온전함') if r.companion else '거울 숲에서 소녀를 구할 수 있음',
                   '함께 나눈 약속: '+str(len(r.pacts))+'/3',
                   ' · '.join({'secret':'비밀','memory':'기억','plan':'계획'}[k] for k in r.pacts) or '쉼터에서 이야기를 나눠 보자']
            for x,rows in [(105,left),(690,right)]:
                for i,line in enumerate(rows): self.wrap(line,x,509-i*37,490,19,MUTED,1.3,1)
            self.text('경계를 완전히 되돌리려면',105,286,20,GOLD)
            self.wrap('준비 완료. 왕좌에서 경계 복원을 선택할 수 있다.' if not r.missing_restore() else '아직 필요한 것: '+', '.join(r.missing_restore()),105,250,1060,18,MUTED,1.35,2)
            self.text('최근의 선택',105,197,18,GOLD)
            self.wrap('  →  '.join(choice_label(e,v) for e,v in r.choices[-2:]) or '이제 첫 이야기를 써 내려갈 차례다.',105,167,1050,16,MUTED,1.2,1)
        elif s.journal_page == 1:
            histories = [h for h in s.store.history if h.get('seed') != r.seed]
            past = Run.from_dict(histories[s.history_index%len(histories)]) if histories else None
            self.a.fit('adv/ui_panels__record_book', 640, 355, 1130, 495)
            for x, label, run in [(320, '이전 세계선', past), (700, '이번 세계선', r)]:
                ink = (55, 40, 25)
                self.text(label, x, 525, 26, ink)
                if run:
                    values = [f'Lv.{run.level} · '+{'physical':'물리', 'magic':'마법', 'balance':'균형', '':'기본'}[run.path],
                              f'공격 {run.attack} / 마력 {run.magic}', f'처치 {run.kills} / 피격 {run.hits}',
                              f'신뢰 {run.trust} · 침식 {run.erosion}', '루네아 동반' if run.companion else '단독 여행',
                              ENDINGS[run.ending][0] if run.ending else '아직 쓰는 이야기']
                    for i, value in enumerate(values):
                        self.text(value, x-15, 470-i*45, 18, ink)
                else:
                    self.wrap('완결한 세계선이 생기면 이곳에서 비교할 수 있다.', x, 465, 240, 19, ink)
            self.text('↑ ↓ 이전 기록 바꾸기 · 종료 엔딩과 선택 이력을 로컬 파일에 보관', 640, 91, 16, MUTED, True)
        elif s.journal_page == 2:
            known = {h.get('ending') for h in s.store.history}
            for i, (ending, (title, story)) in enumerate(ENDINGS.items()):
                x, y = 105+(i%3)*390, 450-(i//3)*152
                unlocked = ending in known
                self.a.panel('adv/ui_controls__choice_selected' if unlocked else 'adv/ui_controls__choice_disabled', x, y-70, 350, 130)
                self.a.fit('adv/ending_badges__'+(ending if unlocked else 'locked_ending'), x+65, y-5, 80, 80)
                self.text(ending+' · '+('동반' if ending.startswith('D') else '단독' if ending.startswith('S') else '히든'), x+120, y+20, 17, (53, 41, 27))
                self.wrap(title if unlocked else '아직 펼치지 않은 결말', x+120, y-13, 205, 16, (68, 54, 38), 1.4, 2)
            self.text('진엔딩 6 · 배드 엔딩 2 · 히든 엔딩 1 / HP 0 재도전은 결말 수에 포함하지 않는다.', 640, 91, 15, MUTED, True)
        else:
            known_hidden = any(h.get('ending') == 'H1' for h in s.store.history)
            gallery = [(key, c) for key, c in self.a.clips.items() if key.startswith('adv/') and (not c.get('spoiler') or known_hidden)]
            key, clip = gallery[s.gallery_index%len(gallery)]
            self.text(clip['label'], 640, 565, 25, GOLD, True)
            f = self.a.frame(key, s.time)
            self.a.fit(key, 640, 345, 950, 335, frame=f)
            self.text(f'{clip["frameCount"]}프레임 · {clip["group"]}', 640, 140, 17, MUTED, True)
            self.text(f'{s.gallery_index%len(gallery)+1} / {len(gallery)}  ·  ↑ ↓ 또는 Q / E로 이미지 바꾸기', 640, 105, 16, MUTED, True)
        self.text('← → 책갈피 이동   ·   Tab / Esc 닫기', 640, 33, 17, MUTED, True)

    def ending(self):
        s, ending, age = self.s, self.s.run.ending, self.s.finished_age
        fill(0, 0, 1280, 720, (4, 6, 12, 255))
        if ending == 'H1' and age < 10:
            key = 'hidden_reveal__hidden_reveal' if age<3 else 'hidden_grab__hidden_grab' if age<6 else 'hidden_dissolve__hidden_dissolve'
            segment = age if age<3 else age-3 if age<6 else age-6
            c = self.a.clips['adv/'+key]
            frame = min(c['frameCount']-1, int(segment/(4 if age>=6 else 3)*c['frameCount']))
            self.a.draw('adv/'+key, 690, 115, None, 1, frame=frame)
            if age>5:
                self.text('너의 그 선택들에 대해 후회하지 않을 자신이 있냐?', 640, 70, 23, MUTED, True)
        else:
            key = 'adv/'+self.a.endings[ending]['asset']
            self.a.fit(key, 640, 380, 1280, 680)
            fill(0, 0, 1280, 180, (4, 9, 15, 220))
            image='ending_5' if ending=='H1' else 'ending_'+ending[-1]
            self.title_image(image,640,133,600)
            self.wrap(ENDINGS[ending][1], 170, 81, 960, 18, CREAM, 1.4, 3)

    def draw(self):
        s = self.s
        s.hitboxes = []
        if s.run.ending:
            self.ending()
        else:
            SDL_RenderSetScale(engine.renderer, s.camera.zoom, s.camera.zoom)
            try:
                self.world()
            finally:
                SDL_RenderSetScale(engine.renderer, 1, 1)
            self.cinematic()
            if not s.modal:
                self.hud()
                self.banner()
        if s.player.hp <= 0 and not s.run.ending:
            fill(0, 0, 1280, 720, (3, 6, 15, min(230, int(s.death_age*190))))
            self.a.draw('adv/failure_respawn__failure_vision', 640, 250, None, 1.2, s.death_age)
            self.title_image('failure',640,430,600)
            self.text('마지막 저장 지점에서 다시 시작합니다.  ·  Enter 건너뛰기', 640, 356, 20, MUTED, True)
        if s.modal:
            self.modal()
        if s.toast_time > 0:
            bottom = 214 if s.modal and s.modal['kind'] in {'dialogue','boss','final'} else 366 if s.modal else 200
            panel(300,bottom,680,51,edge=ACCENT)
            self.wrap(s.toast, 320, bottom+33, 640, 16, GOLD, 1.2, 2)
