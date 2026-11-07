"""한 판의 진행: 실제 전투, 사건, 성장, 체크포인트, 아홉 결말을 연결한다."""
import copy
import random
from math import sin,pi
from pico2d import (
    SDL_KEYDOWN, SDL_KEYUP, SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT,
    SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN, SDLK_RETURN, SDLK_SPACE, SDLK_ESCAPE,
    SDLK_1, SDLK_8, SDLK_e, SDLK_q, SDLK_h, SDLK_l, SDLK_TAB, SDLK_c, SDLK_z, SDLK_x,
    SDLK_F9, SDLK_F1, SDLK_F7,
)
from player import Player, SHIFT
from world import World, Camera
from game_assets import Assets
from progress import Run, ENDINGS
from combat import Enemy, Companion, Shot
from sound import Sounds
from campaign_data import STAGE_LENGTH, SPAWNS, BOSSES, EVENT_TEXT, PERKS, objects
from story import CHAPTERS, INTRO, EVENT_LINES, SPEAKERS, RECORDS


class Campaign:
    def __init__(self, root, ui, store, resume=False):
        self.root, self.ui, self.store = root, ui, store
        self.assets = Assets(root / 'assets')
        self.world = World(root / 'assets/world', 1280)
        self.camera = Camera(1280, 720)
        self.player = Player(root / 'assets/hero')
        self.player.animation.add_story_clips(self.assets)
        self.run = Run()
        self.sounds = Sounds()
        self.mp = 80.0
        self.time = 0.0
        self.keys = set()
        self.modal, self.selected = None, 0
        self.toast, self.toast_time = '', 0
        self.bursts, self.numbers, self.shots, self.hazards = [], [], [], []
        self.hit_ids, self.wave_ids = set(), set()
        self.attack_hits = {}
        self.last_serial = -1
        self.slash_sound_serial=-1
        self.shield = self.hitstop = self.death_age = 0.0
        self.hybrid_time = 0.0
        self.finished_age = 0.0
        self.request = ''
        self.journal_page = self.gallery_index = self.history_index = 0
        self.developer = False
        self.actor_actions = {}
        self.interaction_age = 0.0
        self.hitboxes = []
        self.banner, self.banner_queue = None, []
        self.story_context = None
        self.rescue = None
        self.cine_out = None
        self.stage_settle=0.0
        self.ui_serial=0
        self.companion = None
        self.last_max_hp = self.run.max_hp
        point = store.restore() if resume else None
        if point:
            self.restore(point)
            self.notify('저장 지점에서 모험을 이어갑니다.')
        else:
            self.enter_stage(0)
            self.open('검을 주운 다음 날',
                      '어젯밤, 길에서 검 하나를 주웠다. 그 뒤로 마을에 낯선 짐승들이 나타났다.\n촌장님이라면 이 검을 아실까? 먼저 찾아가 보자.',
                      [('모험을 시작한다', self.close_modal)], 'portrait_hero__hero_resolve')
        self.sync_stats()
        from game_view import CampaignView
        self.view = CampaignView(self)

    def notify(self, text, seconds=3.0):
        self.toast, self.toast_time = text, seconds

    def highlight(self, image, subtitle='', duration=2.8):
        item = dict(image=image, subtitle=subtitle, age=0, duration=duration)
        if self.banner:
            self.banner_queue.append(item)
            self.banner_queue = self.banner_queue[-3:]
        else:
            self.banner = item

    def open(self, title, text, options, portrait=None, kind='dialogue', visual=None, speaker=None, focus=None, emphasis=None):
        self.ui_serial+=1
        self.toast_time = 0
        self.modal = dict(title=title, text=text, options=options, portrait=portrait, kind=kind, visual=visual)
        if kind in {'dialogue', 'boss', 'final'}:
            if self.player.attack_pending:
                self.player.attack_pending=False;self.player.mode='free';self.player.gait=None
                self.player.followups.clear();self.player.combo_queued=False
            context = self.story_context
            obj = next((o for o in self.objects if o.get('event')==context), None)
            name = speaker or SPEAKERS.get(context, '루네아' if portrait and 'lunea' in portrait else '소년')
            sx = focus if focus is not None else obj['x'] if obj else self.player.x
            if focus is None:
                if name=='루네아' and self.companion: sx=self.companion.x
                elif name=='루네아' and context=='rescue' and obj: sx=obj['x']+35
                elif name=='상인' and obj: sx=obj['x']+190
                elif name in {'소년','이야기'}: sx=self.player.x
            sx = max(self.player.x-620, min(self.player.x+620, sx))
            self.modal.update(speaker=name, speaker_x=sx, speaker_y=max(0,self.player.y)+165,
                              focus_x=(self.player.x+sx)/2, focus_y=max(0,self.player.y)+10,
                              emphasis=emphasis, revealed=False)
            if obj and obj.get('npc') and abs(sx-self.player.x)<96 and self.player.grounded:
                side = -1 if self.player.x<=sx else 1
                self.modal['step_to'] = sx+side*104
            if self.player.grounded and self.player.mode=='free':
                self.player.animation.play('idle_breathe')
                self.player.gait, self.player.previous_direction = 'idle_breathe', 0
                if abs(sx-self.player.x)>30: self.player.facing = 1 if sx>self.player.x else -1
            if self.companion and visual not in {'camp','rescue'}:
                self.companion.motion.play('lunea/idle_breathe')
            if name=='루네아' and self.companion:
                self.modal['anchor']='companion'
        self.selected = 0
        self.interaction_age = 0
        self.keys.clear()

    def close_modal(self):
        self.ui_serial+=1
        if self.modal and self.modal.get('cine'):
            self.cine_out=dict(self.modal['cine'],age=0)
            t=min(1,self.interaction_age/5);t=t*t*(3-2*t)
            start,end=self.cine_out.get('zoom',(1,1));z=max(1,start+(end-start)*t)
            self.cine_out.update(zoom=(z,z),pan=(1-t)*10)
        visual = self.modal.get('visual') if self.modal else None
        story = self.modal and self.modal['kind'] in {'dialogue','boss','final'}
        self.modal = None
        self.story_context = None
        self.keys.clear()
        if story:
            self.player.gait = None
        if visual == 'camp':
            self.player._action('adv/hero_camp__hero_stand_up')
            if self.companion:
                self.companion.motion.play('adv/lunea_camp__lunea_stand_up')

    def choose(self, index):
        if not self.modal or not 0 <= index < len(self.modal['options']):
            return
        option = self.modal['options'][index]
        if len(option) > 2 and option[2]:
            self.notify(option[2], 4)
            return
        self.sounds.play('select')
        option[1]()

    def enter_stage(self, index, x=180, checkpoint=True):
        self.run.stage = index
        self.run.unlocked = max(self.run.unlocked, index)
        self.world.set_stage(index)
        self.world.width = STAGE_LENGTH
        self.objects = objects(index)
        rng = random.Random(self.run.seed + index*997)
        self.enemies = []
        for i, (number, position) in enumerate(SPAWNS[index]):
            uid = f'{index}:enemy:{i}'
            if uid not in self.run.killed:
                self.enemies.append(Enemy(self.assets, number, position+(rng.uniform(-55, 55) if number < 16 else 0), index, uid, rng))
        self.player.x, self.player.y, self.player.vy, self.player.floor_y = x, 0.0, 0.0, 0.0
        self.player.mode, self.player.gait = 'free', None
        self.player.attack_pending=False;self.player.brake_speed=self.player.horizontal_speed=0
        self.player.combo_queued=False;self.player.followups.clear()
        self.player.forced_crouch=self.player.crouching=False
        self.player.animation.play('idle_breathe')
        self.player.effects.waves.clear()
        self.player.effects.trail = None
        self.player.effects.last_hit_state = None
        self.attack_hits.clear()
        self.player.dash_attack_remaining = 0
        self.shots, self.hazards, self.bursts, self.numbers = [], [], [], []
        self.companion = Companion(self.assets, x-90) if self.run.companion else None
        self.camera.follow(self.player, self.world.width, snap=True)
        self.banner, self.banner_queue = None, []
        self.highlight('chapter_'+str(index+1), INTRO[index])
        if checkpoint:
            self.save_checkpoint()

    def save_checkpoint(self, heal=False):
        if heal:
            self.player.hp, self.mp = self.run.max_hp, self.run.max_mp
            self.burst('lunea/fx_heal' if self.companion else 'adv/pickup_fx__pickup', self.player.x, 0, .65)
        enemies = [dict(uid=e.uid, hp=e.hp, x=e.x) for e in self.enemies if e.alive]
        self.store.save(self.run, self.player.x, self.player.y, self.player.hp, self.mp, enemies)
        if self.store.error:
            self.notify(self.store.error, 5)

    def restore(self, point):
        self.run = Run.from_dict(point['run'])
        self.last_max_hp = self.run.max_hp
        self.enter_stage(self.run.stage, point['x'], checkpoint=False)
        self.player.y = point.get('y', 0)
        self.player.floor_y=self.floor_beneath(self.player)
        self.player.forced_crouch=self.under_root(self.player.x,self.player.y)
        if self.player.forced_crouch:
            self.player.crouching=True;self.player.animation.play('crouch_idle')
        if self.companion:
            self.companion.y=self.player.y;self.companion.vy=0
            for o in self.solid_platforms():
                left,right=self.platform_span(o)
                if abs(o['y']-self.player.y)<2 and left<=self.player.x<=right:
                    self.companion.x=max(left+18,min(right-18,self.companion.x))
            self.companion.floor_y=self.floor_beneath(self.companion)
        self.player.hp, self.mp = point['hp'], point['mp']
        by_id = {e['uid']: e for e in point.get('enemies', [])}
        for enemy in self.enemies:
            if enemy.uid in by_id:
                enemy.hp, enemy.x = by_id[enemy.uid]['hp'], by_id[enemy.uid]['x']
        self.player.invulnerable = 1.5
        self.death_age, self.shield, self.hitstop = 0, 0, 0
        self.modal = None
        self.keys.clear()
        self.sync_stats()
        self.ui_serial+=1
        self.camera.follow(self.player, self.world.width, snap=True)
        self.burst('adv/failure_respawn__checkpoint_return', self.player.x, 0, .8)
        self.highlight('checkpoint', '저장했던 불빛 곁에서 다시 시작합니다')

    def sync_stats(self):
        p, r = self.player, self.run
        if r.max_hp > self.last_max_hp and p.hp > 0:
            p.hp = min(r.max_hp, p.hp+r.max_hp-self.last_max_hp)
        self.last_max_hp = r.max_hp
        p.hp = min(r.max_hp, p.hp)
        self.mp = min(r.max_mp, self.mp)
        p.dash_unlocked = r.skills.get('dash', 0) > 0
        p.magic_unlocked = r.skills.get('wave', 0) > 0
        if not self.developer:
            p.effects.level = r.tier
        p.effects.buff_duration = 5 + r.skills.get('duration', 0)*.8
        p.effects.reach_scale = 1+.07*r.skills.get('wide_slash', 0)
        p.DASH_SPEED = Player.DASH_SPEED*(1 + .055*r.skills.get('dash_distance', 0))

    def grow(self):
        if self.run.earned <= 0:
            self.notify('첫 전투를 마치고 레벨업하면 성장 방향을 고를 수 있습니다.')
            self.close_modal()
            return
        if not self.run.path:
            self.open('첫 성장 · 힘의 방향',
                      '처음 배울 기술을 고르자. 다른 기술도 나중에 배울 수 있다.\n강한 근접 공격, 멀리 날리는 검기, 두 기술의 조합 중 무엇으로 싸울까?',
                      [(label, lambda path=path: self.pick_path(path)) for path, label in [('physical', '물리 특화'), ('magic', '마법 특화'), ('balance', '균형 성장')]], kind='path')
        elif self.run.unspent:
            labels = [('attack', '공격력 +5', '대시와 근접 베기 피해 증가'), ('magic', '마력 +6', '마검파의 피해 증가'),
                      ('vitality', '최대 HP +20', '생존력 증가'), ('focus', '최대 MP +15', '마력 집중을 더 오래 활용')]
            self.open(f'능력치 배분 · 남은 {self.run.unspent}점',
                      f'공격력 {self.run.attack} · 마력 {self.run.magic}\n버튼을 누를 때마다 능력치 1점을 쓴다. 배분한 뒤에는 기술도 강화할 수 있다.',
                      [(name+' · '+tip, lambda key=key: self.allocate(key)) for key, name, tip in labels]+[('나중에 배분한다 · L로 다시 열기', self.close_modal)], kind='stats')
        elif self.run.skill_points:
            self.grow_skill()
        else:
            self.notify('배분할 포인트가 없습니다. 전투와 탐색으로 경험을 얻으세요.')
            self.close_modal()

    def pick_path(self, path):
        self.run.set_path(path)
        self.run.choose('성장 방향', {'physical': '물리 특화', 'magic': '마법 특화', 'balance': '균형 성장'}[path])
        self.sync_stats()
        self.grow()

    def allocate(self, key):
        self.run.allocate(key)
        self.sync_stats()
        if self.run.unspent:
            self.grow()
        elif self.run.skill_points:
            self.grow_skill()
        else:
            self.close_modal()

    def grow_skill(self, offset=0):
        options = []
        preferred = ['dash', 'dash_distance', 'single', 'recovery'] if self.run.path == 'physical' else ['wave', 'pierce', 'wide', 'duration'] if self.run.path == 'magic' else ['dash', 'wave', 'hybrid', 'quick']
        order = sorted(PERKS, key=lambda p: (p[0] not in preferred, preferred.index(p[0]) if p[0] in preferred else PERKS.index(p)))
        for key, title, tip, icon in order[offset:offset+4]:
            level = self.run.skills.get(key, 0)
            options.append((f'{title} Lv.{level} → {level+1} · {tip}', lambda key=key: self.pick_skill(key), '최대 단계입니다.' if level >= 6 else '', 'perk_icons__'+icon))
        options += [('다른 강화 보기', lambda: self.grow_skill((offset+4)%len(order))), ('나중에 강화한다 · L로 열기', self.close_modal)]
        self.open(f'기술 강화 · 남은 {self.run.skill_points}점', '스탯과 기술은 따로 성장한다. 대시 베기는 공격력, 마검파는 마력의 영향을 크게 받는다.', options, kind='skills')

    def pick_skill(self, key):
        if self.run.upgrade(key):
            if key == 'supply':
                self.run.shards += 2
            self.sync_stats()
        if self.run.skill_points:
            self.grow_skill()
        else:
            self.close_modal()

    def burst(self, key, x, y, scale=.5, life=None):
        if not key.startswith(('adv/', 'lunea/')):
            key = 'adv/'+key
        self.bursts.append(dict(key=key, x=x, y=y, scale=scale, age=0, life=life or self.assets.duration(key)))

    def feedback(self, x, y, number, key):
        self.sounds.play('hit')
        self.burst(key, x, y, .4)
        self.numbers.append(dict(x=x, y=y, text=str(number), age=0, hurt=False))
        self.hitstop = .025

    def damage_player(self, amount, source):
        p = self.player
        if p.hp <= 0 or p.invulnerable > 0:
            return 0
        if self.shield > 0:
            self.sounds.play('guard')
            self.shield = 0
            self.burst('lunea/fx_barrier', p.x, p.y, .6)
            p.invulnerable = .4
            return 0
        front = (source-p.x)*p.facing >= 0
        if p.mode == 'guard' and front and p.animation.name == 'guard_raise' and p.animation.elapsed <= .24:
            self.sounds.play('guard')
            p.invulnerable = .28
            self.burst('guard_fx__perfect_guard', p.x+p.facing*45, p.y+85, .55)
            self.mp = min(self.run.max_mp, self.mp+8)
            self.notify('정확한 방어 · 피해 0 / MP +8', 1.2)
            return 0
        guard = p.mode == 'guard' and front
        if p.mode == 'guard' and not front:
            p.mode = 'free'
        damage = p.take_damage(amount)
        self.sounds.play('hit')
        self.run.hits += 1
        self.burst('guard_fx__guard_hit' if guard else 'hit_impacts__hit_soft', p.x, p.y+80, .4)
        self.numbers.append(dict(x=p.x, y=p.y+140, text='-'+str(damage), age=0, hurt=True))
        return damage

    def press(self, key):
        if self.stage_settle>0:return
        p = self.player
        self.update_posture(p)
        if key == SDLK_e:
            self.interact()
            return
        if key == SDLK_h:
            if self.run.shards <= 0:
                self.notify('회복 파편이 없습니다. 상자와 쉼터를 찾아보세요.')
            elif p.hp > 0 and p.hp < self.run.max_hp:
                self.sounds.play('pickup')
                self.run.shards -= 1
                p.hp = min(self.run.max_hp, p.hp+45+8*self.run.skills.get('supply', 0))
                self.burst('pickup_fx__pickup', p.x, p.y+60, .55)
            return
        if key == SDLK_q:
            if self.companion:
                self.companion.support(self)
            else:
                self.notify('아직 함께 모험하는 동료가 없습니다.')
            return
        if key == SDLK_l:
            if self.run.earned:
                self.grow()
            else:
                self.notify('첫 전투를 마치면 성장 방향을 선택할 수 있습니다.')
            return
        if key == SDLK_z:
            cost = max(12, 24-self.run.skills.get('quick', 0)*2)
            if not p.magic_unlocked:
                self.notify('첫 성장에서 마법·균형 방향 또는 기술 강화의 마검파를 선택하세요.')
                return
            if self.mp < cost:
                self.notify('집중할 MP가 부족합니다. 잠시 회복하거나 쉼터에서 쉬세요.')
                return
            before = p.animation.serial
            p.press(key, self.keys)
            if p.animation.serial != before:
                self.sounds.play('magic')
                self.mp -= cost
                p.animation.fps *= 1 + self.run.skills.get('quick', 0)*.13
            return
        serial = p.animation.serial
        p.press(key, self.keys)
        if p.animation.serial != serial and (key == SDLK_UP or key in SHIFT):
            self.sounds.play('jump' if key == SDLK_UP else 'dash')

    def handle(self, event):
        if event.type == SDL_KEYUP:
            self.keys.discard(event.key)
            return
        if event.type==SDL_KEYDOWN and getattr(event,'repeat',0):return
        if self.stage_settle>0:return
        if self.modal:
            if self.modal['kind'] == 'journal':
                if event.type == SDL_KEYDOWN:
                    if event.key in {SDLK_ESCAPE, SDLK_TAB}:
                        self.close_modal()
                    elif event.key in {SDLK_LEFT, SDLK_RIGHT}:
                        self.journal_page = (self.journal_page+(1 if event.key == SDLK_RIGHT else -1))%4
                    elif event.key in {SDLK_UP, SDLK_DOWN, SDLK_e, SDLK_q}:
                        delta = 1 if event.key in {SDLK_DOWN, SDLK_e} else -1
                        self.gallery_index += delta
                        self.history_index += delta
                return
            if event.type in {SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN}:
                for x, y, w, h, index in self.hitboxes:
                    if x <= event.x <= x+w and y <= 720-event.y <= y+h:
                        self.selected = index
                        if event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
                            self.choose(index)
                        break
            elif event.type == SDL_KEYDOWN:
                if event.key in {SDLK_UP, SDLK_LEFT, SDLK_DOWN, SDLK_RIGHT}:
                    self.selected = (self.selected+(1 if event.key in {SDLK_DOWN, SDLK_RIGHT} else -1))%len(self.modal['options'])
                elif event.key in {SDLK_RETURN, SDLK_SPACE}:
                    if self.modal['kind'] in {'dialogue','boss','final'} and not self.modal.get('revealed') and self.interaction_age*38 < len(self.modal['text']):
                        self.modal['revealed'] = True
                    else:
                        self.choose(self.selected)
                elif SDLK_1 <= event.key <= SDLK_1+3:
                    page = self.selected//4*4
                    self.choose(page+event.key-SDLK_1)
                elif event.key == SDLK_ESCAPE and self.modal['kind'] in {'pause', 'stats', 'skills'}:
                    self.close_modal()
            return
        if event.type != SDL_KEYDOWN:
            return
        if self.run.ending:
            if event.key in {SDLK_RETURN, SDLK_SPACE} and self.finished_age > 1:
                self.result()
            return
        if self.player.hp <= 0:
            if event.key == SDLK_RETURN:
                self.death_age = 2.0
            return
        if event.key == SDLK_ESCAPE:
            self.pause()
        elif event.key == SDLK_TAB:
            self.open_journal()
        elif event.key == SDLK_F9:
            self.developer = not self.developer
            self.notify('연습 키 켜짐: 숫자 1~8 맵 / F1~F7 검기' if self.developer else '연습 키 꺼짐')
        elif SDLK_1 <= event.key <= SDLK_8:
            index = event.key-SDLK_1
            if self.developer or index <= self.run.unlocked:
                self.travel_stage(index)
            else:
                self.notify('아직 가 보지 않은 지역입니다. 오른쪽 길을 따라 진행하세요.')
        elif self.developer and SDLK_F1 <= event.key <= SDLK_F7:
            self.player.effects.level = event.key-SDLK_F1+1
        elif event.key not in self.keys:
            self.keys.add(event.key)
            self.press(event.key)

    def pause(self):
        self.open('잠시 쉬어 가기', '선택하는 동안 전투와 시간이 멈춘다. 저장은 마지막 쉼터 또는 안전한 곳에서 할 수 있다.',
                  [('계속하기', self.close_modal), ('성장 포인트 확인', self.grow), ('기록책 · 엔딩 · 이미지 도감', self.open_journal),
                   ('안전한 현재 위치 저장', self.manual_save), ('시작 화면으로 · 마지막 저장 유지', lambda: setattr(self, 'request', 'menu'))], kind='pause')

    def manual_save(self):
        if any(e.alive and abs(e.x-self.player.x) < 650 and abs(e.y-self.player.y)<220 for e in self.enemies) or any(abs(s.y-self.player.y)<180 for s in self.shots) or (self.hazards and self.player.y<180) or not self.player.grounded:
            self.notify('주변이 위험합니다. 모닥불 곁이나 적이 없는 지상에서 저장하세요.')
            return
        self.save_checkpoint()
        self.close_modal()
        self.notify('현재 위치와 선택을 저장했습니다.')

    def open_journal(self):
        self.open('모험 기록책', '', [('닫기', self.close_modal)], kind='journal')

    def obj_uid(self, obj):
        return f'{self.run.stage}:{obj["id"]}'

    def under_root(self, x, y=0):
        return any(o['kind']=='crawl' and abs(o['x']-x)<o['w']/2+22
                   and o['y']<=y<o['y']+o.get('ceiling',112) for o in self.objects)

    def update_posture(self,p):
        # 먼저 웅크려 들어가야 한다. 안에서 키를 놓아도 나올 때까지 자세를 유지한다.
        p.forced_crouch=self.under_root(p.x,p.y) and (p.crouching or p.forced_crouch or p.drop_timer>0)

    def nearest(self):
        interactable = [o for o in self.objects if o['kind'] in {'event', 'record', 'camp', 'chest', 'lever'}
                        and abs(o['x']-self.player.x) < 135 and abs(o['y']-self.player.y) < 110]
        return min(interactable, key=lambda o: abs(o['x']-self.player.x), default=None)

    def interact(self):
        if not self.player.grounded:
            self.notify('착지한 뒤 E를 눌러 살펴보세요.', 1.5)
            return
        obj = self.nearest()
        if not obj:
            self.notify('상호작용할 물건 가까이에서 E를 누르세요.')
            return
        kind, uid = obj['kind'], self.obj_uid(obj)
        if kind == 'record':
            if obj['record'] not in self.run.records:
                self.sounds.play('pickup')
                self.run.records.append(obj['record'])
                self.gain_xp(30)
                self.player._action('adv/hero_pickup__hero_reach', 'adv/hero_pickup__hero_reach_up')
                self.burst('pickup_fx__pickup', obj['x'], 85, .5)
                self.highlight('record', RECORDS[obj['record']][0])
                self.story_context = None
                self.open(RECORDS[obj['record']][0], RECORDS[obj['record']][1], [('기억하고 길을 나선다', self.close_modal)],
                          'portrait_hero__hero_think', speaker='기록의 목소리', focus=obj['x'])
            else:
                self.notify('이미 기록책에 적어 둔 문양입니다.')
        elif kind == 'chest':
            if uid not in self.run.taken:
                self.sounds.play('pickup')
                self.run.taken.append(uid)
                self.run.shards += 2
                self.gain_xp(25)
                obj['opened'] = self.time
                self.burst('pickup_fx__pickup', obj['x'], obj['y']+80, .6)
                self.notify('회복 파편 2개 · 경험치 25')
            else:
                self.notify('이 상자는 이미 열었습니다.')
        elif kind == 'lever':
            self.run.mark('gate_open')
            self.run.mark('gate_time_set')
            self.notify('성문의 사슬이 올라간다.')
            for gate in self.objects:
                if gate['kind'] == 'gate':
                    gate['opened'] = self.time
        elif kind == 'camp':
            self.camp()
        else:
            self.event(obj['event'])

    def event(self, key):
        self.story_context = key
        if key=='rescue' and not self.run.companion:
            from rescue_story import RescueStory
            self.rescue=RescueStory(self);self.rescue.start();return
        if key == 'final':
            if not self.run.has('boss_won'):
                self.notify('먼저 바르켄을 쓰러뜨려야 합니다.')
            else:
                self.final_choice()
            return
        if key == 'memory' and not self.run.companion:
            self.open('남겨진 달의 문양', '누군가의 이름을 지켜 주려는 의식이 남아 있다. 소년은 조용히 문양의 위치를 기록했다.', [('기억하고 돌아선다', self.close_modal)])
            return
        if key == 'side_seal':
            self.open(*EVENT_TEXT[key][:1], EVENT_TEXT[key][2], [('동료의 달빛으로 연다' if self.companion else '사슬의 빈틈을 살핀다', lambda: self.event_result(key, 'open'))], EVENT_TEXT[key][1])
            return
        title, portrait, text = EVENT_TEXT[key]
        text = EVENT_LINES.get(key, text)
        if self.run.has(key+'_done') and key not in {'healer', 'memory', 'rescue'}:
            self.open(title, '이곳에서 해야 할 일은 마쳤다. 이제 다음 길로 나아가자.\n지금까지의 선택은 Tab 기록책에서 다시 볼 수 있다.', [('계속 간다', self.close_modal)], portrait, speaker='이야기')
            return
        options = {
            'elder': [('충고를 듣고 출발한다', 'listen')],
            'healer': [('몸과 마력을 회복한다', 'heal'), ('다시 길을 나선다', 'leave')],
            'rescue': [('빛의 순서대로 함께 매듭을 푼다', 'careful'), ('마검으로 봉인을 잘라 구한다 · 부적에 금이 감', 'force'), ('구조 표식을 남기고 혼자 간다', 'mark')],
            'merchant': [('붕대를 나눠 상인을 돕는다', 'help'), ('봉인석의 힘을 가져간다', 'take'), ('아무것도 건드리지 않고 떠난다', 'leave')],
            'mirror': [('반사의 버릇을 기억한다', 'remember')],
            'altar': [('문양을 정화한다 · 침식 -1', 'purify'), ('힘을 흡수한다 · 침식 +1 / 경험치 +70', 'absorb')],
            'memory': [('이름을 함께 기억하고 부적을 복구한다', 'repair'), ('나중에 다시 살핀다', 'leave')],
            'envoy': [('마을에 경고를 보낸다 · 신뢰 +1', 'warn'), ('계약을 받는다 · 성문 추격 감소 / 침식 +1', 'contract'), ('계약을 거절하고 길을 연다', 'refuse')],
        }[key]
        if key == 'rescue' and self.run.companion:
            self.open('풀려난 거울 웅덩이', '아직도 물결이 조금 무섭네. 그래도 이제 혼자가 아니니까.\n가자. 네가 돌아갈 길도 함께 찾고 싶어.', [('함께 간다', self.close_modal)], 'portrait_lunea__lunea_relief')
            return
        self.open(title, text, [(label, lambda key=key, value=value: self.event_result(key, value)) for label, value in options], portrait, visual='rescue' if key == 'rescue' else 'memory' if key == 'memory' else None,
                  emphasis='choice' if key in {'rescue','merchant','altar','envoy'} else None)

    def event_result(self, key, value):
        r = self.run
        first = not r.has(key+'_done')
        r.choose(key, value)
        text, portrait = '선택이 다음 지역과 결말에 남는다.', 'portrait_hero__hero_think'
        if key == 'rescue':
            if value in {'careful', 'force'}:
                r.companion, r.fracture = True, value == 'force'
                self.companion = Companion(self.assets, self.player.x-90)
                self.companion.motion.play('adv/lunea_rescue__lunea_freed')
                r.mark('rescue_done')
                text = '“루네아.” 소녀는 자신의 이름을 되찾았다. 이제부터 길을 함께 걷는다.' + ('\n급히 끊은 봉인 때문에 부적에 균열이 남았다. 제단이나 마지막 쉼터에서 복구할 수 있다.' if r.fracture else '\n봉인을 함께 풀어 부적도 온전하게 남았다.')
                portrait = 'portrait_lunea__lunea_grateful'
                self.gain_xp(35)
                self.highlight('companion', '루네아가 함께 모험합니다 · Q 달빛 지원')
            else:
                r.mark('aid_marker')
                text = '표식은 남겼지만 동료가 합류한 것은 아니다. 되돌아와 소녀를 구하면 이후에는 동반 세계선이 된다.'
        elif key == 'merchant':
            if first and value == 'help':
                r.trust = min(2, r.trust+1)
                r.shards += 2
                self.actor_actions['merchant'] = ('adv/merchant_event__merchant_gift', self.time)
                text, portrait = '상인은 붕대를 감고 보급품을 건넸다. “마을로 돌아가면 네 이야기를 전하마.”\n회복 파편 +2 · 마을 신뢰 +1', 'portrait_npcs__merchant_thanks'
            elif first and value == 'take':
                r.erosion = min(3, r.erosion+1)
                r.mark('ward_taken')
                self.gain_xp(60)
                text = '검은 더 쉽게 휘둘러졌다. 그 뒤에서 수레의 작은 불빛이 꺼졌다. 침식 +1'
        elif key == 'altar':
            if first and value == 'purify':
                r.erosion = max(0, r.erosion-1)
                r.mark('altar_purified')
                self.gain_xp(35)
                text = '제단이 잔잔한 달빛을 되찾았다. 힘을 빼앗지 않아도 이름을 지키는 방법이 보인다.'
            elif first:
                r.erosion = min(3, r.erosion+1)
                self.gain_xp(70)
                text = '오래된 힘이 검으로 흘러들었다. 그림자는 또 조금 늦게 움직였다. 기억의 복구 기회는 남아 있다.'
        elif key == 'memory':
            if value == 'repair':
                r.fracture = False
                if 'memory' not in r.pacts:
                    r.pacts.append('memory')
                self.burst('lunea/fx_heal', self.player.x, 0, .6)
                text, portrait = '금 간 부적에 은빛 이음새가 남았다. 루네아는 잊지 않겠다는 약속을 지도에 적었다.', 'portrait_lunea__lunea_smile'
        elif key == 'envoy':
            if first and value == 'warn':
                r.trust = min(2, r.trust+1)
                r.shards += 2
                r.mark('village_warned')
                text = '마을의 등불이 차례로 켜졌다. 주민들은 대피 준비와 마지막 보급을 약속했다.'
                self.actor_actions['envoy'] = ('adv/envoy_event__envoy_warning', self.time)
            elif first and value == 'contract':
                r.erosion = min(3, r.erosion+1)
                r.mark('contract')
                text = '전령이 추격자들을 물렸다. 계약은 왕관에 대한 마지막 동의가 아니다. 왕좌 앞에서 다시 고를 수 있다.'
                for enemy in self.enemies:
                    if not enemy.boss and enemy.alive:
                        enemy.hp = 0
                        enemy.rewarded = True
                        r.killed.append(enemy.uid)
                        enemy.change('dead', enemy.key('defeat'))
        elif key == 'healer' and value == 'heal':
            self.player.hp, self.mp = r.max_hp, r.max_mp
            text = '마을의 손길로 몸과 마력이 회복됐다.'
        elif key == 'side_seal':
            r.mark('side_seal_open')
            self.burst('lunea/fx_seal', self.player.x+90, 0, .6)
            text = '측면 길이 열렸다. 회랑의 추적자 한 무리를 우회할 수 있다.'
            for enemy in self.enemies:
                if enemy.number == 11 and enemy.alive:
                    enemy.hp, enemy.rewarded = 0, True
                    r.killed.append(enemy.uid)
                    enemy.change('dead', enemy.key('defeat'))
        if key not in {'healer'} and not (key == 'rescue' and value == 'mark') and not (key == 'memory' and value == 'leave'):
            r.mark(key+'_done')
        self.sync_stats()
        result_lines = {
            ('elder','listen'): '먼저 숲길의 짐승을 물리쳐 보거라. 경험을 쌓으면 새로운 기술을 배울 수 있을 게다.\n마검의 힘을 어떻게 쓸지는 네가 정하는 거란다.',
            ('rescue','careful'): '나는 루네아야. 구해 줘서 고마워.\n네 검을 알아볼 수 있을 것 같아. 나도 함께 가게 해 줘.',
            ('rescue','force'): '고마워. 나는 루네아야. 함께 가고 싶어.\n부적에 금이 갔지만 괜찮아. 달의 제단에서 함께 고칠 수 있을 거야.',
            ('rescue','mark'): '도움을 요청하는 표식을 남겼다. 지금은 혼자 길을 나선다.\n마음이 바뀌면 이곳으로 돌아와 소녀를 구할 수 있다.',
            ('merchant','help'): '정말 고맙구나. 마을에 네 이야기를 전하마.\n이 회복 파편 두 개를 가져가렴.',
            ('merchant','take'): '검에 힘이 흘러들었다. 수레의 봉인석은 빛을 잃었다.\n힘을 얻었지만, 마을을 지키던 불빛은 하나 줄었다.',
            ('altar','purify'): '문양에 달빛이 돌아왔다. 검의 검은 기운도 잦아들었다.\n힘을 빼앗지 않고 밤을 되돌릴 방법이 있을지 모른다.',
            ('altar','absorb'): '검이 오래된 마력을 삼켰다. 더 강해졌지만 내 그림자가 낯설다.\n회랑의 쉼터에서는 이 힘을 가라앉힐 수 있다.',
            ('memory','repair'): '기억해 줘서 고마워. 부적도 다시 온전해졌어.\n마지막까지 함께 이름을 지키자.',
            ('envoy','warn'): '마을에 경고를 보냈다. 이제 주민들은 대피를 준비할 수 있다.\n남은 성채의 길은 직접 열어야 한다.',
            ('envoy','contract'): '계약으로 추격자들이 물러났다. 하지만 검의 어둠은 짙어졌다.\n왕좌에서 어떤 결정을 내릴지는 아직 나에게 달려 있다.',
            ('envoy','refuse'): '계약을 거절했다. 길은 더 험하겠지만 왕의 뜻대로 움직이지는 않겠다.\n성문의 사슬 스위치를 찾아 앞으로 가자.',
            ('mirror','remember'): '왕관 속 얼굴과 손등의 상처를 기억해 두자.\n왜 나와 똑같았는지, 폐허에 남은 기록에 답이 있을지도 몰라.',
            ('merchant','leave'): '수레는 그대로 두었다. 상인은 작은 등불을 켜고 도움을 기다린다.\n나는 숲의 문지기가 있는 길로 향한다.',
        }
        if value=='leave' and key in {'healer','memory'}:
            self.close_modal()
            return
        text = result_lines.get((key,value), text)
        self.open('길에 남은 선택', text, [('이어서 간다', self.close_modal)], portrait,
                  speaker='루네아' if key in {'rescue','memory'} and r.companion else '상인' if key=='merchant' and value=='help' else {'elder':'촌장','healer':'치유사','mirror':'소년'}.get(key,'이야기'))

    def camp(self):
        if any(e.alive and abs(e.x-self.player.x) < 650 and abs(e.y-self.player.y)<220 for e in self.enemies) or any(abs(s.y-self.player.y)<180 for s in self.shots) or (self.hazards and self.player.y<180):
            self.notify('주변의 위협을 정리한 뒤 모닥불에서 쉴 수 있습니다.')
            return
        self.save_checkpoint(heal=True)
        r = self.run
        options = [('불빛 곁에서 쉬고 출발한다 · 저장 완료', self.close_modal)]
        if r.companion:
            if 'secret' not in r.pacts:
                options.insert(0, ('검과 손등 상처의 비밀을 나눈다', lambda: self.camp_pact('secret')))
            if r.stage >= 4 and ('memory' not in r.pacts or r.fracture):
                options.insert(0, ('부적을 복구하고 함께 이름을 기억한다', lambda: self.camp_pact('memory')))
            if r.stage >= 6 and 'plan' not in r.pacts:
                options.insert(0, ('마지막 선택을 함께 계획한다', lambda: self.camp_pact('plan')))
        if r.stage >= 6 and r.erosion:
            options.insert(0, ('검의 힘을 가라앉힌다 · 침식 -1', self.calm))
        self.open('기억을 놓아두는 쉼터', '불빛 곁에서 몸과 마력이 회복됐다. 여기까지의 모험을 저장했다.\n잠시 쉬며 이야기를 나누자.' if r.companion else '불빛 곁에서 몸과 마력이 회복됐다. 여기까지의 모험을 저장했다.', options, 'portrait_lunea__lunea_smile' if r.companion else 'portrait_hero__hero_relief', visual='camp', speaker='루네아' if r.companion else '소년')

    def camp_pact(self, key):
        if key not in self.run.pacts:
            self.run.pacts.append(key)
        if key == 'memory':
            self.run.fracture = False
        self.save_checkpoint(heal=True)
        lines = {'secret': '소년은 거울 속 왕관과 손등의 상처를 숨기지 않았다. 루네아는 한 걸음 가까이 앉았다.',
                 'memory': '이름을 하나씩 되짚자 부적의 금이 은빛 선으로 이어졌다. 루네아는 자신의 길을 스스로 고르겠다고 말했다.',
                 'plan': '두 사람은 검을 사람에게 묶지 않고 문양에 돌려보내기로 했다. 모르는 선택은 함께 확인하기로 약속했다.'}
        self.open('불빛 사이의 약속', lines[key], [('잠시 더 이야기한다', self.camp), ('함께 출발한다', self.close_modal)], 'portrait_lunea__lunea_hope', visual='camp')

    def calm(self):
        self.run.erosion = max(0, self.run.erosion-1)
        self.camp()

    def final_choice(self):
        if self.player.hp <= 0:
            return
        if self.run.hidden_entry:
            self.finish('H1')
            return
        missing = self.run.missing_restore()
        self.open('왕좌 뒤의 세 갈래 빛',
                  '왕은 쓰러졌다. 이제 마검의 힘을 어디로 돌려보낼까?\n'+('밤을 온전히 되돌릴 준비가 끝났다.' if not missing else '완전한 복원에는 아직 준비가 필요하다. 기록책을 확인하거나 회랑으로 돌아갈 수 있다.'),
                  [('경계를 완전히 복원한다', lambda: self.end_choice('restore'), '부족한 준비: '+', '.join(missing) if missing else ''),
                   ('잠정 봉인 후 여행을 이어 간다', lambda: self.end_choice('journey')),
                   ('옛 달의 의식을 선택한다', lambda: self.end_choice('moon')),
                   ('밤의 왕관을 받는다 · 되돌릴 수 없는 선택', self.confirm_crown),
                   ('마지막 회랑으로 돌아가 준비를 보완한다', self.return_hall)], 'portrait_hero__hero_focus', kind='final', emphasis='final', speaker='소년')

    def confirm_crown(self):
        self.open('왕관의 무게', '힘을 모두 받아들이면 세상은 끝없는 밤에 잠긴다. 이것은 최종 엔딩으로 기록된다.',
                  [('왕관을 받는다', lambda: self.end_choice('crown')), ('다른 방법을 고른다', self.final_choice)], 'portrait_hero__hero_doubt')

    def return_hall(self):
        self.close_modal()
        self.enter_stage(6, 2800)

    def end_choice(self, choice):
        ending = self.run.resolve_ending(choice, self.player.hp > 0)
        if ending:
            self.run.choose('최종 선택', choice)
            self.finish(ending)

    def finish(self, ending):
        if self.run.ending or self.player.hp <= 0:
            return
        self.run.ending = ending
        self.finished_age = 0
        self.modal = None
        self.keys.clear()
        self.store.finish(self.run)

    def result(self):
        ending = self.run.ending
        self.open(ENDINGS[ending][0], ENDINGS[ending][1], [('새로운 세계선 시작', lambda: setattr(self, 'request', 'new')),
                  ('이번 기록과 엔딩 도감 보기', self.open_journal), ('시작 화면으로', lambda: setattr(self, 'request', 'menu'))], kind='result')

    def gain_xp(self, amount):
        count = self.run.gain_xp(amount)
        if count:
            self.sounds.play('level')
            self.sync_stats()
            self.player.hp = min(self.run.max_hp, self.player.hp+25) if self.player.hp > 0 else 0
            self.burst('levelup_fx__levelup', self.player.x, self.player.y, .8)
            self.highlight('growth', f'레벨 {self.run.level} · L을 눌러 새 힘을 선택하세요')

    def attack_player(self):
        p, r = self.player, self.run
        a = p.animation
        if a.serial != self.last_serial:
            self.last_serial = a.serial
            if a.name == 'dash_slash':
                self.hybrid_time = 4
            if a.name in p.effects.ATTACKS or 'recovery' in a.name:
                previous=a.fps
                a.fps = a.clip['fps'] * (1 + .025*r.skills.get('recovery', 0))
                a.elapsed*=previous/a.fps;a.started_at*=previous/a.fps
        state = p.effects.strike_state(p)
        if not state or p.hp <= 0:
            return
        if state['serial']==a.serial and self.slash_sound_serial!=a.serial:
            self.sounds.play('slash');self.slash_sound_serial=a.serial
        # 같은 베기의 검기·칼날·사라지는 잔상에 여러 번 닿아도 피해는 한 번이다.
        self.hit_ids = self.attack_hits.setdefault(state['serial'],set())
        self.attack_hits = {key:value for key,value in self.attack_hits.items() if key>=a.serial-8}
        coefficient = {'slash_1': 1, 'slash_2': 1.2, 'slash_3': 1.65, 'air_slash': 1.15, 'crouch_slash': .95}.get(state['name'], 1)
        damage = r.attack * coefficient * (1 + .09*r.skills.get('single', 0))
        if state['name'] == 'dash_slash':
            damage = (8 + r.attack*(1.8+.2*r.skills['dash']))*(1+.08*r.skills.get('single', 0))
        for enemy in self.enemies:
            target = enemy.hurtbox()
            touching = p.effects.melee_hits(state,target)
            if enemy.uid not in self.hit_ids and enemy.alive and touching:
                enemy.hurt(damage, state['facing'], self)
                self.hit_ids.add(enemy.uid)
        for obj in self.objects:
            uid = self.obj_uid(obj)
            if obj['kind'] not in {'crate', 'barrier', 'pillar'} or uid in r.broken or uid in self.hit_ids:
                continue
            target = (obj['x']-35,obj['y'],obj['x']+35,obj['y']+130)
            if p.effects.melee_hits(state,target):
                obj['hp'] -= damage
                self.hit_ids.add(uid)
                self.burst('hit_impacts__hit_metal', obj['x'], obj['y']+45, .4)
                if obj['hp'] <= 0:
                    r.broken.append(uid)
                    obj['broken_time'] = self.time
                    r.shards += 1
                    self.gain_xp(15)
                    if obj['kind'] == 'pillar':
                        for enemy in self.enemies:
                            if enemy.boss and enemy.alive:
                                enemy.change('hurt', enemy.key('hurt'))
                                enemy.slow = 4
                        self.notify('봉인 기둥이 무너졌다. 왕의 움직임이 잠시 멎는다.')
        p.effects.last_hit_state = state

    @staticmethod
    def overlap(a, b):
        return bool(a and b and a[0]<=b[2] and b[0]<=a[2] and a[1]<=b[3] and b[1]<=a[3])

    def update_waves(self):
        p, r = self.player, self.run
        settings = p.effects.settings['waveMotion']
        for wave in p.effects.waves:
            wave.setdefault('hit', set())
            wave.setdefault('damage', (6+r.magic*(1.45+.18*r.skills.get('wave', 0))) * (1.35 if self.hybrid_time > 0 and r.skills.get('hybrid', 0) else 1))
            wave.setdefault('size', 1+.14*r.skills.get('wide', 0))
            # 실제 픽셀 모양을 지나온 위치마다 확인해 빠른 파동도 적을 건너뛰지 않는다.
            start_age=wave.get('hit_age',0)
            for enemy in self.enemies:
                if enemy.alive and enemy.uid not in wave['hit'] and p.effects.wave_hits(wave,enemy.hurtbox(),start_age):
                    enemy.hurt(wave['damage'], wave['facing'], self)
                    wave['hit'].add(enemy.uid)
                    if len(wave['hit']) >= 1+r.skills.get('pierce', 0):
                        wave['age'] = settings['lifetime']
                        break
            wave['hit_age']=wave['age']

    def platform_span(self, o):
        c = self.assets.clips.get(o.get('visual', ''), {})
        surface = c.get('surface', {})
        scale=o['w']/c.get('frameWidth',o['w'])
        left=surface.get('left',6/scale)*scale
        right=surface.get('right',(o['w']-6)/scale)*scale
        return o['x']-o['w']/2+left,o['x']-o['w']/2+right

    def solid_platforms(self):
        result=[o for o in self.objects if o['kind']=='platform' and getattr(self,'time',0)>=o.get('disabled_until',0)]
        result += [dict(o,kind='platform',y=o['y']+o.get('roof',154),id=o.get('id','root')+'_roof')
                   for o in self.objects if o['kind']=='crawl']
        return result

    def update_terrain(self,dt):
        actors=[self.player]+([self.companion] if self.companion else [])
        for o in self.objects:
            if o['kind']!='platform': continue
            previous_x,previous_y=o['x'],o['y']
            riders=[p for p in actors if abs(p.y-previous_y)<2 and p.vy<=0 and self.platform_span(o)[0]<=p.x<=self.platform_span(o)[1]]
            motion=o.get('motion')
            if motion=='lift':
                o['y']=o['base_y']+o['travel']*(.5-.5*sin(self.time*2*pi/o['period']+pi/2))
            elif motion=='moving':
                o['x']=o['base_x']+o['travel']*sin(self.time*2*pi/o['period'])
            elif motion=='crumble':
                if self.time<o.get('disabled_until',0): continue
                o['stepped']=o.get('stepped',0)+dt if riders else max(0,o.get('stepped',0)-dt)
                if o['stepped']>.75:
                    o['disabled_until']=self.time+4;o['stepped']=0
                    self.burst('adv/hit_impacts__hit_metal',o['x'],o['y'],.35)
                    continue
            for p in riders:
                p.x+=o['x']-previous_x;p.y+=o['y']-previous_y;p.floor_y=o['y']

    def floor_beneath(self, actor):
        if getattr(actor,'drop_timer',0)>0: return 0
        return max((o['y'] for o in self.solid_platforms()
                    if self.platform_span(o)[0] <= actor.x <= self.platform_span(o)[1]
                    and abs(actor.y-o['y'])<2 and actor.vy<=0), default=0)

    def platforms(self, old_y, actor=None):
        p = self.player if actor is None else actor
        if getattr(p,'drop_timer',0)>0: return
        height=getattr(p,'collision_height',126 if getattr(p,'crouching',getattr(p,'crouched',False)) else getattr(p,'BODY_HEIGHT',150))
        for o in self.objects:
            if o['kind']=='crawl' and abs(p.x-o['x'])<o['w']/2:
                ceiling=o['y']+o.get('ceiling',112)
                if p.vy>0 and old_y+height<=ceiling and p.y+height>=ceiling:
                    p.y=ceiling-height;p.vy=0
        tops = [o for o in self.solid_platforms() if self.platform_span(o)[0] <= p.x <= self.platform_span(o)[1]]
        if p.vy <= 0:
            landed = [o for o in tops if old_y >= o['y']-1 and p.y <= o['y']]
            if landed:
                top = max(o['y'] for o in landed)
                was_air = old_y > top+2
                p.y, p.vy, p.floor_y, p.air_dash_ready = top, 0, top, True
                if was_air and p is self.player and p.mode not in {'hurt', 'dead'}:
                    p._action('air_attack_land' if p.animation.name == 'air_slash' else 'land_soft')
                elif was_air and p is not self.player:
                    p.motion.play('lunea/land_soft')

    def blockers(self, old_x, actor=None, crouched=False):
        p = self.player if actor is None else actor
        for obj in self.objects:
            if self.obj_uid(obj) in self.run.broken:
                continue
            kind = obj['kind']
            height = 65 if kind == 'cover' else 160 if kind == 'barrier' else 330 if kind == 'gate' else 0
            if kind == 'gate' and self.run.has('gate_open'):
                continue
            block = height and p.y < height-8
            radius = obj.get('w', 80)/2+20
            if kind=='crawl':
                height=getattr(p,'collision_height',126 if (crouched or getattr(p,'crouching',False) or getattr(p,'forced_crouch',False)) else getattr(p,'BODY_HEIGHT',150))
                block=p.y<obj['y']+obj.get('roof',154)-1 and p.y+height>obj['y']+obj.get('ceiling',112)
            left,right=obj['x']-radius,obj['x']+radius
            if block and (min(old_x,p.x)<right and max(old_x,p.x)>left):
                if old_x<=left:p.x=min(p.x,left)
                elif old_x>=right:p.x=max(p.x,right)
                elif kind!='crawl':p.x=old_x

    def travel_stage(self,index,x=180):
        """지역을 바꾼 직후 잠깐 멈춰 교차 전환을 읽을 시간을 준다."""
        self.keys.clear();self.enter_stage(index,x);self.stage_settle=.65

    def exit_ready(self):
        boss = BOSSES.get(self.run.stage)
        return (boss is None or not any(e.alive and e.number == boss for e in self.enemies)) and (self.run.stage != 5 or self.run.has('gate_open'))

    def update(self, dt):
        self.time += dt
        if self.stage_settle>0:
            self.stage_settle=max(0,self.stage_settle-dt)
            return
        if self.cine_out:
            self.cine_out['age']+=dt
            if self.cine_out['age']>.6:self.cine_out=None
        self.toast_time = max(0, self.toast_time-dt)
        for b in self.bursts:
            b['age'] += dt
        self.bursts = [b for b in self.bursts if b['age'] < b['life']]
        for n in self.numbers:
            n['age'] += dt
        self.numbers = [n for n in self.numbers if n['age'] < .8]
        for key, (clip, start) in list(self.actor_actions.items()):
            if self.time-start > self.assets.duration(clip)+1:
                del self.actor_actions[key]
        if self.run.ending:
            self.finished_age += dt
            if not self.modal and self.finished_age > (12 if self.run.ending == 'H1' else 5):
                self.result()
            return
        if self.modal:
            self.interaction_age += dt
            if self.modal['kind'] in {'dialogue','boss','final'}:
                if 'step_to' in self.modal:
                    p=self.player
                    dx=self.modal['step_to']-p.x
                    if abs(dx)>1:
                        p.x += max(-130*dt,min(130*dt,dx))
                        p.facing = 1 if dx>0 else -1
                        if p.animation.name!='walk': p.animation.play('walk')
                    else:
                        del self.modal['step_to']
                        p.facing=1 if self.modal['speaker_x']>p.x else -1
                        p.animation.play('idle_breathe')
                        p.gait='idle_breathe'
                self.player.animation.update(dt)
                if self.companion:
                    self.companion.update(dt, self, cinematic=True)
                    if self.modal.get('anchor')=='companion':
                        self.modal['speaker_x']=self.companion.x
                        self.modal['speaker_y']=self.companion.y+175
                        self.modal['focus_x']=(self.player.x+self.companion.x)/2
                self.camera.focus(self.modal['focus_x'], self.modal['focus_y'], self.world.width, dt,self.modal.get('shot_zoom',1.18))
            else:
                self.camera.follow(self.player, self.world.width, dt)
            return
        if self.banner:
            self.banner['age'] += dt
            if self.banner['age'] >= self.banner['duration']:
                self.banner = self.banner_queue.pop(0) if self.banner_queue else None
        p, r = self.player, self.run
        if p.hp <= 0:
            if self.death_age == 0:
                self.sounds.play('death')
            p.animation.update(dt)
            self.death_age += dt
            if self.death_age >= 2:
                point = self.store.restore()
                if point:
                    self.restore(point)
                    self.notify('직전 저장 지점으로 돌아왔다. 저장 이후의 선택과 보상도 함께 되돌아간다.', 4)
            return
        if self.hitstop > 0:
            self.hitstop = max(0, self.hitstop-dt)
            return
        r.seconds += dt
        self.shield = max(0, self.shield-dt)
        self.hybrid_time = max(0, self.hybrid_time-dt)
        self.mp = min(r.max_mp, self.mp+dt*(7 if p.mode == 'free' else 2.5))
        self.update_terrain(dt)
        old_x,old_y=p.x,p.y
        p.floor_y = self.floor_beneath(p)
        self.update_posture(p)
        p.update(dt, self.keys)
        self.platforms(old_y)
        self.blockers(old_x)
        for o in self.objects:
            if o['kind']=='spring' and abs(p.x-o['x'])<52 and p.mode=='jump' and p.jump_launched and p.y<55 and p.vy>300 and self.time>=o.get('next_bounce',0):
                p.vy=1160;p.floor_y=0;p.mode='free';p.gait=None;p.air_dash_ready=True
                o['next_bounce']=self.time+1
                self.sounds.play('jump')
                self.burst('adv/pickup_fx__pickup',o['x'],0,.5)
            elif o['kind']=='crystal' and self.obj_uid(o) not in r.taken and abs(p.x-o['x'])<42 and abs(p.y+65-o['y'])<65:
                r.taken.append(self.obj_uid(o));self.mp=min(r.max_mp,self.mp+12)
                self.gain_xp(28);self.sounds.play('pickup')
                self.burst('adv/pickup_fx__pickup',o['x'],o['y'],.3)
        p.x = max(75, min(self.world.width-75, p.x))
        boss = next((e for e in self.enemies if e.boss and e.alive and abs(e.x-p.x)<620), None)
        if boss and p.grounded and p.mode=='free' and not r.has('met_boss_'+str(boss.number)):
            r.mark('met_boss_'+str(boss.number))
            lines = {16:'뿌리가 길을 막아섰다. 숲의 문지기를 넘어야 성채로 갈 수 있다.',
                     17:'이름을 지우는 파수자다. 공격 전 바닥에 생기는 문양을 보자.',
                     18:'성문의 기사가 검을 들었다. 돌진이 끝난 뒤의 빈틈을 노리자.',
                     19:'마지막 문지기다. 이 길을 넘으면 더는 왕좌를 피할 수 없다.',
                     20:'마침내 왔구나. 그 검과 함께 쌓아 온 힘… 모두 내게 보여라.'}
            self.open(boss.actor['name'], lines[boss.number], [('맞선다', self.close_modal)],
                      'portrait_hero__hero_focus', kind='boss', focus=boss.x,
                      speaker='바르켄' if boss.number==20 else '소년', emphasis='boss')
            if boss.number != 20:
                self.modal['speaker_x'] = p.x
            return
        self.attack_player()
        self.update_waves()
        for enemy in self.enemies:
            enemy.update(dt, self)
            if enemy.defeated and not enemy.rewarded:
                enemy.rewarded = True
                if enemy.uid not in r.killed:
                    r.killed.append(enemy.uid)
                    r.kills += 1
                    r.shards += 1 if enemy.boss else 0
                    self.gain_xp(140+30*r.stage if enemy.boss else 24+8*r.stage)
                    if enemy.boss:
                        self.highlight('victory', enemy.actor['name']+'을 넘어섰다')
        for shot in self.shots:
            shot.update(dt)
            for obj in self.objects:
                if obj['kind'] == 'cover' and abs(shot.x-obj['x']) < obj.get('w', 100)/2 and 0 < shot.y < obj.get('h', 72):
                    shot.age = shot.life
                    self.burst('hit_impacts__hit_metal', shot.x, shot.y, .3)
            if not shot.dead and abs(shot.x-p.x) < shot.radius+20 and p.y+15 < shot.y+shot.radius and shot.y-shot.radius < p.y+p.collision_height:
                self.damage_player(shot.damage, shot.x)
                shot.age = shot.life
                kind = 'spore_burst' if 'spore' in shot.key else 'paper_break' if 'paper' in shot.key else 'thread_snap' if 'needle' in shot.key else 'night_impact'
                self.burst('projectile_impacts__'+kind, shot.x, shot.y, .4)
        self.shots = [s for s in self.shots if not s.dead and -100 < s.x < self.world.width+100]
        for hazard in self.hazards:
            hazard['age'] += dt
            if hazard['age'] >= hazard['wait'] and not hazard['hit']:
                hazard['hit'] = True
                self.burst('root_spike__root_spike' if hazard['kind'] == 'root' else 'seal_warning__seal_burst', hazard['x'], 0, .65)
                if abs(p.x-hazard['x']) < hazard['radius'] and p.y < 125:
                    self.damage_player(hazard['damage'], hazard['x'])
        self.hazards = [h for h in self.hazards if h['age'] < h['life']]
        if self.companion:
            self.companion.update(dt, self)
        for obj in self.objects:
            if obj['kind'] == 'hazard' and abs(p.x-obj['x']) < 320 and int(self.time)%6 == 0 and not self.hazards:
                self.hazards.append(dict(x=obj['x'], y=0, age=0, wait=1, life=2, hit=False, kind='rock', damage=18, radius=70))
            if obj['kind'] == 'wind' and abs(p.x-obj['x']) < obj['w']/2 and p.y < 140:
                p.x += dt*35
        # 동시에 쓰러지면 승리 연출보다 HP 0의 재도전을 먼저 처리한다.
        if p.hp <= 0:
            self.keys.clear()
            return
        if self.run.stage == 7 and not any(e.alive or e.age < .9 for e in self.enemies) and not r.has('boss_won'):
            r.mark('boss_won')
            self.save_checkpoint()
            self.final_choice()
            return
        if not r.path and r.level >= 2:
            self.grow()
            return
        if p.x >= self.world.width-110 and r.stage < 7:
            if self.exit_ready():
                self.travel_stage(r.stage+1)
            else:
                p.x = self.world.width-115
                self.notify('길이 막혀 있다. 파수자를 쓰러뜨리고, 성문이라면 사슬 스위치를 찾아보자.', 2)
        elif p.x <= 85 and r.stage > 0:
            self.travel_stage(r.stage-1, self.world.width-210)
        self.sync_stats()
        proximity=max((max(0,min(1,(900-abs(e.x-p.x))/500)) for e in self.enemies if e.alive and e.boss),default=0)
        self.camera.follow(p, self.world.width, dt,combat_wide=proximity)

    def draw(self):
        self.view.draw()

    def close(self):
        self.sounds.close()
