"""플레이 화면·선택창·성장창·기록책. 그림은 생성한 PNG, 글자는 선명한 글꼴로 표시한다."""
from math import atan2, hypot, sin
import pico2d.pico2d as engine
from pico2d import SDL_RenderSetScale, SDL_Rect, SDL_SetRenderDrawColor, SDL_RenderDrawRect
from interface import fill
from animation import draw_region, load_pixel_image
from progress import Run, ENDINGS
from story import CHAPTERS, objective, choice_label
from combat import Companion
from campaign_data import BACKDROP_SUPPORTS

CREAM = (237, 228, 209)
MUTED = (170, 191, 187)
GOLD = (231, 194, 125)
TEAL = (151, 216, 198)
PANEL = (13, 22, 32, 174)
EDGE = (91, 111, 120, 164)
ACCENT = (208, 174, 107, 222)
BRIGHT = (246, 239, 222)

INTERACTIONS = {
    'event': ('살펴보기', 149), 'record': ('기록 읽기', 91), 'chest': ('상자 열기', 103),
    'camp': ('쉬기 · 저장', 100), 'lever': ('성문 열기', 121), 'door': ('문으로 들어가기', 304),
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
        self.guide_arrow = self.a.image(self.a.clips['polish/route_pointer']['path'])

    def icon(self, index, x, y, size=20):
        self.hud_icons.clip_draw(index*64, 0, 64, 64, round(x), round(y), size, size)

    def key(self, label, x, y, width=30, strong=False):
        panel(x, y, width, 26, edge=ACCENT if strong else EDGE,
              background=(70, 53, 29, 205) if strong else (25, 39, 50, 184))
        self.text(label, x+width/2, y+14, 15, GOLD if strong else BRIGHT, True)

    def text(self, value, x, y, size=20, color=CREAM, center=False):
        self.ui.text(str(value), x, y, size, color, center)

    def text_lines(self, text, width, size):
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
        return lines

    def wrap(self, text, x, y, width, size=20, color=CREAM, spacing=1.55, max_lines=8):
        lines=self.text_lines(text,width,size)
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
            key=f'polish/crawl_{s.run.stage+1}'
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
                    a.draw(key, o['x'], y, s.camera, .72, s.time-started)
                else:
                    # 제자리에 서 있는 NPC에게 이동용 시트를 재생하지 않는다.
                    facing = 1 if s.player.x>o['x'] else -1
                    a.draw('adv/'+o['npc']+'__idle', o['x'], y, s.camera, .72, s.time, facing)
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
                actor_x = o['actor_x']
                facing = 1 if s.player.x > actor_x else -1
                override = s.actor_actions.get('merchant')
                if override:
                    a.draw(override[0], actor_x, y, s.camera, .72, s.time-override[1], facing)
                elif s.run.has('merchant_done') and not s.run.has('ward_taken'):
                    a.draw('adv/npc_merchant__idle', actor_x, y, s.camera, .72, age, facing)
                    if s.run.trust:
                        a.draw('adv/merchant_cart__cart_supplies', o['x']-440, 0, s.camera, .35)
                else:
                    a.draw('adv/merchant_event__merchant_injured', actor_x, y, s.camera, .72, facing=facing, frame=7)
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
        if s.region=='explore':
            key=f'polish/stage_support_{s.run.stage+1}'
            for x,y,height in BACKDROP_SUPPORTS[s.run.stage]:
                if abs(x-s.camera.x-640)<1050:
                    s.assets.draw(key,x,y,s.camera,height/s.assets.clips[key]['height'],alpha=.64)
        # 발판은 인물과 그 위의 보상보다 먼저 그린다.
        for o in s.objects:
            if o['kind'] in {'platform','crawl','decor'}:
                self.object(o)
            elif o['kind']=='door':
                s.assets.draw('polish/door_shadow',o['x'],o['y'],s.camera,.65)
        # 장식의 위치는 화면이 아니라 월드에 고정한다.
        for x in (510, 1770, 2930) if s.region=='explore' else ():
            if abs(x-s.camera.x-640)<820:
                if s.run.stage<3:
                    s.assets.draw('adv/grass_dust__grass_sway', x, 0, s.camera, .23, s.time+x*.001)
                s.assets.draw('adv/leaves_fireflies__fireflies', x+170, 200, s.camera, .35, s.time+x*.003, alpha=.3)
        for o in s.objects:
            if o['kind'] not in {'platform','crawl','decor','door'}:
                self.object(o)
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
            if s.door_entry:
                t=min(1,s.door_entry['age']/.62)
                if t<.94:
                    p=s.player
                    depth=max(0,(t-.35)/.59)
                    p.animation.draw(p.x,p.y+22*depth,p.facing,s.camera,1-.46*depth)
            elif not (s.player.invulnerable>.05 and int(s.time*16)%2 and s.player.mode not in {'hurt', 'dead'}):
                s.player.draw(s.camera)
            if s.player.mode=='free' and s.player.previous_direction and s.player.grounded:
                s.assets.draw('adv/grass_dust__foot_dust', s.player.x-25*s.player.facing, s.player.y, s.camera, .18, s.time)
        for shot in s.shots:
            s.assets.draw(shot.key, shot.x, shot.y, s.camera, .25 if 'night_orb' not in shot.key else .38, shot.age, -1 if shot.vx<0 else 1)
        for hazard in s.hazards:
            if hazard['age'] < hazard['wait']:
                s.assets.draw('adv/seal_warning__seal_telegraph', hazard['x'], hazard['y'], s.camera, .6, hazard['age'])
            if hazard['kind'] == 'rock' and hazard['age']>=hazard['wait']:
                age = hazard['age']-hazard['wait']
                s.assets.draw('adv/falling_stone__stone_fall' if age<.5 else 'adv/falling_stone__stone_impact', hazard['x'], 0, s.camera, .55, age if age<.5 else age-.5)
        for b in s.bursts:
            s.assets.draw(b['key'], b['x'], b['y'], s.camera, b['scale'], b['age'])
        for n in s.numbers:
            self.text(n['text'], n['x']-s.camera.x, n['y']-s.camera.y+n['age']*65, 23, (241, 131, 136) if n['hurt'] else GOLD, True)
        for o in s.objects:
            if o['kind']=='door':
                s.assets.draw('adv/gate_open__gate_open',o['x'],o['y'],s.camera,.65,
                              max(0,s.time-o.get('opened',s.time-99)),frame=None if s.door_ready(o) else 0)

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

        goal,gx,gy=objective(s)
        boss=next((e for e in s.enemies if e.boss and e.alive),None)
        if s.region=='boss' and boss:
            panel(383,619,414,65,edge=(167,102,105,195))
            self.text(boss.actor['name'],590,665,20,GOLD,True)
            fill(401,638,378,11,(47,32,41,230))
            fill(401,638,378*max(0,boss.hp)/boss.max_hp,11,(180,73,91,255))
            self.text(f'H 회복 {r.shards}',1100,52,16,BRIGHT)
            self.route_arrow(gx,gy)
            return

        panel(824,603,432,93)
        fill(825,693,430,2,ACCENT)
        self.icon(3,847,673,25)
        self.text(f'{r.stage+1}-{r.page+1}  {CHAPTERS[r.stage]}',871,672,18,GOLD)
        self.wrap(goal,871,640,365,20,BRIGHT,1.2,2)

        panel(24,22,420,62)
        actions=[('C','연속 베기',True),('Shift','대시 베기',r.skills.get('dash',0)>0),('Z','마검파',r.skills.get('wave',0)>0)]
        for i,(key,name,ready) in enumerate(actions):
            x=36+136*i
            if i:
                fill(x-8,34,1,37,(73,93,105,210))
            self.key(key,x,48,47 if i==1 else 30,strong=bool(ready))
            self.text(name,x+10,35,15,BRIGHT if ready else MUTED)
            if i and ready:
                self.text('→ C',x+54,61,14,TEAL)
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
        panel(1032,22,224,42)
        self.text('Tab 기록   Esc 메뉴',1144,43,16,BRIGHT,True)
        if r.unspent or r.skill_points:
            panel(24,540,310,30,edge=ACCENT)
            self.text(f'남은 스탯 {r.unspent} · 기술 {r.skill_points}',39,555,16,BRIGHT)
        hint = ('↓   누른 채 좌우로 이동' if s.near_crawl(p.x,p.y) else
                '↓ + ↑   발판 아래로' if p.floor_y>0 else
                '↑   도약 문양 위에서 높이 점프' if any(o['kind']=='spring' and abs(o['x']-p.x)<110 for o in s.objects)
                else '')
        if hint:
            y=122 if p.effects.buff_remaining>0 else 88
            panel(508,y,264,34)
            self.text(hint,640,y+17,16,BRIGHT,True)
        self.interaction_markers(gx,gy)
        self.route_arrow(gx,gy)
        self.crawl_markers()
        if s.developer:
            self.text('연습 모드 · F9',1123,582,14,GOLD)

    def interaction_markers(self, goal_x, goal_y):
        s,p,r=self.s,self.s.player,self.s.run
        near=s.nearest()
        for obj in s.objects:
            kind=obj['kind']
            if kind not in INTERACTIONS or obj is not near or not p.grounded:
                continue
            if kind=='record' and obj['record'] in r.records or kind=='chest' and s.obj_uid(obj) in r.taken:
                continue
            if kind=='lever' and r.has('gate_open'):
                continue
            if kind=='event' and obj.get('event')=='rescue' and r.has('rescue_done'):
                continue
            label,height=INTERACTIONS[kind]
            if kind=='door' and not s.door_ready(obj):
                label='잠긴 문'
            if kind=='door':
                x,y=s.camera.project(obj['x'],obj['y']+height)
                height+=min(0,(529-y)/s.camera.zoom)
            if kind=='event' and (obj.get('npc') or obj.get('actor_x') is not None):
                label='이야기하기'
                height=134 if obj.get('event')=='merchant' and (not r.has('merchant_done') or r.has('ward_taken')) else 195
            target_x=obj.get('actor_x',obj['x'])
            x,y=s.camera.project(target_x,obj['y']+height)
            if not 22<x<1258 or not 123<y<540:
                continue
            quest=abs(goal_x-target_x)<42 and abs(goal_y-obj['y'])<32
            hue=ACCENT if quest else EDGE
            card_x=max(22,min(1080,x-89))
            panel(card_x,y+19,176,40,edge=hue)
            self.key('E',card_x+8,y+26,30,strong=quest)
            self.text(label,card_x+49,y+39,16,BRIGHT)
            fill(x-1,y+6,2,13,hue)

    def route_arrow(self,x,y):
        s=self.s
        p=s.player
        target=next((o for o in s.objects if o['kind'] in INTERACTIONS
                     and o.get('actor_x',o['x'])==x and o['y']==y),None)
        gx,gy=s.camera.project(x,y)
        if target and 42<gx<1238 and 38<gy<670:
            kind=target['kind']
            height=373 if kind=='door' else 214 if target.get('npc') else INTERACTIONS[kind][1]+36
            ax,ay=s.camera.project(x,y+height)
            if s.nearest() is target and p.grounded:
                ay+=34
            # Mark the prop's top; tuck below the HUD where their screen areas overlap.
            ceiling=568 if ax<368 or ax>796 else 669
            ay=max(126,min(ceiling,ay))
            angle=1.5708
        else:
            px,py=s.camera.project(p.x,p.y+117)
            dx,dy=gx-px,gy-(py-117*s.camera.zoom)
            distance=max(1,hypot(dx,dy))
            if distance<89:
                return
            ax=max(48,min(1232,px+dx/distance*160))
            ay=max(138,min(513,py+dy/distance*160))
            angle=atan2(-dy,dx)
        im=self.guide_arrow
        im.opacify(.87+.07*sin(s.time*3))
        draw_region(im,(0,0,im.w,im.h),ax,ay,72/im.w,1,angle)
        im.opacify(1)

    def crawl_markers(self):
        s=self.s
        for o in s.objects:
            if o['kind']!='crawl':
                continue
            for side in (-1,1):
                x,y=s.camera.project(o['x']+side*(o['w']/2-26),o['y']+93)
                if 42<x<1238 and 120<y<533:
                    self.a.fit('polish/crawl_marker',x,y,32,36)

    def fiction_card(self):
        s, m = self.s, self.s.modal
        story=m['kind'] in {'dialogue','boss','final'}
        if story:
            left,width = 370,848
            if not m.get('cine') and m.get('portrait') and s.region!='merchant':
                panel(54,49,293,312,background=(9,16,25,132))
                self.a.fit('adv/'+m['portrait'],200,210,263,255)
        else:
            left,width=267,746
        options=m['options']
        rows=options
        bottom=34 if story else 75
        label=m.get('speaker') if story else None
        show_speaker=label and label not in {'이야기','소년'}
        lines=self.text_lines(m['text'],width-56,19) if m['text'] else []
        top=bottom+121+48*len(rows)+20*len(lines)+(19 if show_speaker else 0)
        panel(left,bottom,width,top-bottom,edge=ACCENT,background=(10,18,29,211))
        self.a.fit('polish/fiction_header',left+width/2,top-35,width-24,70,alpha=.95)
        wordmark={'거울 웅덩이':'label_rescue','숲의 상인':'label_merchant',
                  '일시 정지':'label_pause','능력치 성장':'label_stat_growth',
                  '기술 성장':'label_skill_growth'}.get(m['title'])
        if m['kind']=='path':
            wordmark='label_level'
        if wordmark:
            self.a.fit('polish/'+wordmark,left+width/2,top-35,230,28)
        else:
            self.text(m['title'],left+width/2,top-35,25,GOLD,True)
        if show_speaker:
            self.text(label,left+26,top-70,16,TEAL)
        content_y=top-92 if show_speaker else top-75
        for j,line in enumerate(lines):
            self.text(line,left+28,content_y-j*22,19,CREAM)
        for offset, option in enumerate(rows):
            i=offset
            y=bottom+27+(len(rows)-1-offset)*48
            selected=i==s.selected
            disabled=len(option)>2 and bool(option[2])
            asset='polish/fiction_selected' if selected else 'polish/fiction_row'
            fill(left+22,y+3,width-44,37,(10,19,30,221 if selected else 189))
            self.a.panel(asset,left+19,y,width-38,43,.96 if selected else .80)
            tip=option[3] if len(option)>3 else None
            if tip:
                icon='polish/'+tip if tip.startswith('path_') else 'adv/'+tip
                self.a.fit(icon,left+74,y+22,31,31)
            self.text(str(offset+1),left+39,y+22,14,GOLD,True)
            color=MUTED if disabled else BRIGHT if selected else CREAM
            stat_art={'공격력 +5':'attack','마력 +6':'magic','최대 HP +20':'vitality','최대 MP +15':'focus',
                      '마검파':'wave','대시공격':'dash'}.get(option[0])
            if stat_art:
                art='polish/label_'+stat_art
                info=self.a.clips[art]
                w=22*info['width']/info['height']
                inset=98 if tip else 62
                self.a.fit(art,left+inset+w/2,y+22,w,22)
            else:
                text_width=width-(140 if tip else 102)
                text_y=y+31 if len(self.text_lines(option[0],text_width,19))>1 else y+22
                self.wrap(option[0],left+(98 if tip else 62),text_y,text_width,19,color,1.0,2)
            s.hitboxes.append((left+19,y,width-38,43,i))
        self.text('↑ ↓ 선택   ·   Enter 확인',left+23,bottom+13,13,MUTED)

    def banner(self):
        b=self.s.banner
        if not b: return
        age,left=b['age'],b['duration']-b['age']
        alpha=min(1,age/.3,left/.45)
        y=530+10*(1-min(1,age/.4))
        panel(395,y-45,490,102,edge=(208,174,107,round(225*alpha)),
              background=(13,22,32,round(181*alpha)))
        self.title_image(b['image'],640,y+13,366,alpha)
        self.text(b['subtitle'],640,y-30,17,BRIGHT,True)

    def cinematic(self):
        s=self.s
        if s.region=='merchant' and s.modal:
            age=s.interaction_age
            self.a.cover('polish/merchant_story',640,360,1280,720,
                         zoom=1+min(1,age/5)*.025,alpha=min(1,age/.25))
            fill(0,696,1280,24,(3,7,14,163))
            return
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
        m=self.s.modal
        if m['kind']=='journal':
            self.journal()
            return
        if m['kind'] not in {'dialogue','boss','final'}:
            fill(0,0,1280,720,(4,10,16,112))
        self.fiction_card()

    def journal(self):
        s,r=self.s,self.s.run
        fill(0,0,1280,720,(7,13,22,217))
        panel(156,81,968,562,edge=ACCENT,background=(12,22,34,237))
        tabs=('journal_stats','journal_compare','journal_ending')
        for i,art in enumerate(tabs):
            x=188+i*300
            selected=i==s.journal_page
            panel(x,568,284,51,edge=ACCENT if selected else EDGE,
                  background=(55,48,39,242) if selected else (19,32,45,235))
            self.a.fit('polish/'+art,x+142,594,164,21,alpha=1 if selected else .78)
        if s.journal_page==0:
            self.journal_stats(r)
        elif s.journal_page==1:
            self.journal_compare(r)
        else:
            self.journal_endings()
        self.text('← → 탭 이동   ·   Tab / Esc 닫기',640,103,16,MUTED,True)

    def journal_stats(self,r):
        names={'physical':'대시공격','magic':'마검파','balance':'균형'}
        panel(193,415,405,123,edge=EDGE,background=(20,32,45,235))
        self.text(f'레벨 {r.level}',215,511,25,GOLD)
        self.text(names.get(r.path,'마검사'),215,474,18,BRIGHT)
        self.text(f'검기 {r.tier}단계',215,444,16,MUTED)
        panel(193,205,405,190,edge=EDGE,background=(20,32,45,235))
        for i,(label,value) in enumerate((('공격력',r.attack),('마력',r.magic),
                                           ('최대 HP',r.max_hp),('최대 MP',r.max_mp))):
            x=215+(i%2)*196
            y=358-(i//2)*72
            self.text(label,x,y,16,MUTED)
            self.text(value,x,y-33,26,BRIGHT)
        self.text(f'남은 포인트   스탯 {r.unspent}   기술 {r.skill_points}',215,226,15,TEAL)
        panel(620,205,463,333,edge=EDGE,background=(20,32,45,235))
        self.text('여정',643,509,24,GOLD)
        notes=[('동행','루네아' if r.companion else '혼자'),
               ('마을 신뢰',f'{r.trust} / 2'),('침식',f'{r.erosion} / 3'),
               ('기억의 기록',f'{len(r.records)} / 3'),('함께한 약속',f'{len(r.pacts)} / 3')]
        for i,(label,value) in enumerate(notes):
            y=463-i*43
            self.text(label,643,y,17,MUTED)
            self.text(value,1000,y,19,BRIGHT,True)
            fill(643,y-21,414,1,(78,87,96,124))
        missing=r.missing_restore()
        status='경계 복원 준비 완료' if not missing else '복원 준비  ·  '+', '.join(missing)
        self.wrap(status,198,175,880,15,MUTED,1.35,2)
        if r.choices:
            self.wrap('최근 선택  ·  '+choice_label(*r.choices[-1]),198,132,880,15,BRIGHT,1.1,1)

    def journal_compare(self,r):
        s=self.s
        histories=[h for h in s.store.history if h.get('seed')!=r.seed]
        past=Run.from_dict(histories[s.history_index%len(histories)]) if histories else None
        for x,title,run in ((193,'이전 세계선',past),(657,'현재 세계선',r)):
            panel(x,182,426,353,edge=EDGE,background=(20,32,45,235))
            self.text(title,x+26,502,24,GOLD)
            if run is None:
                self.text('완결한 기록이 없음',x+26,443,18,MUTED)
                continue
            entries=(('레벨',run.level),('공격력',run.attack),('마력',run.magic),
                     ('처치',run.kills),('동행','루네아' if run.companion else '혼자'),
                     ('결말',ENDINGS[run.ending][0] if run.ending else '진행 중'))
            for i,(label,value) in enumerate(entries):
                y=448-i*45
                self.text(label,x+26,y,16,MUTED)
                self.text(value,x+175,y,19,BRIGHT)
        if len(histories)>1:
            self.text(f'↑ ↓ 이전 기록   {s.history_index%len(histories)+1} / {len(histories)}',
                      640,148,16,MUTED,True)

    def journal_endings(self):
        known={h.get('ending') for h in self.s.store.history}
        entries=[(name,info[0]) for name,info in ENDINGS.items() if name!='H1' or name in known]
        for i,(ending,title) in enumerate(entries):
            x=193+(i%3)*299
            y=429-(i//3)*112
            unlocked=ending in known
            panel(x,y,275,96,edge=ACCENT if unlocked else EDGE,background=(21,33,46,230))
            badge=ending if unlocked else 'locked_ending'
            self.a.fit('adv/ending_badges__'+badge,x+40,y+48,49,49)
            self.text('동반' if ending.startswith('D') else '단독' if ending.startswith('S') else '숨은 결말',
                      x+77,y+65,14,TEAL if unlocked else MUTED)
            self.wrap(title if unlocked else '미발견',x+77,y+37,180,16,BRIGHT if unlocked else MUTED,1.15,2)
        self.text(f'발견한 결말   {len(known & ENDINGS.keys())} / 9',640,157,17,GOLD,True)

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
            if not s.modal and not s.story_only and not s.door_entry:
                self.hud()
                self.banner()
        if s.player.hp <= 0 and not s.run.ending:
            fill(0, 0, 1280, 720, (3, 6, 15, min(230, int(s.death_age*190))))
            self.a.draw('adv/failure_respawn__failure_vision', 640, 250, None, 1.2, s.death_age)
            self.title_image('failure',640,430,600)
            self.text('마지막 저장 지점에서 다시 시작합니다.  ·  Enter 건너뛰기', 640, 356, 20, MUTED, True)
        if s.modal:
            self.modal()
        if s.toast_time > 0 and not s.door_entry and (not s.story_only or s.modal):
            bottom = 608 if s.modal else 200
            panel(300,bottom,680,51,edge=ACCENT)
            self.wrap(s.toast, 320, bottom+33, 640, 16, GOLD, 1.2, 2)
