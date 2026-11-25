"""플레이 화면·선택창·성장창·기록책. 그림은 생성한 PNG, 글자는 선명한 글꼴로 표시한다."""
from math import atan2, hypot, sin
import pico2d.pico2d as engine
from pico2d import SDL_RenderSetScale, SDL_Rect, SDL_SetRenderDrawColor, SDL_RenderDrawRect
from interface import fill, speech_tail
from battle_ui import BattleArt
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
        self.battle_art = BattleArt(scene.root/'assets')
        self.hud_icons = load_pixel_image(scene.root/'assets/ui/hud_icons.png', smooth=True)
        self.guide_arrow = self.a.image(self.a.clips['polish/route_pointer']['path'])

    def icon(self, index, x, y, size=20):
        self.hud_icons.clip_draw(index*64, 0, 64, 64, round(x), round(y), size, size)

    def key(self, label, x, y, width=30, strong=False, height=26):
        panel(x, y, width, height, edge=ACCENT if strong else EDGE,
              background=(70, 53, 29, 122) if strong else (25, 39, 50, 105))
        self.text(label, x+width/2, y+height/2+1, 14, GOLD if strong else BRIGHT, True)

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
            else:
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
            self.battle_art.damage(n['text'], n['x']-s.camera.x, n['y']-s.camera.y, n['age'], n['hurt'])
        for o in s.objects:
            if o['kind']=='door':
                s.assets.draw('adv/gate_open__gate_open',o['x'],o['y'],s.camera,.65,
                              max(0,s.time-o.get('opened',s.time-99)),frame=None if s.door_ready(o) else 0)

    def nameplates(self):
        """월드 좌표를 화면에 옮긴 뒤 그려 줌 배율과 무관하게 선명하게 읽힌다."""
        s,p=self.s,self.s.player
        entries=[]
        if p.hp>0 and not s.door_entry:
            frame=p.animation.clip['frames'][p.animation.frame]
            px,py=p.x,p.y
            if s.modal and s.modal.get('visual')=='camp':
                hx,lx,py,facing=s.modal['camp_seats']
                t=min(1,s.camp_age/.36);t=t*t*(3-2*t)
                px+=(hx-px)*t
            px+=p.facing*(frame.get('headAnchorX',0)+p.animation.bridge_x)*frame.get('renderScale',1)
            entries.append((s.run.display_name,px,py+frame.get('bodyHeight',174)+16,GOLD))
        if s.companion:
            ally=s.companion
            if s.modal and s.modal.get('visual')=='camp':
                _,lx,y,_=s.modal['camp_seats']
                entries.append(('루네아',lx,y+140,TEAL))
            else:
                entries.append(('루네아',ally.x,ally.y+174,TEAL))
        npc_names={'elder':'촌장','healer':'치유사','merchant':'상인','envoy':'마왕의 전령'}
        for obj in s.objects:
            event=obj.get('event')
            if event in npc_names and (obj.get('npc') or event=='merchant'):
                height=157 if event=='merchant' and not s.run.has('merchant_done') else 199
                entries.append((npc_names[event],obj.get('actor_x',obj['x']),obj['y']+height,CREAM))
            elif event=='rescue' and not s.companion:
                entries.append(('루네아',obj['x']+35,obj['y']+174,TEAL))
        for enemy in s.enemies:
            if enemy.alive:
                box=enemy.hurtbox()
                entries.append((enemy.actor['name'],enemy.x,box[3]+24,(238,181,170)))
        for label,wx,wy,color in entries:
            x,y=s.camera.project(wx,wy)
            if not 25<x<1255 or not 100<y<625:continue
            width=self.ui.measure(label,16)+16
            fill(x-width/2,y-11,width,23,(7,13,22,105))
            self.text(label,x+1,y,16,(10,13,21),True)
            self.text(label,x,y+1,16,color,True)

    def title_image(self, name, x, y, width=360, alpha=1):
        key = 'polish/title_'+name
        if key in self.a.clips:
            c = self.a.clips[key]
            # 작은 제목을 무리하게 늘리지 않는다.
            self.a.fit(key, x, y, min(width, c['width']*1.2), 90, alpha=alpha)

    def meter(self, x, y, w, label, value, maximum, color, icon):
        self.icon(icon,x+9,y+8,16)
        self.text(label,x+22,y+8,13,MUTED)
        bx=x+51
        fill(bx,y,w-51,15,(28,39,49,175))
        width=(w-51)*max(0,min(1,value/max(1,maximum)))
        fill(bx,y,width,15,color)
        if width>1:
            fill(bx,y+13,width,2,tuple(min(255,c+36) for c in color[:3])+(255,))
        self.text(f'{max(0,int(value))} / {maximum}',bx+(w-51)/2,y+8,13,BRIGHT,True)

    def hud(self):
        s,r,p=self.s,self.s.run,self.s.player
        # 배경이 비치는 낮은 띠 안에 능력치와 여섯 조작키만 모은다.
        self.battle_art.frame.opacify(.55)
        self.battle_art.frame.draw(640,42,900,78)
        self.battle_art.frame.opacify(1)
        self.text(f'{r.display_name}  Lv.{r.level}',214,64,16,GOLD)
        self.meter(430,55,205,'HP',p.hp,r.max_hp,(163,67,82,245),0)
        self.meter(655,55,205,'MP',s.mp,r.max_mp,(55,108,158,245),1)
        self.text(f'공격 {r.attack:g}  마력 {r.magic:g}',878,64,15,CREAM)
        fill(214,44,852,2,(31,40,50,125))
        fill(214,44,852*min(1,r.xp/max(1,r.xp_needed)),2,(183,145,84,215))
        cd=s.magic_cooldown
        actions=[
            ('C','연속 베기',True,None),
            ('Shift','대시 → C' if p.dash_unlocked else '대시',True,p.dash_cooldown),
            ('Z','마검파',p.magic_unlocked,cd),
            ('X','방어',True,None),
            ('Q','달빛',bool(s.companion),s.companion.cooldown if s.companion else None),
            ('H',f'회복 {r.shards}',r.shards>0,None)]
        for i,(key,name,unlocked,cooldown) in enumerate(actions):
            x=220+i*142
            kw=42 if key=='Shift' else 24
            self.key(key,x,12,kw,strong=unlocked and not cooldown,height=22)
            label=(f'대시 {cooldown:.1f}초' if key=='Shift' and cooldown
                   else f'{name} {cooldown:.0f}s' if cooldown and cooldown>0
                   else name if unlocked else '미습득')
            self.text(label,x+kw+7,24,14,CREAM if unlocked else MUTED)
            if key=='Shift' and cooldown:
                fill(x+kw+7,12,76*min(1,cooldown/p.dash_recharge),2,ACCENT)
        goal,gx,gy=objective(s)
        self.battle_art.banner(194,675,365,78)
        self.text(f'{r.stage+1}-{r.page+1}  {CHAPTERS[r.stage]}',58,689,23,GOLD)
        self.text('Esc 메뉴   ·   Tab 기록',58,659,16,CREAM)
        if goal:
            self.battle_art.banner(1042,675,455,78)
            self.text('지금 할 일',871,702,14,GOLD)
            self.wrap(goal,871,678,380,23,BRIGHT,1.0,2)
        if r.unspent:
            self.text(f'L 성장 선택 · {r.unspent}회',875,620,17,GOLD)
        self.interaction_markers(gx,gy)
        self.route_arrow(gx,gy)
        self.crawl_markers()

    def boss_health(self):
        s = self.s
        if s.region != 'boss':
            return
        boss = next((enemy for enemy in s.enemies if enemy.boss and enemy.alive), None)
        if boss is None:
            return
        width = 660
        left = 640 - width / 2
        self.text(boss.actor['name'],641,645,28,(11,13,22),True)
        self.text(boss.actor['name'],640,647,28,GOLD,True)
        panel(left-3,602,width+6,26,edge=ACCENT,background=(28,18,30,213))
        ratio = max(0, min(1, boss.hp / boss.max_hp))
        fill(left,605,width*ratio,20,(159,42,64,245))
        fill(left,622,width*ratio,3,(236,128,133,224))
        self.text(f'{max(0, round(boss.hp)):,} / {boss.max_hp:,}',640,616,14,BRIGHT,True)

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
        s,m=self.s,self.s.modal
        story=m['kind'] in {'dialogue','boss','final'}
        if story:
            sx,sy=s.camera.project(m.get('speaker_x',s.player.x),m.get('speaker_y',s.player.y+165))
            width=520
            left=max(16,min(1264-width,sx-width/2))
            lines=self.text_lines(m['text'],width-42,19)
            height=68+25*len(lines)
            bottom=max(285,min(690-height,sy+25))
            speech_tail((max(left+22,min(left+width-36,sx-12)),bottom),
                        (max(left+36,min(left+width-22,sx+12)),bottom),
                        (max(12,min(1268,sx)),min(bottom-10,sy+8)))
            panel(left,bottom,width,height,edge=ACCENT,background=(8,17,39,237))
            self.text(m.get('speaker','소년'),left+20,bottom+height-22,15,GOLD)
            visible=m['text'][:max(1,int(s.interaction_age*48))] if not m.get('revealed') else m['text']
            if len(visible)==len(m['text']):m['revealed']=True
            self.wrap(visible,left+20,bottom+height-53,width-40,19,CREAM,1.3,5)
            left,width,bottom=280,720,18
        else:
            left,width,bottom=280,720,164
            panel(left,bottom,width,349,edge=ACCENT,background=(8,17,29,240))
            self.text(m['title'],640,478,26,GOLD,True)
            self.wrap(m['text'],left+28,435,width-56,18,CREAM,1.3,3)
        if m.get('name_entry'):
            entry=m['name_entry']
            panel(340,16,600,139,edge=ACCENT,background=(10,19,33,210))
            self.text('이름을 알려 주세요',640,131,21,GOLD,True)
            panel(430,65,420,42,edge=ACCENT,background=(7,15,25,185))
            value=entry.text+entry.composition
            self.text(value or '한글·영문·숫자 1~10자',640,87,23,BRIGHT if value else MUTED,True)
            if entry.composition:
                width=self.ui.measure(value,23)
                cx=640+width/2
                fill(cx-self.ui.measure(entry.composition,23),72,self.ui.measure(entry.composition,23),1,GOLD+(255,))
            self.text(entry.error or 'Enter 확인  ·  Backspace 지우기',640,52,14,
                      (240,160,145) if entry.error else MUTED,True)
            panel(520,19,240,28,edge=ACCENT,background=(68,53,36,160))
            self.text('이 이름으로 출발',640,34,17,BRIGHT,True)
            s.hitboxes.append((520,19,240,28,0))
            return
        rows=m['options']
        for i,option in enumerate(rows):
            y=bottom+27+(len(rows)-1-i)*48
            selected=i==s.selected
            disabled=len(option)>2 and bool(option[2])
            panel(left+14,y,width-28,42,edge=ACCENT if selected else EDGE,
                  background=(53,42,62,236) if selected else (9,19,32,220))
            self.text(str(i+1),left+37,y+21,15,GOLD,True)
            self.wrap(option[0],left+60,y+22,width-89,18,
                      MUTED if disabled else BRIGHT if selected else CREAM,1.0,1)
            s.hitboxes.append((left+14,y,width-28,42,i))
        numbers = ' · '.join(str(i + 1) for i in range(len(rows)))
        hint = 'Enter 계속' if len(rows)==1 else f'{numbers} 선택  /  Enter 확인'
        self.text(hint,640,bottom+12,12,MUTED,True)

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

    def reward_notice(self):
        reward = self.s.rewards[0]
        age, duration = reward['age'], reward['duration']
        opacity = max(.35, min(1, age / .18, (duration - age) / .3))
        y = 550 + 14 * (1 - min(1, age / .23))
        self.battle_art.banner(640,y,490,73)
        self.text(reward['title'],640,y+13,28,GOLD,True)
        self.text(reward['detail'],640,y-16,17,CREAM,True)
        fill(444,y-31,392*(1-min(1,age/duration)),2,(222,182,112,round(175*opacity)))

    def cinematic(self):
        # 대화는 같은 공간의 인물과 말풍선으로 이어 간다.
        return

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
        self.text(f'대시 재사용 {r.dash_recharge}초  ·  성장 선택 {r.unspent}회',215,226,15,TEAL)
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
                self.text('네가 한 선택들, 정말 후회하지 않을 자신이 있냐?', 640, 70, 23, MUTED, True)
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
            self.nameplates()
            self.battle_art.hurt_border(s.damage_flash)
            if not s.modal and not s.story_only and not s.door_entry:
                self.hud()
                if not s.reward_visible:
                    self.banner()
            if not s.door_entry and (not s.modal or s.modal['kind']=='boss'):
                self.boss_health()
        if s.player.hp <= 0 and not s.run.ending:
            fill(0, 0, 1280, 720, (3, 6, 15, min(230, int(s.death_age*190))))
            self.a.draw('adv/failure_respawn__failure_vision', 640, 250, None, 1.2, s.death_age)
            self.title_image('failure',640,430,600)
            self.text('마지막 저장 지점에서 다시 시작합니다.  ·  Enter 건너뛰기', 640, 356, 20, MUTED, True)
        if s.modal:
            self.modal()
        if not s.run.ending and s.reward_visible:
            self.reward_notice()
        if s.toast_time > 0 and not s.door_entry and (not s.story_only or s.modal):
            bottom = 580 if s.modal else 133
            panel(380,bottom,520,38,edge=EDGE)
            self.wrap(s.toast, 396, bottom+25, 488, 15, GOLD, 1.2, 1)
