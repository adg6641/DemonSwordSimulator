"""플레이 화면·선택창·성장창·기록책. 그림은 생성한 PNG, 글자는 선명한 글꼴로 표시한다."""
import pico2d.pico2d as engine
from pico2d import SDL_RenderSetScale
from interface import fill, speech_tail
from progress import Run, ENDINGS
from story import CHAPTERS, objective, choice_label

CREAM = (237, 228, 209)
MUTED = (170, 191, 187)
GOLD = (231, 194, 125)
TEAL = (151, 216, 198)


class CampaignView:
    def __init__(self, scene):
        self.s = scene
        self.a, self.ui = scene.assets, scene.ui
        self.wrap_cache = {}

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
            key = o['visual']
            scale = 1
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
            scale = .7
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
                    a.draw('adv/lunea_rescue__lunea_trapped', o['x']+35, 0, s.camera, .6, age)
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
            age = s.interaction_age
            clip = 'adv/hero_camp__hero_sit_down' if age < .67 else 'adv/hero_story__hero_read_map'
            s.assets.draw(clip, s.player.x, s.player.y, s.camera, 1, age)
            if s.companion:
                clip = 'adv/lunea_camp__lunea_sit_down' if age < .67 else 'adv/lunea_story__lunea_map'
                s.assets.draw(clip, s.player.x-145, 0, s.camera, .6, age)
        else:
            if s.companion:
                if visual == 'memory':
                    s.assets.draw('adv/lunea_ritual__lunea_memory_ritual', s.companion.x, s.companion.y, s.camera, .6, s.interaction_age)
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

    def hud(self):
        s, r, p = self.s, self.s.run, self.s.player
        fill(20, 602, 342, 98, (8, 17, 24, 226))
        self.a.fit('adv/portrait_hero__hero_focus', 64, 655, 68, 76)
        self.text(f'Lv.{r.level}', 110, 679, 20, GOLD)
        self.text({'physical':'물리', 'magic':'마법', 'balance':'균형'}.get(r.path,'소년'), 174, 679, 17, MUTED)
        for y, v, top, label, color in [(651,p.hp,r.max_hp,'HP',(180,77,89,255)), (627,s.mp,r.max_mp,'MP',(74,133,174,255))]:
            fill(110,y-6,228,12,(28,33,39,255))
            fill(110,y-6,228*max(0,v)/top,12,color)
            self.text(f'{label}  {max(0,int(v))}/{top}', 222,y,14,CREAM,True)
        fill(110,609,228,3,(45,43,36,255))
        fill(110,609,228*r.xp/r.xp_needed,3,(208,171,100,255))
        goal, gx = objective(s)
        fill(754,617,506,83,(8,17,24,218))
        self.text(f'{r.stage+1:02d}  {CHAPTERS[r.stage]}', 775,678,18,GOLD)
        arrow = '→' if gx>p.x+80 else '←' if gx<p.x-80 else 'E'
        self.wrap(arrow+'  '+goal,775,648,460,18,CREAM,1.35,2)

        fill(20,20,365,67,(8,17,24,218))
        for i,(label,key) in enumerate([('C 베기',None),('대시 베기','dash'),('Z 마검파','wave')]):
            x=40+i*115
            unlocked = key is None or r.skills.get(key,0)>0
            self.text(label,x,66,17,CREAM if unlocked else (108,121,125))
            self.text('연속 입력' if key is None else 'Shift 뒤 C' if key=='dash' else 'Z 뒤 C' if unlocked else '성장 후 해금',x,40,13,MUTED)
        self.text(f'H 회복  {r.shards}', 405,43,16,CREAM)
        if s.companion:
            self.text('Q 달빛  '+(f'{s.companion.cooldown:.0f}초' if s.companion.cooldown>0 else '준비'), 525,43,16,TEAL)
        # 오른쪽 정렬 대신 고정 폭의 한 줄로 조작을 분리한다.
        self.text('L 성장   Tab 기록   Esc 메뉴', 998,30,15,MUTED)
        if r.unspent or r.skill_points:
            fill(20,100,240,35,(28,28,25,226))
            self.text(f'L  새 성장 포인트 {r.unspent+r.skill_points}',36,119,17,GOLD)
        if p.effects.buff_remaining>0:
            self.text(f'마검파 {p.effects.buff_remaining:.1f}초', 680,43,16,TEAL)
        boss=next((e for e in s.enemies if e.boss and e.alive and abs(e.x-p.x)<900),None)
        if boss:
            fill(420,100,540,9,(37,23,30,240))
            fill(420,100,540*boss.hp/boss.max_hp,9,(178,79,98,255))
            self.text(boss.actor['name'],690,132,19,GOLD,True)
            if boss.state=='windup': self.text('공격 준비 · 피하거나 막으세요',690,158,16,(243,173,147),True)
        near=s.nearest()
        if near:
            x,y=s.camera.project(near['x'],near['y']+195)
            x=max(135,min(1145,x))
            label={'event':'이야기하기','record':'기록 읽기','chest':'상자 열기','camp':'쉬기 · 저장','lever':'성문 열기'}[near['kind']]
            fill(x-116,y-17,232,35,(8,17,24,235))
            self.text('E  '+label,x,y,18,GOLD,True)
        if s.developer: self.text('연습 모드 · F9 끄기',1010,590,15,GOLD)

    def story_dialogue(self):
        s,m=self.s,self.s.modal
        # 월드 확대 뒤에도 말풍선 글자와 선택 버튼은 화면 픽셀 크기를 유지한다.
        sx,sy=s.camera.project(m['speaker_x'],m['speaker_y'])
        cx=max(390,min(890,sx))
        bottom=max(459,min(487,sy+18))
        show=min(1,s.interaction_age/.18)
        visible=m['text'] if m.get('revealed') else m['text'][:int(s.interaction_age*38)]
        if m['kind']=='boss' and m['speaker']=='바르켄':
            # 거인의 얼굴 앞에 큰 말풍선을 덮지 않고 빈 왼쪽 공간을 쓴다.
            cx,bottom=360,492
            self.a.fit('polish/speech_body',cx,bottom+87,680,174,alpha=show)
            speech_tail((696,bottom+104),(696,bottom+126),(max(755,min(990,sx-55)),bottom+125))
            self.text(m['speaker'],cx-250,bottom+139,21,GOLD)
            self.wrap(visible,cx-250,bottom+109,535,20,CREAM,1.3,3)
        else:
            self.a.fit('polish/speech',cx,bottom+100,740,200,alpha=show)
            self.text(m['speaker'],cx-270,bottom+163,21,GOLD)
            self.wrap(visible,cx-270,bottom+132,605,20,CREAM,1.3,4)
        fill(0,0,1280,205,(6,14,22,244))
        fill(32,204,1216,1,(171,147,99,175))
        self.text(m['title'],48,180,22,GOLD)
        if m.get('emphasis'): self.title_image(m['emphasis'],1100,178,245)
        self.options(m, compact=True)
        self.text('↑ ↓ 선택  ·  Enter 확인 / 글 한 번에 보기  ·  클릭 가능',640,15,14,MUTED,True)

    def options(self,m,compact=False):
        s=self.s
        start=s.selected//4*4
        for row,i in enumerate(range(start,min(start+4,len(m['options'])))):
            option=m['options'][i]
            disabled=len(option)>2 and bool(option[2])
            if compact:
                left,bottom,w,h=48+(row%2)*604,99-(row//2)*61,580,53
            else:
                left,bottom,w,h=105,312-row*62,1070,53
            selected=i==s.selected
            fill(left,bottom,w,h,(38,48,53,255) if selected else (16,29,38,250))
            fill(left,bottom,3,h,(225,189,116,255) if selected else (78,95,100,200))
            color=(120,133,136) if disabled else GOLD if selected else CREAM
            icon=option[3] if len(option)>3 else None
            if icon and not compact:
                self.a.fit('adv/'+icon,left+30,bottom+27,30,30)
            self.wrap(f'{row+1}. '+option[0],left+(58 if icon and not compact else 20),bottom+32,w-56,18,color,1.2,2)
            s.hitboxes.append((left,bottom,w,h,i))
        if len(m['options'])>4:
            self.text(f'{start//4+1}/{(len(m["options"])+3)//4}  ↓ 다음 선택지',1050,180 if compact else 87,14,MUTED)

    def banner(self):
        b=self.s.banner
        if not b: return
        age,left=b['age'],b['duration']-b['age']
        alpha=min(1,age/.3,left/.45)
        y=533+12*(1-min(1,age/.4))
        fill(410,y-46,460,110,(5,13,22,round(alpha*180)))
        self.title_image(b['image'],640,y+12,430,alpha)
        self.text(b['subtitle'],640,y-32,17,MUTED,True)

    def modal(self):
        s, m = self.s, self.s.modal
        if m['kind'] in {'dialogue','boss','final'}:
            self.story_dialogue()
            return
        if m['kind'] == 'journal':
            self.journal()
            return
        fill(0, 0, 1280, 720, (4, 10, 16, 185))
        self.a.panel('adv/ui_panels__dialogue_panel', 48, 58, 1184, 618)
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
        self.a.panel('adv/ui_panels__dialogue_panel', 30, 65, 1220, 625)
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
            fill(300, bottom, 680, 51, (10, 21, 29, 240))
            self.wrap(s.toast, 320, bottom+33, 640, 16, GOLD, 1.2, 2)
