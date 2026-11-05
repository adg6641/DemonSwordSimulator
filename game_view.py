"""플레이 화면·선택창·성장창·기록책. 그림은 생성한 PNG, 글자는 선명한 글꼴로 표시한다."""
from math import sin
from interface import fill
from progress import Run, ENDINGS
from campaign_data import OBJECTIVES

CREAM = (237, 228, 209)
MUTED = (170, 191, 187)
GOLD = (231, 194, 125)
TEAL = (151, 216, 198)


class CampaignView:
    def __init__(self, scene):
        self.s = scene
        self.a, self.ui = scene.assets, scene.ui

    def text(self, value, x, y, size=20, color=CREAM, center=False):
        self.ui.text(str(value), x, y, size, color, center)

    def wrap(self, text, x, y, width, size=20, color=CREAM, spacing=1.55, max_lines=8):
        lines = []
        for paragraph in str(text).split('\n'):
            line, length = '', 0
            for ch in paragraph:
                advance = size*(.58 if ord(ch)<128 else 1.0)
                if length+advance > width and line:
                    lines.append(line)
                    line, length = '', 0
                line += ch
                length += advance
            lines.append(line)
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
            c = a.clips[key]
            scale = o['w']/c['frameWidth']
            y -= (c['frameHeight']-16)*scale
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
                    phase = s.time%11
                    state = 'greet' if abs(s.player.x-o['x'])<180 and phase<1 else 'walk' if 6<phase<8 else 'idle'
                    dx = sin((phase-6)/2*3.14159)*22 if state=='walk' else 0
                    a.draw('adv/'+o['npc']+'__'+state, o['x']+dx, 0, s.camera, .72, phase)
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
        if int(s.time/6)%2:
            s.assets.draw('adv/leaves_fireflies__leaf_drift' if s.run.stage<3 else 'adv/night_mist__night_mist', s.camera.x+900, 35 if s.run.stage>=3 else 300, s.camera, .7, s.time, alpha=.5)
        else:
            s.assets.draw('adv/leaves_fireflies__fireflies', s.camera.x+830, 200, s.camera, .6, s.time, alpha=.55)
        s.assets.draw('adv/grass_dust__grass_sway', s.camera.x+380, 0, s.camera, .23, s.time)
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
                    s.assets.draw('adv/lunea_ritual__lunea_memory_ritual', s.companion.x, 0, s.camera, .6, s.interaction_age)
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

    def hud(self):
        s, r, p = self.s, self.s.run, self.s.player
        fill(18, 575, 375, 128, (7, 17, 23, 215))
        self.a.fit('adv/portrait_hero__hero_focus', 65, 659, 75, 75)
        self.a.fit('adv/ui_hud__portrait_socket', 65, 659, 88, 88)
        self.text(f'Lv.{r.level}  '+({'physical': '물리 특화', 'magic': '마법 특화', 'balance': '균형 성장'}.get(r.path, '검을 주운 소년')), 113, 686, 19)
        for y, value, maximum, kind, color in [(655, p.hp, r.max_hp, 'hp', (172, 69, 80, 255)), (627, s.mp, r.max_mp, 'mp', (72, 125, 164, 255))]:
            fill(113, y-6, 244, 12, (25, 28, 35, 255))
            fill(113, y-6, max(0, 244*value/maximum), 12, color)
            self.a.panel('adv/ui_hud__'+kind+'_frame', 104, y-14, 266, 28)
            self.text(f'{kind.upper()} {max(0, int(value))} / {maximum}', 236, y, 15, CREAM, True)
        fill(38, 592, 328, 6, (37, 37, 36, 255))
        fill(38, 592, 328*r.xp/r.xp_needed, 6, (199, 163, 83, 255))
        self.text(f'EXP {r.xp}/{r.xp_needed}', 38, 606, 13, MUTED)
        self.a.fit('adv/ui_hud__erosion_'+str(r.erosion), 414, 661, 46, 46)
        self.text(f'침식 {r.erosion}  |  신뢰 {r.trust}', 450, 680, 16, MUTED)
        fill(850, 654, 412, 46, (7, 17, 23, 235))
        self.text(f'{r.stage+1} / 8  ·  {s.world.stage["title"]}', 1055, 680, 20, GOLD, True)
        fill(430, 601, 832, 45, (7, 17, 23, 195))
        self.wrap(OBJECTIVES[r.stage], 448, 627, 790, 16, MUTED, 1.2, 2)
        for i, (skill, label, icon) in enumerate([('dash', 'Shift → C', 'dash'), ('wave', 'Z → C', 'magic')]):
            x = 36+i*84
            self.a.panel('adv/ui_hud__skill_socket', x, 38, 60, 60)
            self.a.fit('adv/stat_icons__'+icon, x+30, 68, 36, 36, alpha=1 if r.skills.get(skill, 0) else .25)
            self.text(label, x+30, 23, 13, MUTED, True)
        self.a.fit('adv/reward_icons__healing_shard', 238, 68, 32, 40)
        self.text(f'H · {r.shards}', 265, 65, 17)
        if s.companion:
            self.a.fit('adv/ui_hud__companion_socket', 352, 70, 64, 64)
            self.a.fit('adv/portrait_lunea__lunea_smile', 352, 70, 48, 48)
            self.text('Q 달빛 '+(f'{s.companion.cooldown:.0f}초' if s.companion.cooldown>0 else '준비'), 396, 68, 16, TEAL)
        self.text('E 상호작용   L 성장   Tab 기록책   Esc 일시 정지', 768, 30, 16, MUTED)
        if r.unspent or r.skill_points:
            self.text(f'L · 성장 대기 {r.unspent+r.skill_points}점', 38, 554, 19, GOLD)
        if p.effects.buff_remaining > 0:
            self.text(f'마검파 {p.effects.buff_remaining:.1f}초 · 검기 {p.effects.level}단계', 510, 68, 18, TEAL)
        boss = next((e for e in s.enemies if e.boss and e.alive and abs(e.x-p.x) < 1000), None)
        if boss:
            fill(320, 111, 640, 12, (35, 19, 25, 240))
            fill(320, 111, 640*boss.hp/boss.max_hp, 12, (170, 76, 94, 255))
            self.a.panel('adv/ui_hud__boss_frame', 300, 100, 680, 34)
            self.text(boss.actor['name'], 640, 151, 19, GOLD, True)
            if boss.state == 'windup':
                self.text('공격 예고 · 점프 / 대시 / 방어', 640, 179, 16, (234, 158, 136), True)
        nearby = s.nearest()
        if nearby and not s.modal:
            x = max(125, min(1150, nearby['x']-s.camera.x))
            self.text('E · '+({'event': '살펴보기', 'record': '기록 읽기', 'chest': '상자 열기', 'camp': '쉬기 · 저장', 'lever': '사슬 스위치'}[nearby['kind']]), x, nearby['y']-s.camera.y+210, 18, GOLD, True)
        if s.developer:
            self.text('연습 키 활성 · F9 해제', 1000, 565, 16, GOLD)

    def modal(self):
        s, m = self.s, self.s.modal
        if m['kind'] == 'journal':
            self.journal()
            return
        fill(0, 0, 1280, 720, (4, 10, 16, 185))
        self.a.panel('adv/ui_panels__dialogue_panel', 48, 58, 1184, 618)
        self.text(m['title'], 640, 638, 30, GOLD, True)
        if m['kind'] == 'path':
            self.wrap(m['text'], 100, 585, 1080, 19, MUTED, 1.45, 3)
            for i, path in enumerate(['physical', 'magic', 'balance']):
                left, bottom = 108+i*365, 115
                self.a.panel('adv/ui_controls__choice_focus' if i == s.selected else 'adv/ui_controls__choice_normal', left, bottom, 335, 350)
                self.a.fit('adv/growth_cards__path_'+path, left+168, 340, 290, 180)
                self.text(m['options'][i][0], left+168, 215, 27, (49, 38, 27), True)
                tips = ['공격력 계수가 높은 대시 베기', '마력 계수가 높은 날아가는 검기', '대시와 마검파를 함께 활용']
                self.wrap(tips[i], left+30, 170, 275, 17, (69, 54, 35), 1.4, 2)
                s.hitboxes.append((left, bottom, 335, 350, i))
        else:
            if m.get('portrait'):
                self.a.fit('adv/'+m['portrait'], 196, 493, 230, 224)
                text_x, width = 342, 820
            else:
                text_x, width = 104, 1070
            self.wrap(m['text'], text_x, 576, width, 20, CREAM, 1.55, 5)
            start = s.selected//4*4
            for row, i in enumerate(range(start, min(start+4, len(m['options'])))):
                option = m['options'][i]
                disabled = len(option)>2 and bool(option[2])
                left, bottom, w, h = 105, 312-row*62, 1070, 53
                state = 'disabled' if disabled else 'focus' if i == s.selected else 'normal'
                self.a.panel('adv/ui_controls__button_'+state, left, bottom, w, h)
                icon = option[3] if len(option)>3 else None
                if icon:
                    self.a.fit('adv/'+icon, left+30, bottom+26, 30, 30)
                self.wrap(f'{row+1}. '+option[0], left+(58 if icon else 28), bottom+28, w-85, 17, (144, 152, 150) if disabled else CREAM, 1.2, 1)
                s.hitboxes.append((left, bottom, w, h, i))
            if len(m['options']) > 4:
                self.text(f'{start+1}~{min(start+4, len(m["options"]))} / {len(m["options"])}  ·  ↓ 계속 이동', 640, 87, 15, MUTED, True)
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
            self.text(f'레벨 {r.level} · 검기 {r.tier}단계', 105, 565, 29, GOLD)
            lines = [f'공격력 {r.attack} / 마력 {r.magic} / 최대 HP {r.max_hp} / 최대 MP {r.max_mp}',
                     f'배분: 공격 {r.spent["attack"]} · 마력 {r.spent["magic"]} · 생존 {r.spent["vitality"]} · 집중 {r.spent["focus"]}',
                     f'남은 능력치 {r.unspent} / 기술 {r.skill_points}  ·  L로 성장창',
                     f'마을 신뢰 {r.trust}/2 · 침식 {r.erosion}/3 · 기록 {len(r.records)}/3',
                     '동료: '+('루네아 · '+('부적 균열 있음' if r.fracture else '부적 온전') if r.companion else '단독 세계선'),
                     '약속: '+(' · '.join({'secret':'비밀', 'memory':'기억', 'plan':'계획'}[p] for p in r.pacts) or '아직 없음'),
                     '완전 복원 준비: '+('완료' if not r.missing_restore() else ' / '.join(r.missing_restore()))]
            for i, line in enumerate(lines):
                self.wrap(line, 105, 510-i*47, 1060, 20, MUTED, 1.35, 2)
            self.text('최근 선택', 105, 150, 18, GOLD)
            self.wrap('  →  '.join(f'{e}: {v}' for e, v in r.choices[-4:]) or '아직 기록된 선택이 없습니다.', 105, 115, 1040, 16, MUTED, 1.2, 2)
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
            self.text(ENDINGS[ending][0], 640, 128, 35, GOLD, True)
            self.wrap(ENDINGS[ending][1], 170, 81, 960, 18, CREAM, 1.4, 3)

    def draw(self):
        s = self.s
        s.hitboxes = []
        if s.run.ending:
            self.ending()
        else:
            self.world()
            self.hud()
        if s.player.hp <= 0 and not s.run.ending:
            fill(0, 0, 1280, 720, (3, 6, 15, min(230, int(s.death_age*190))))
            self.a.draw('adv/failure_respawn__failure_vision', 640, 250, None, 1.2, s.death_age)
            self.text('당신이 쓰러진 뒤, 세계는 밤에 잠겼다.', 640, 420, 31, CREAM, True)
            self.text('직전 저장 지점에서 다시 시작합니다.  ·  Enter 건너뛰기', 640, 356, 21, MUTED, True)
        if s.modal:
            self.modal()
        if s.toast_time > 0:
            bottom = 366 if s.modal else 475
            fill(170, bottom, 940, 54, (10, 21, 29, 240))
            self.wrap(s.toast, 195, bottom+36, 890, 17, GOLD, 1.2, 2)
