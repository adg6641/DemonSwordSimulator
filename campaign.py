"""한 판의 진행: 실제 전투, 사건, 성장, 체크포인트, 아홉 결말을 연결한다."""
import copy
import random
from math import sin,pi
from pico2d import (
    SDL_KEYDOWN, SDL_KEYUP, SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN, SDL_BUTTON_LEFT,
    SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN, SDLK_RETURN, SDLK_SPACE, SDLK_ESCAPE,
    SDLK_1, SDLK_8, SDLK_e, SDLK_q, SDLK_h, SDLK_l, SDLK_TAB, SDLK_c, SDLK_z, SDLK_x,
    SDLK_F9, SDLK_F1, SDLK_F7,
    SDL_TEXTINPUT,SDL_TEXTEDITING,SDL_StartTextInput,SDL_StopTextInput,SDL_SetTextInputRect,
    SDL_Rect,SDLK_BACKSPACE,SDLK_v,KMOD_CTRL,SDL_GetClipboardText,
)
from player import Player, SHIFT, MOVING_LANDINGS
from world import World, Camera
from game_assets import Assets
from progress import Run, ENDINGS
from combat import Enemy, Companion, Shot
from sound import Sounds
from campaign_data import SPAWNS, BOSSES, PAGES, PAGE_WIDTH, PLATFORM_ROUTES, EVENT_TEXT, PERKS, page_objects
from story import CHAPTERS, INTRO, EVENT_LINES, SPEAKERS, RECORDS
from naming import NameEntry


STAGE_AMBIENCE = ('village', 'forest', 'deep', 'ruins', 'shrine', 'gate', 'corridor', 'throne')
SWING_SOUNDS = {
    'slash_1': 'swing_1', 'slash_2': 'swing_2', 'slash_3': 'swing_3',
    'air_slash': 'swing_air', 'crouch_slash': 'swing_low', 'dash_slash': 'swing_dash',
}
STORY_SOUNDS = {
    ('rescue', 'careful'): 'companion_join', ('rescue', 'force'): 'companion_join',
    ('merchant', 'help'): 'merchant', ('merchant', 'take'): 'absorb',
    ('altar', 'purify'): 'purify', ('altar', 'absorb'): 'absorb',
    ('memory', 'repair'): 'purify', ('envoy', 'warn'): 'pact',
    ('envoy', 'contract'): 'absorb', ('healer', 'heal'): 'heal',
    ('mirror', 'remember'): 'record', ('side_seal', 'open'): 'seal_break',
}
MENU_SOUNDS = {'journal': 'ui_page', 'pause': 'ui_open', 'pause_menu': 'ui_open',
               'stats': 'ui_open', 'skills': 'ui_open', 'path': 'ui_open'}


class Campaign:
    def __init__(self, root, ui, store, resume=False, *, sounds=None):
        self.root, self.ui, self.store = root, ui, store
        self.assets = Assets(root / 'assets')
        self.world = World(root / 'assets/world', 1280)
        self.camera = Camera(1280, 720)
        self.player = Player(root / 'assets/hero')
        self.player.animation.add_story_clips(self.assets)
        self.player.animation.preload()
        self.player.effects.preload()
        self.assets.lunea_atlas.preload()
        self.run = Run()
        self.owns_sounds = sounds is None
        self.sounds = sounds if sounds is not None else Sounds(root / 'assets/audio')
        self.foot_contact = None
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
        self.damage_flash = 0.0
        self.magic_cooldown = 0.0
        self.contact_target = None
        self.hybrid_time = 0.0
        self.finished_age = 0.0
        self.request = ''
        self.journal_page = self.history_index = 0
        self.developer = False
        self.actor_actions = {}
        self.interaction_age = 0.0
        self.hitboxes = []
        self.banner, self.banner_queue = None, []
        self.story_context = None
        self.rescue = None
        self.cine_out = None
        self.stage_settle=0.0
        self.door_entry=None
        self.pending_event=None
        self.opened_final=False
        self.ui_serial=0
        self.companion = None
        self.last_max_hp = self.run.max_hp
        point = store.restore() if resume else None
        if point:
            self.restore(point)
            self.notify('저장 지점에서 모험을 이어갑니다.')
        else:
            self.enter_stage(0)
            self.talk([('소년','검을 주운 뒤로 짐승들이 날 따라와.'),
                       ('소년','촌장님께 이 검을 보여 드려야겠어.')],
                      [('출발',self.close_modal)])
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
        previous = self.modal
        self.modal = dict(title=title, text=text, options=options, portrait=portrait, kind=kind, visual=visual)
        self.sounds.set_context(quiet=True, camp=visual == 'camp')
        if kind == 'boss':
            self.sounds.play('boss_warn')
        elif kind == 'final':
            self.sounds.play('story_turn')
        elif kind == 'dialogue':
            self.sounds.play('dialogue', gain=.65 if previous else 1.0)
        elif kind in MENU_SOUNDS:
            self.sounds.play(MENU_SOUNDS[kind])
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
                elif name=='상인' and obj: sx=obj.get('actor_x',obj['x'])
                elif name in {'소년','이야기'}: sx=self.player.x
            sx = max(self.player.x-620, min(self.player.x+620, sx))
            label=self.run.display_name if name=='소년' else name
            self.modal.update(speaker=label, speaker_x=sx, speaker_y=max(0,self.player.y)+165,
                              focus_x=(self.player.x+sx)/2, focus_y=max(0,self.player.y)+10,
                              emphasis=emphasis, revealed=False)
            if obj and obj.get('npc') and abs(sx-self.player.x)<96 and self.player.grounded:
                side = -1 if self.player.x<=sx else 1
                self.modal['step_to'] = sx+side*104
            continuing_camp = visual=='camp' and previous and previous.get('visual')=='camp'
            if self.player.grounded and self.player.mode=='free' and not continuing_camp:
                self.player.animation.play('idle_breathe')
                self.player.gait, self.player.previous_direction = 'idle_breathe', 0
                if abs(sx-self.player.x)>30: self.player.facing = 1 if sx>self.player.x else -1
            if self.companion and visual not in {'camp','rescue'}:
                self.companion.motion.play('lunea/idle_breathe')
            if name=='루네아' and self.companion:
                self.modal['anchor']='companion'
        if visual == 'camp':
            self.setup_camp_pose(previous)
        self.selected = 0
        self.interaction_age = 0
        self.keys.clear()

    @property
    def region(self):
        return PAGES[self.run.stage][self.run.page]

    @property
    def story_only(self):
        return self.region in {'rescue','merchant'}

    def setup_camp_pose(self, previous):
        player = self.player
        if previous and previous.get('visual')=='camp':
            seats = previous['camp_seats']
        else:
            fire = min((obj for obj in self.objects if obj['kind']=='camp'),
                       key=lambda obj: abs(obj['x']-player.x)+abs(obj['y']-player.y)*2,
                       default=None)
            x,y = (fire['x'],fire['y']) if fire else (player.x+108,player.y)
            facing = 1 if player.x<=x else -1
            seats = (x-facing*112, x+facing*111, y, facing)
            self.camp_age = 0.0
            player.animation.play('adv/hero_camp__hero_sit_down')
        hx,lx,y,facing=seats
        speaker_x = lx if self.modal['speaker']=='루네아' and self.companion else hx
        self.modal.update(camp_seats=seats, speaker_x=speaker_x, speaker_y=y+122,
                          focus_x=(hx+lx)/2,focus_y=y+15)

    def close_modal(self):
        if self.modal and self.modal.get('name_entry'):
            SDL_StopTextInput()
        self.ui_serial+=1
        if self.modal and self.modal.get('cine'):
            self.cine_out=dict(self.modal['cine'],age=0)
            t=min(1,self.interaction_age/5);t=t*t*(3-2*t)
            start,end=self.cine_out.get('zoom',(1,1));z=max(1,start+(end-start)*t)
            self.cine_out.update(zoom=(z,z),pan=(1-t)*10)
        visual = self.modal.get('visual') if self.modal else None
        story = self.modal and self.modal['kind'] in {'dialogue','boss','final'}
        seats = self.modal.get('camp_seats') if visual == 'camp' else None
        self.modal = None
        self.sounds.set_context()
        self.story_context = None
        self.keys.clear()
        if story:
            self.player.gait = None
        if seats:
            hx,lx,y,facing=seats
            player=self.player
            frame=player.animation.frame
            t=min(1,self.camp_age/.36)
            t=t*t*(3-2*t)
            player.x,player.y,player.floor_y,player.facing=player.x+(hx-player.x)*t,y,y,facing
            player._action('adv/hero_camp__hero_stand_up', start_frame=player.animation.clip['frameCount']-1-frame)
            if self.companion:
                companion=self.companion
                companion.x,companion.y,companion.floor_y,companion.facing=lx,y,y,-facing
                companion.ground_speed=0
                companion.motion.play('adv/lunea_camp__lunea_stand_up')

    def choose(self, index):
        if not self.modal or not 0 <= index < len(self.modal['options']):
            return
        option = self.modal['options'][index]
        if len(option) > 2 and option[2]:
            self.sounds.play('ui_lock')
            self.notify(option[2], 4)
            return
        self.sounds.play('ui_accept')
        option[1]()

    def talk(self, lines, options, *, title='', portrait=None, visual=None):
        """짧은 말을 인물별 말풍선으로 잇고 마지막에만 선택한다."""
        def advance(index):
            speaker,text=lines[index]
            buttons=options if index==len(lines)-1 else [('계속',lambda:advance(index+1))]
            approach=self.modal.get('step_to') if self.modal else None
            self.open(title or speaker,text,buttons,portrait,speaker=speaker,visual=visual)
            if approach is not None:self.modal['step_to']=approach
        advance(0)

    def enter_stage(self, index, x=180, checkpoint=True, *, page=0, y=0):
        self.run.stage = index
        self.run.page = page
        self.run.unlocked = max(self.run.unlocked, index)
        self.world.set_stage(index)
        self.world.width = PAGE_WIDTH[self.region]
        self.sounds.clear_scene_events()
        self.sounds.set_scene(self.region if self.story_only else STAGE_AMBIENCE[index])
        self.foot_contact = None
        self.objects = page_objects(index, page)
        self.door_entry = self.pending_event = None
        self.opened_final = False
        self.actor_actions.clear()
        self.cine_out = None
        rng = random.Random(self.run.seed + index*997)
        self.enemies = []
        for i, (number, position) in enumerate(SPAWNS[index]):
            if self.story_only or (number==BOSSES.get(index)) != (self.region=='boss'):
                continue
            uid = f'{index}:enemy:{i}'
            if uid not in self.run.killed:
                self.enemies.append(Enemy(self.assets, number, 1230 if self.region=='boss' else position+rng.uniform(-55,55), index, uid, rng))
        if self.region=='explore' and index:
            left,right = PLATFORM_ROUTES[index]
            regular=[number for number,_ in SPAWNS[index] if number!=BOSSES.get(index)]
            for n,(number,slot) in enumerate(zip(regular,(left[2],right[3]))):
                uid=f'{index}:upper:{n}'
                if uid in self.run.killed:
                    continue
                px,py,width=slot
                enemy=Enemy(self.assets,number,px,index,uid,rng)
                enemy.perch=(px-width/2+27,px+width/2-27,py)
                enemy.y+=py
                self.enemies.append(enemy)
        self.player.x, self.player.y, self.player.vy, self.player.floor_y = x, y, 0.0, y
        self.player.air_dash_ready = True
        self.player.drop_timer = 0.0
        self.player.mode, self.player.gait = 'free', None
        self.player.attack_pending=False;self.player.brake_speed=self.player.horizontal_speed=0
        self.player.combo_queued=False;self.player.followups.clear()
        self.player.forced_crouch=self.player.crouching=False
        self.player.previous_direction=self.player.move_time=0
        self.player.last_ground_y=self.player.flight_origin_y=self.player.flight_peak_y=y
        self.player.in_flight=False
        self.player.animation.play('idle_breathe')
        self.player.effects.waves.clear()
        self.player.effects.bursts.clear()
        self.player.effects.trail = None
        self.player.effects.clear_blade_trail()
        self.player.effects.last_hit_state = None
        self.attack_hits.clear()
        self.contact_target=None
        self.hitstop=self.damage_flash=0
        self.player.dash_attack_remaining = 0
        self.shots, self.hazards, self.bursts, self.numbers = [], [], [], []
        self.companion = Companion(self.assets, x-90) if self.run.companion else None
        if self.companion:
            self.companion.y=self.companion.floor_y=y
        self.camera.follow(self.player, self.world.width, snap=True)
        self.banner, self.banner_queue = None, []
        if page==0:
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
        x,y = point['x'],point.get('y',0)
        if 'page' not in point['run'] and self.run.page:
            x,y = 1450,0
        self.enter_stage(self.run.stage, x, checkpoint=False, page=self.run.page,y=y)
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
                enemy.keep_on_perch()
        self.player.invulnerable = 1.5
        self.death_age, self.shield, self.hitstop = 0, 0, 0
        self.modal = None
        self.keys.clear()
        self.sync_stats()
        if self.story_only:
            self.pending_event=self.region
        self.ui_serial+=1
        self.camera.follow(self.player, self.world.width, snap=True)
        self.sounds.play('respawn')
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
            p.effects.set_level(r.tier)
        p.effects.buff_duration = 5 + r.skills.get('duration', 0)*.8
        p.effects.reach_scale = 1+.07*r.skills.get('wide_slash', 0)
        p.DASH_DISTANCE = Player.DASH_DISTANCE + 4*r.skills.get('dash_distance', 0)

    def grow(self):
        if self.run.unspent <= 0:
            self.notify('2레벨에 첫 성장, 이후 10레벨마다 골라요.')
            self.close_modal()
            return
        self.run.growth_offered=self.run.level
        self.open('성장 방향', '하나만 고르면 기술과 능력치가 함께 올라요.',
                  [('검술 · 대시 베기 + 공격력 + HP',lambda:self.pick_bundle('physical')),
                   ('마법 · 마검파 + 마력 + MP',lambda:self.pick_bundle('magic')),
                   ('균형 · 두 기술 + 고른 능력치',lambda:self.pick_bundle('balance'))],kind='path')

    def pick_bundle(self, path):
        if self.run.choose_bundle(path):
            self.sounds.play('skill')
            self.run.choose('성장 묶음',path)
            self.sync_stats()
        self.close_modal()

    def burst(self, key, x, y, scale=.5, life=None):
        if not key.startswith(('adv/', 'lunea/')):
            key = 'adv/'+key
        self.bursts.append(dict(key=key, x=x, y=y, scale=scale, age=0, life=life or self.assets.duration(key)))

    def sound_at(self, name, x, y, *, gain=1.0):
        p = self.player
        self.sounds.at(name, x - p.x, y - p.y, gain=gain)

    def surface(self):
        if self.player.floor_y > 1:
            return 'wood' if self.run.stage < 3 else 'stone'
        return 'earth' if self.run.stage < 3 else 'stone'

    def footstep(self, distance):
        p = self.player
        animation = p.animation
        if not p.grounded or animation.name not in {'walk', 'run', 'crouch_walk'} | MOVING_LANDINGS:
            self.foot_contact = None
            return
        if abs(distance) < .1:
            return
        contact = (animation.serial, int(animation.elapsed / animation.duration * 2))
        if contact != self.foot_contact:
            self.foot_contact = contact
            gain = {'run': 1, 'crouch_walk': .46}.get(animation.name, .7)
            self.sounds.play('step_' + self.surface(), gain=gain)

    def feedback(self, x, y, number, key, *, magic=False):
        sound = 'wave_hit' if magic else 'hit_metal' if key.endswith('_metal') else 'hit_flesh'
        self.sound_at(sound, x, y)
        self.player.effects.burst('impact',x,y,self.player.facing)
        self.numbers.append(dict(x=x, y=y, text=str(number), age=0, hurt=False))
        if not magic:
            self.hitstop = max(self.hitstop, {
                'slash_1': .060, 'slash_2': .074, 'slash_3': .095, 'dash_slash': .085,
            }.get(self.player.animation.name, .050))

    def keep_attack_distance(self, old_x):
        """베기는 닿는 거리에서 멈춘다. 적의 몸 안으로 전진하지 않는다."""
        p=self.player
        attacking=p.mode=='combo' or p.animation.name=='dash_slash' and p.mode=='action'
        if not attacking:
            self.contact_target=None
            return
        advance=(p.x-old_x)*p.facing
        if advance <= 0:
            return
        boxes=[enemy.hurtbox() for enemy in self.enemies if enemy.alive]
        boxes.extend((obj['x']-35,obj['y'],obj['x']+35,obj['y']+130)
                     for obj in self.objects if obj['kind'] in {'crate','barrier','pillar'}
                     and self.obj_uid(obj) not in self.run.broken)
        allowed=advance
        for left,bottom,right,top in boxes:
            edge=left if p.facing>0 else right
            distance=(edge-old_x)*p.facing
            if distance < 0 or bottom>p.y+p.collision_height or top<p.y+12:
                continue
            gap=46
            contact=self.contact_target
            if contact:
                enemy=contact.get('enemy')
                obj=contact.get('obj')
                contact_box=enemy.hurtbox() if enemy and enemy.alive else (
                    (obj['x']-35,obj['y'],obj['x']+35,obj['y']+130) if obj else None)
                if contact_box==(left,bottom,right,top):
                    if 'gap' not in contact:
                        contact['gap']=max(46,min(106,distance))
                    gap=contact['gap']
            allowed=min(allowed,max(0,distance-gap))
        p.x=old_x+p.facing*allowed

    def damage_player(self, amount, source):
        p = self.player
        if p.hp <= 0 or p.invulnerable > 0:
            return 0
        if self.shield > 0:
            self.sounds.play('moon_impact')
            self.shield = 0
            self.burst('lunea/fx_barrier', p.x, p.y, .6)
            p.invulnerable = .4
            return 0
        front = (source-p.x)*p.facing >= 0
        if p.mode == 'guard' and front and p.animation.name == 'guard_raise' and p.animation.elapsed <= .24:
            self.sounds.play('parry')
            p.invulnerable = .28
            p.animation.play('guard_impact')
            self.guard_sparks()
            self.mp = min(self.run.max_mp, self.mp+8)
            self.notify('정확한 방어 · 피해 0 / MP +8', 1.2)
            return 0
        guard = p.mode == 'guard' and front
        if p.mode == 'guard' and not front:
            p.mode = 'free'
        damage = p.take_damage(amount)
        self.damage_flash = .32
        self.hitstop = max(self.hitstop,.055 if guard else .080)
        if p.hp > 0:
            self.sounds.play('guard' if guard else 'hurt_player')
        self.run.hits += 1
        if guard and p.hp > 0:
            self.guard_sparks()
        else:
            p.effects.burst('damage', p.x, p.y + 80, p.facing)
        self.numbers.append(dict(x=p.x, y=p.y+140, text='-'+str(damage), age=0, hurt=True))
        return damage

    def guard_sparks(self):
        p = self.player
        blade = p.animation.weapon_pose
        hand, tip = blade['hand'], blade['tip']
        x = hand[0] + (tip[0] - hand[0]) * .36
        y = hand[1] + (tip[1] - hand[1]) * .36
        p.effects.burst('guard', p.x + p.facing * x, p.y - y, p.facing)

    def press(self, key):
        if self.stage_settle>0 or self.door_entry:return
        p = self.player
        self.update_posture(p)
        if key == SDLK_e:
            self.interact()
            return
        if key == SDLK_h:
            if self.run.shards <= 0:
                self.sounds.play('ui_lock')
                self.notify('회복 파편이 없습니다. 상자와 쉼터를 찾아보세요.')
            elif p.hp > 0 and p.hp < self.run.max_hp:
                self.sounds.play('heal')
                self.run.shards -= 1
                p.hp = min(self.run.max_hp, p.hp+45+8*self.run.skills.get('supply', 0))
                self.burst('pickup_fx__pickup', p.x, p.y+60, .55)
            return
        if key == SDLK_q:
            if self.companion:
                self.companion.support(self)
            else:
                self.sounds.play('ui_lock')
                self.notify('아직 함께 모험하는 동료가 없습니다.')
            return
        if key == SDLK_l:
            if self.run.earned:
                self.grow()
            else:
                self.sounds.play('ui_lock')
                self.notify('2레벨에 첫 성장, 이후 10레벨마다 선택해요.')
            return
        if key == SDLK_z:
            cost = max(12, 24-self.run.skills.get('quick', 0)*2)
            if not p.magic_unlocked:
                self.sounds.play('ui_lock')
                self.notify('성장 방향에서 마법이나 균형을 고르면 쓸 수 있어요.')
                return
            if self.magic_cooldown > 0:
                return
            if self.mp < cost:
                self.sounds.play('ui_lock')
                self.notify('집중할 MP가 부족합니다. 잠시 회복하거나 쉼터에서 쉬세요.')
                return
            before = p.animation.serial
            p.press(key, self.keys)
            if p.animation.serial != before:
                self.sounds.play('magic_charge')
                self.mp -= cost
                self.magic_cooldown = 7.0
                p.animation.fps *= 1 + self.run.skills.get('quick', 0)*.13
            return
        serial = p.animation.serial
        p.press(key, self.keys)
        if p.animation.serial != serial and key in SHIFT and p.mode == 'dash':
            self.sounds.play('dash_air' if p.animation.name == 'dash_air' else 'dash_ground')

    def handle(self, event):
        if self.modal and self.modal.get('name_entry'):
            self.handle_name(event)
            return
        if event.type == SDL_KEYUP:
            self.keys.discard(event.key)
            return
        if event.type==SDL_KEYDOWN and getattr(event,'repeat',0):return
        if self.stage_settle>0 or self.door_entry:return
        if self.modal:
            if self.modal['kind'] == 'journal':
                if event.type == SDL_KEYDOWN:
                    if event.key in {SDLK_ESCAPE, SDLK_TAB}:
                        self.sounds.play('ui_back')
                        self.close_modal()
                    elif event.key in {SDLK_LEFT, SDLK_RIGHT}:
                        self.sounds.play('ui_page')
                        self.journal_page = (self.journal_page+(1 if event.key == SDLK_RIGHT else -1))%3
                    elif self.journal_page==1 and event.key in {SDLK_UP,SDLK_DOWN}:
                        self.sounds.play('ui_page')
                        self.history_index += 1 if event.key==SDLK_DOWN else -1
                return
            if event.type in {SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN}:
                for x, y, w, h, index in self.hitboxes:
                    if x <= event.x <= x+w and y <= 720-event.y <= y+h:
                        if self.selected != index and event.type == SDL_MOUSEMOTION:
                            self.sounds.play('ui_move')
                        self.selected = index
                        if event.type == SDL_MOUSEBUTTONDOWN and event.button == SDL_BUTTON_LEFT:
                            self.choose(index)
                        break
            elif event.type == SDL_KEYDOWN:
                if event.key in {SDLK_UP, SDLK_LEFT, SDLK_DOWN, SDLK_RIGHT}:
                    if len(self.modal['options']) > 1:
                        self.sounds.play('ui_move')
                    self.selected = (self.selected+(1 if event.key in {SDLK_DOWN, SDLK_RIGHT} else -1))%len(self.modal['options'])
                elif event.key in {SDLK_RETURN, SDLK_SPACE}:
                    self.choose(self.selected)
                elif SDLK_1 <= event.key <= SDLK_1+2:
                    self.choose(event.key-SDLK_1)
                elif event.key == SDLK_ESCAPE and self.modal['kind'] in {'pause','pause_menu','stats','skills'}:
                    self.sounds.play('ui_back')
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
                self.sounds.play('ui_lock')
                self.notify('아직 가 보지 않은 지역입니다. 오른쪽 길을 따라 진행하세요.')
        elif self.developer and SDLK_F1 <= event.key <= SDLK_F7:
            self.player.effects.set_level(event.key-SDLK_F1+1)
        elif event.key not in self.keys:
            self.keys.add(event.key)
            self.press(event.key)

    def pause(self):
        self.open('일시 정지', '',
                  [('계속하기', self.close_modal), ('저장과 종료', self.pause_save),
                   ('다시 시작 · 은퇴', self.pause_run)], kind='pause')

    def pause_run(self):
        self.open('이번 모험', '', [('처음부터 다시 시작', self.confirm_restart),
                  ('은퇴하기', self.confirm_retire), ('뒤로', self.pause)], kind='pause_menu')

    def confirm_restart(self):
        self.open('다시 시작', '이번 진행을 지우고 첫 장부터 시작할까?',
                  [('다시 시작',lambda: setattr(self,'request','new')),
                   ('돌아가기',self.pause_run)],kind='pause_menu')

    def confirm_retire(self):
        self.open('은퇴하기', '이번 모험을 끝내고 시작 화면으로 갈까?',
                  [('은퇴하기',self.retire),('돌아가기',self.pause_run)],kind='pause_menu')

    def retire(self):
        if not self.store.discard_checkpoint():
            self.notify('진행 기록을 지우지 못했다. 다시 시도해 보자.')
            return
        self.sounds.play('retire')
        self.open('마검사의 조기 은퇴', '마왕에게 잡혔다. 첫 임무는 마왕성 복도 청소였다.',
                  [('시작 화면',lambda: setattr(self,'request','menu'))],kind='retired')

    def pause_save(self):
        self.open('저장과 종료', '', [('현재 위치 저장',self.manual_save),
                  ('시작 화면',lambda: setattr(self,'request','menu')),('뒤로',self.pause)],kind='pause_menu')

    def manual_save(self):
        if any(e.alive and abs(e.x-self.player.x) < 650 and abs(e.y-self.player.y)<220 for e in self.enemies) or any(abs(s.y-self.player.y)<180 for s in self.shots) or (self.hazards and self.player.y<180) or not self.player.grounded:
            self.notify('주변이 위험합니다. 모닥불 곁이나 적이 없는 지상에서 저장하세요.')
            return
        self.save_checkpoint()
        self.close_modal()
        self.sounds.play('ui_lock' if self.store.error else 'save')
        self.notify(self.store.error or '현재 위치와 선택을 저장했습니다.')

    def open_journal(self):
        self.open('모험 기록책', '', [('닫기', self.close_modal)], kind='journal')

    def obj_uid(self, obj):
        return f'{self.run.stage}:{obj["id"]}'

    def under_root(self, x, y=0):
        return self.near_crawl(x, y, padding=20) is not None

    def near_crawl(self, x, y, padding=90):
        return next((o for o in self.objects if o['kind']=='crawl'
                     and abs(o['x']-x)<o['w']/2+padding
                     and o['y']<=y<o['y']+o['ceiling']), None)

    def update_posture(self,p):
        # 먼저 웅크려 들어가야 한다. 안에서 키를 놓아도 나올 때까지 자세를 유지한다.
        p.forced_crouch=self.under_root(p.x,p.y) and (p.crouching or p.forced_crouch or p.drop_timer>0)

    def nearest(self):
        p=self.player
        interactable = [o for o in self.objects
                        if o['kind'] in {'event','record','camp','chest','lever','door'}
                        and abs(o.get('actor_x',o['x'])-p.x)<135
                        and abs(o['y']-p.y)<(44 if o['kind']=='door' or o['y'] else 72)]
        return min(interactable, key=lambda o: abs(o.get('actor_x',o['x'])-p.x)+2*abs(o['y']-p.y), default=None)

    def interact(self):
        if not self.player.grounded:
            self.sounds.play('ui_lock')
            self.notify('착지한 뒤 E를 눌러 살펴보세요.', 1.5)
            return
        obj = self.nearest()
        if not obj:
            self.sounds.play('ui_lock')
            self.notify('상호작용할 물건 가까이에서 E를 누르세요.')
            return
        kind, uid = obj['kind'], self.obj_uid(obj)
        if kind=='door':
            if self.door_ready(obj):
                self.sound_at('door', obj['x'], obj['y'])
                self.door_entry=dict(door=obj, age=0.0, start_x=self.player.x)
                self.bursts.clear()
                self.keys.clear()
                self.player.animation.play('walk')
                self.player.facing=1 if obj['x']>=self.player.x else -1
            else:
                self.sounds.play('ui_lock')
                self.notify('사슬 스위치를 먼저 당기자.' if obj.get('lock')=='lever' else '문지기를 먼저 쓰러뜨리자.')
        elif kind == 'record':
            if obj['record'] not in self.run.records:
                self.sound_at('record', obj['x'], obj['y'])
                self.run.records.append(obj['record'])
                self.gain_xp(30)
                self.player._action('adv/hero_pickup__hero_reach', 'adv/hero_pickup__hero_reach_up')
                self.burst('pickup_fx__pickup', obj['x'], obj['y']+85, .5)
                self.highlight('record', RECORDS[obj['record']][0])
                self.story_context = None
                self.open(RECORDS[obj['record']][0], RECORDS[obj['record']][1], [('기억하고 길을 나선다', self.close_modal)],
                          'portrait_hero__hero_think', speaker='기록의 목소리', focus=obj['x'])
            else:
                self.sounds.play('ui_lock')
                self.notify('이미 기록책에 적어 둔 문양입니다.')
        elif kind == 'chest':
            if uid not in self.run.taken:
                self.sound_at('chest', obj['x'], obj['y'])
                self.run.taken.append(uid)
                self.run.shards += 2
                self.gain_xp(25)
                obj['opened'] = self.time
                self.burst('pickup_fx__pickup', obj['x'], obj['y']+80, .6)
                self.notify('회복 파편 2개 · 경험치 25')
            else:
                self.sounds.play('ui_lock')
                self.notify('이 상자는 이미 열었습니다.')
        elif kind == 'lever':
            self.sound_at('lever', obj['x'], obj['y'])
            if not self.run.has('gate_open'):
                self.sounds.play('gate', gain=.74)
            self.run.mark('gate_open')
            self.run.mark('gate_time_set')
            self.notify('성문이 열렸다. 문 앞에서 E를 누르자.')
            for gate in self.objects:
                if gate['kind'] == 'door' and gate.get('lock')=='lever':
                    gate['opened'] = self.time
        elif kind == 'camp':
            self.camp()
        else:
            self.event(obj['event'])

    def begin_name(self):
        self.open('촌장과 첫 만남','먼 길을 나서기 전에, 네 이름을 알려 주겠니?',
                  [('이 이름으로 출발',self.confirm_name)],speaker='촌장')
        self.modal['name_entry']=NameEntry()
        SDL_SetTextInputRect(SDL_Rect(430,613,420,42))
        SDL_StartTextInput()

    def handle_name(self,event):
        entry=self.modal['name_entry']
        if event.type==SDL_TEXTINPUT:
            entry.insert(event.text)
        elif event.type==SDL_TEXTEDITING:
            entry.edit(event.text)
        elif event.type==SDL_KEYDOWN:
            if event.key==SDLK_BACKSPACE:
                entry.backspace()
            elif event.key==SDLK_RETURN:
                self.confirm_name()
            elif event.key==SDLK_ESCAPE:
                self.close_modal()
            elif event.key==SDLK_v and getattr(event,'mod',0)&KMOD_CTRL:
                value=SDL_GetClipboardText()
                if isinstance(value,bytes):entry.insert(value.decode('utf8',errors='ignore'))
        elif event.type==SDL_MOUSEBUTTONDOWN and event.button==SDL_BUTTON_LEFT:
            for x,y,w,h,index in self.hitboxes:
                if x<=event.x<=x+w and y<=720-event.y<=y+h:
                    self.confirm_name()
                    break

    def confirm_name(self):
        if not self.modal or not self.modal.get('name_entry'):return
        value=self.modal['name_entry'].confirm()
        if not value:return
        self.run.nickname=value
        self.sounds.play('ui_accept')
        self.close_modal()
        self.event('elder')
        self.save_checkpoint()

    def event(self, key):
        self.story_context = key
        if key=='elder' and not self.run.nickname:
            self.begin_name()
            return
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
            self.open('남겨진 달의 문양', '잊힌 이름을 지키는 문양이다.', [('기억하고 돌아선다', self.close_modal)])
            return
        if key == 'side_seal':
            self.open(*EVENT_TEXT[key][:1], EVENT_TEXT[key][2], [('동료의 달빛으로 연다' if self.companion else '사슬의 빈틈을 살핀다', lambda: self.event_result(key, 'open'))], EVENT_TEXT[key][1])
            return
        title, portrait, text = EVENT_TEXT[key]
        text = EVENT_LINES.get(key, text)
        if self.run.has(key+'_done') and key not in {'healer', 'memory', 'rescue'}:
            self.open(title, '이미 이야기를 마쳤다.', [('계속 간다', self.close_modal)], portrait, speaker='이야기')
            return
        options = {
            'elder': [('촌장의 말을 듣는다', 'listen')],
            'healer': [('HP·MP 회복', 'heal'), ('떠난다', 'leave')],
            'rescue': [('빛의 순서대로 함께 매듭을 푼다', 'careful'), ('마검으로 봉인을 잘라 구한다 · 부적에 금이 감', 'force'), ('구조 표식을 남기고 혼자 간다', 'mark')],
            'merchant': [('붕대를 나눈다 · 신뢰 +1', 'help'), ('봉인석을 흡수한다 · 침식 +1', 'take'), ('그대로 떠난다', 'leave')],
            'mirror': [('반사의 버릇을 기억한다', 'remember')],
            'altar': [('문양을 정화한다 · 침식 −1', 'purify'), ('힘을 흡수한다 · 침식 +1', 'absorb')],
            'memory': [('이름을 함께 기억하고 부적을 복구한다', 'repair'), ('나중에 다시 살핀다', 'leave')],
            'envoy': [('마을에 경고한다 · 신뢰 +1', 'warn'), ('계약한다 · 추격 감소 / 침식 +1', 'contract'), ('계약을 거절한다', 'refuse')],
        }[key]
        if key == 'rescue' and self.run.companion:
            self.open('풀려난 거울 웅덩이', '아직도 물결이 조금 무섭네. 그래도 이제 혼자가 아니니까.\n가자. 네가 돌아갈 길도 함께 찾고 싶어.', [('함께 간다', self.close_modal)], 'portrait_lunea__lunea_relief')
            return
        short_labels={
            'elder':('검의 이야기를 듣는다',),'healer':('회복한다','떠난다'),
            'merchant':('붕대를 준다','봉인석의 힘을 받는다','떠난다'),
            'mirror':('기록해 둔다',),'altar':('검을 정화한다','힘을 받는다'),
            'memory':('부적을 고친다','다음에 고친다'),
            'envoy':('마을에 알린다','계약한다','거절한다')}
        lines={
            'elder':[('소년','촌장님, 이 검을 주웠어요. 짐승들이 날 따라와요.'),
                     ('촌장','마왕의 검이구나. 힘을 기르고 네가 지킬 것을 정하거라.')],
            'merchant':[('소년','괜찮으세요?'),('상인','다리를 다쳤네. 붕대가 있니? 이 돌은 마을을 지키는 봉인석이야.')],
            'envoy':[('마왕의 전령','검을 넘기겠다고 약속해라. 추격을 멈추지.'),
                     ('소년','마을에 알려야 하나? 아니면 시간을 벌까?')]}
        options=[(short_labels.get(key,tuple(label for label,_ in options))[i],
                  lambda key=key,value=value:self.event_result(key,value))
                 for i,(_,value) in enumerate(options)]
        self.talk(lines.get(key,[(SPEAKERS.get(key,'소년'),text)]),options,
                  title=title,portrait=portrait,visual='memory' if key=='memory' else None)

    def event_result(self, key, value):
        r = self.run
        first = not r.has(key+'_done')
        if first or key in {'healer', 'memory'}:
            cue = STORY_SOUNDS.get((key, value))
            if cue:
                self.sounds.play(cue)
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
            ('merchant','help'): '고맙구나. 회복 파편 두 개를 가져가렴.',
            ('merchant','take'): '마력은 강해졌지만 마을을 지키던 봉인석의 불이 꺼졌다.',
            ('altar','purify'): '문양에 달빛이 돌아왔다. 검의 침식이 잦아들었다.',
            ('altar','absorb'): '마력을 얻었다. 침식이 깊어졌다.',
            ('memory','repair'): '기억해 줘서 고마워. 부적도 다시 온전해졌어.\n마지막까지 함께 이름을 지키자.',
            ('envoy','warn'): '마을에 경고가 닿았다. 주민들이 대피한다.',
            ('envoy','contract'): '추격자들이 물러났다. 침식이 깊어졌다.',
            ('envoy','refuse'): '계약을 거절했다. 사슬 스위치를 찾아 성문을 열자.',
            ('mirror','remember'): '왕관을 쓴 내 모습이다. 폐허의 기록을 찾아보자.',
            ('merchant','leave'): '상인은 등불을 켜고 다음 여행자를 기다린다.',
        }
        if value=='leave' and key in {'healer','memory'}:
            if key=='memory':
                r.mark('memory_deferred')
            self.close_modal()
            return
        text = result_lines.get((key,value), text)
        if self.story_only and key in {'merchant','rescue'}:
            proceed=self.leave_story
        else:
            proceed=self.close_modal
        self.open('길에 남은 선택', text, [('계속 간다', proceed)], portrait,
                  speaker='루네아' if key in {'rescue','memory'} and r.companion else '상인' if key=='merchant' and value=='help' else {'elder':'촌장','healer':'치유사','mirror':'소년'}.get(key,'이야기'))

    def camp(self):
        if any(e.alive and abs(e.x-self.player.x) < 650 and abs(e.y-self.player.y)<220 for e in self.enemies) or any(abs(s.y-self.player.y)<180 for s in self.shots) or (self.hazards and self.player.y<180):
            self.sounds.play('ui_lock')
            self.notify('주변의 위협을 정리한 뒤 모닥불에서 쉴 수 있습니다.')
            return
        self.save_checkpoint(heal=True)
        self.sounds.play('rest')
        self.camp_choices()

    def camp_choices(self):
        leave=('떠난다',self.leave_camp)
        options=([('루네아와 이야기',self.camp_talk)] if self.run.companion else [])
        if self.run.stage>=6 and self.run.erosion:
            options.append(('검을 진정시킨다',self.calm))
        options.append(leave)
        r=self.run
        self.open('모닥불', '회복하고 저장했다.',options,
                  'portrait_lunea__lunea_smile' if r.companion else 'portrait_hero__hero_relief',
                  visual='camp',speaker='루네아' if r.companion else '소년')

    def camp_talk(self):
        r=self.run
        self.sounds.play('pact')
        lines=[]
        if 'secret' not in r.pacts:
            r.pacts.append('secret')
            lines += [('소년','검을 쓸 때마다 손의 상처가 뜨거워져.'),
                      ('루네아','혼자 참지 마. 내가 네 이름을 기억할게.')]
        if r.stage>=4 and ('memory' not in r.pacts or r.fracture):
            if 'memory' not in r.pacts:r.pacts.append('memory')
            r.fracture=False
            lines += [('루네아','부적이 고쳐졌어. 함께 기억해 줘서 고마워.')]
        if r.stage>=6 and 'plan' not in r.pacts:
            r.pacts.append('plan')
            lines += [('소년','검의 힘을 돌려주고, 같이 집에 돌아가자.'),
                      ('루네아','응. 마지막까지 함께할게.')]
        self.save_checkpoint(heal=True)
        self.talk(lines or [('루네아','조금 쉬었다 가자. 내가 곁에 있을게.')],
                  [('출발',self.leave_camp)],visual='camp')

    def leave_camp(self):
        if self.run.stage==6 and 'plan' not in self.run.pacts:
            self.run.mark('plan_deferred')
            self.save_checkpoint()
        self.close_modal()

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
        restore=('준비하러 돌아간다', self.return_hall) if missing else (
            '마검의 힘을 돌려준다', lambda: self.end_choice('restore'))
        self.open('마검의 운명', '왕이 쓰러졌다. 마검의 힘을 어떻게 할까?',
                  [restore, ('마검을 봉인한다', lambda: self.end_choice('journey')),
                   ('다른 길을 택한다', self.other_endings)], 'portrait_hero__hero_focus', kind='final')

    def other_endings(self):
        self.open('다른 길', '달의 힘으로 밤을 끝내거나, 내가 새 왕이 될 수 있어.',
                  [('달의 의식을 시작한다', lambda: self.end_choice('moon')),
                   ('밤의 왕관을 받는다', self.confirm_crown), ('뒤로', self.final_choice)],
                  'portrait_hero__hero_focus',kind='final')

    def confirm_crown(self):
        self.open('왕관의 무게', '왕관을 받으면 밤이 끝나지 않는다.',
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
        self.sounds.clear_scene_events()
        self.sounds.set_context(quiet=True)
        cue = 'ending_hidden' if ending == 'H1' else {
            '1': 'ending_good', '2': 'ending_bitter', '3': 'ending_bitter', '4': 'ending_dark'
        }[ending[-1]]
        self.sounds.play(cue)
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
            if self.run.unspent:
                self.highlight('growth', f'레벨 {self.run.level} · 성장 묶음을 골라요')
            else:
                self.notify(f'레벨 {self.run.level} · 기본 능력치가 조금 올랐어요.',1.6)

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
            cue = SWING_SOUNDS.get(state['name'])
            if cue:
                self.sounds.play(cue)
            self.slash_sound_serial = a.serial
        # 같은 베기의 검기·칼날·사라지는 잔상에 여러 번 닿아도 피해는 한 번이다.
        self.hit_ids = self.attack_hits.setdefault(state['serial'],set())
        self.attack_hits = {key:value for key,value in self.attack_hits.items() if key>=a.serial-8}
        coefficient = {'slash_1': 1, 'slash_2': 1.2, 'slash_3': 1.65, 'air_slash': 1.15, 'crouch_slash': .95}.get(state['name'], 1)
        damage = r.attack * coefficient * (1 + .09*r.skills.get('single', 0))
        if state['name'] == 'dash_slash':
            damage = (8 + r.attack*(1.8+.2*r.skills['dash']))*(1+.08*r.skills.get('single', 0))
        for enemy in self.enemies:
            if enemy.uid not in self.hit_ids and enemy.alive and p.effects.melee_hits(state, enemy.hurtbox()):
                enemy.hurt(damage, state['facing'], self)
                self.contact_target = dict(enemy=enemy,serial=a.serial,facing=p.facing)
                self.hit_ids.add(enemy.uid)
        for obj in self.objects:
            uid = self.obj_uid(obj)
            if obj['kind'] not in {'crate', 'barrier', 'pillar'} or uid in r.broken or uid in self.hit_ids:
                continue
            target = (obj['x']-35,obj['y'],obj['x']+35,obj['y']+130)
            if p.effects.melee_hits(state,target):
                obj['hp'] -= damage
                self.contact_target = dict(obj=obj,serial=a.serial,facing=p.facing)
                self.numbers.append(dict(x=obj['x'],y=obj['y']+70,text=str(round(damage)),age=0,hurt=False))
                self.hitstop=max(self.hitstop,{'slash_1':.060,'slash_2':.074,'slash_3':.095}.get(a.name,.060))
                self.hit_ids.add(uid)
                p.effects.burst('impact',obj['x'],obj['y']+45,p.facing)
                stone = obj['kind'] == 'pillar'
                if obj['hp'] <= 0:
                    self.sound_at('stone_break' if stone else 'wood_break', obj['x'], obj['y'])
                    r.broken.append(uid)
                    obj['broken_time'] = self.time
                    r.shards += 1
                    self.sound_at('pickup', obj['x'], obj['y'], gain=.6)
                    self.gain_xp(15)
                    if obj['kind'] == 'pillar':
                        for enemy in self.enemies:
                            if enemy.boss and enemy.alive:
                                enemy.change('hurt', enemy.key('hurt'))
                                enemy.slow = 4
                        self.notify('봉인 기둥이 무너졌다. 왕의 움직임이 잠시 멎는다.')
                else:
                    self.sound_at('hit_stone' if stone else 'hit_wood', obj['x'], obj['y'])
        p.effects.last_hit_state = state

    @staticmethod
    def overlap(a, b):
        return bool(a and b and a[0]<=b[2] and b[0]<=a[2] and a[1]<=b[3] and b[1]<=a[3])

    def update_waves(self):
        p, r = self.player, self.run
        settings = p.effects.settings['waveMotion']
        for wave in p.effects.waves:
            if 'hit' not in wave:
                self.sounds.play('wave_launch')
                wave['hit'] = set()
            wave.setdefault('damage', (6+r.magic*(1.45+.18*r.skills.get('wave', 0))) * (1.35 if self.hybrid_time > 0 and r.skills.get('hybrid', 0) else 1))
            wave.setdefault('size', 1+.14*r.skills.get('wide', 0))
            # 실제 픽셀 모양을 지나온 위치마다 확인해 빠른 파동도 적을 건너뛰지 않는다.
            targets = [enemy for enemy in self.enemies if enemy.alive and enemy.uid not in wave['hit']]
            samples = p.effects.wave_samples(wave, wave.get('hit_age', 0)) if targets else ()
            for enemy in targets:
                if p.effects.wave_hits(wave, enemy.hurtbox(), samples=samples):
                    enemy.hurt(wave['damage'], wave['facing'], self, magic=True)
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
                lower, upper = o['base_y'] + 4, o['base_y'] + o['travel'] - 4
                if riders and (previous_y <= lower < o['y'] or previous_y >= upper > o['y']):
                    self.sound_at('lift', o['x'], o['y'])
            elif motion=='moving':
                o['x']=o['base_x']+o['travel']*sin(self.time*2*pi/o['period'])
            elif motion=='crumble':
                if self.time<o.get('disabled_until',0): continue
                o['stepped']=o.get('stepped',0)+dt if riders else max(0,o.get('stepped',0)-dt)
                if o['stepped']>.75:
                    o['disabled_until']=self.time+4;o['stepped']=0
                    self.sound_at('crumble', o['x'], o['y'])
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
        height=getattr(p,'collision_height',126 if getattr(p,'crouching',getattr(p,'crouched',False)) else getattr(p,'BODY_HEIGHT',150))
        for o in self.objects:
            if o['kind']=='crawl' and abs(p.x-o['x'])<o['w']/2+20:
                ceiling=o['y']+o['ceiling']
                if p.vy>0 and old_y+height<=ceiling and p.y+height>=ceiling:
                    p.y=ceiling-height;p.vy=0
        if getattr(p,'drop_timer',0)>0: return
        tops = [o for o in self.solid_platforms() if self.platform_span(o)[0] <= p.x <= self.platform_span(o)[1]]
        if p.vy <= 0:
            landed = [o for o in tops if old_y >= o['y']-1 and p.y <= o['y']]
            if landed:
                top = max(o['y'] for o in landed)
                was_air = (old_y > top+.01 and p.vy<0) or getattr(p,'in_flight',False)
                impact_speed=p.vy
                p.y, p.vy, p.floor_y, p.air_dash_ready = top, 0, top, True
                if (was_air and p is self.player and p.mode not in {'hurt','dead'}
                        and p.animation.name not in {'dash_slash','dash_attack_recovery'}):
                    p.land(p.previous_direction,impact_speed)
                elif was_air and p is not self.player:
                    p.motion.play('lunea/land_soft')
                elif was_air:
                    p.in_flight=False
                    p.last_ground_y=top

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

    def travel_stage(self,index,x=180,*,page=0):
        """지역을 바꾼 직후 잠깐 멈춰 교차 전환을 읽을 시간을 준다."""
        self.keys.clear()
        self.enter_stage(index,x,page=page)
        self.sounds.play('portal')
        self.stage_settle=.48
        if self.story_only:
            self.pending_event=self.region

    def exit_ready(self):
        return self.region!='boss' or not any(e.alive or e.age<.9 for e in self.enemies)

    def door_ready(self, door):
        lock=door.get('lock')
        return self.exit_ready() if lock=='boss' else lock!='lever' or self.run.has('gate_open')

    def next_page(self):
        r=self.run
        if r.page+1<len(PAGES[r.stage]):
            page=r.page+1
            area=PAGES[r.stage][page]
            start={'rescue':475,'merchant':590,'boss':325}[area]
            self.travel_stage(r.stage,start,page=page)
        elif r.stage<7:
            self.travel_stage(r.stage+1)

    def leave_story(self):
        self.close_modal()
        self.rescue=None
        self.next_page()

    def offer_growth(self):
        r,p=self.run,self.player
        if (r.unspent and r.level>r.growth_offered
                and not self.story_only and p.grounded and p.mode=='free'
                and not (p.crouching or p.forced_crouch)
                and not any(e.alive and abs(e.x-p.x)<500 and abs(e.y-p.y)<190 for e in self.enemies)
                and not self.shots and not self.hazards):
            self.grow()
            return True
        return False

    def update_door_entry(self,dt):
        entry=self.door_entry
        entry['age']+=dt
        p=self.player
        x=entry['door']['x']
        t=min(1,entry['age']/.62)
        old=p.x
        p.x=entry['start_x']+(x-entry['start_x'])*min(1,t*1.4)
        p.advance_gait(p.x-old)
        self.footstep(p.x-old)
        ally=self.companion
        if ally and ally.floor_y==p.floor_y and abs(ally.x-x)<265:
            dx=x-ally.x
            ally.x+=max(-340*dt,min(340*dt,dx))
            if abs(dx)>1:
                ally.facing=1 if dx>0 else -1
                ally.motion.play('lunea/walk')
                ally.motion.update(dt)
        self.camera.focus(x,entry['door']['y']+15,self.world.width,dt,1.04)
        if t>=1:
            self.next_page()

    def update(self, dt):
        if self.owns_sounds:
            self.sounds.update(dt)
        self.time += dt
        if self.stage_settle>0:
            self.stage_settle=max(0,self.stage_settle-dt)
            return
        if self.door_entry:
            self.update_door_entry(dt)
            return
        if self.pending_event:
            event,self.pending_event=self.pending_event,None
            if (event=='rescue' and self.run.companion) or (event=='merchant' and self.run.has('merchant_done')):
                self.leave_story()
            else:
                self.event(event)
            return
        if self.cine_out:
            self.cine_out['age']+=dt
            if self.cine_out['age']>.6:self.cine_out=None
        self.toast_time = max(0, self.toast_time-dt)
        self.damage_flash = max(0,self.damage_flash-dt)
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
            if self.modal.get('visual')=='camp':
                self.camp_age += dt
                self.player.animation.update(dt)
                self.camera.focus(self.modal['focus_x'],self.modal['focus_y'],self.world.width,dt,1.08)
                return
            if self.modal['kind'] in {'dialogue','boss','final'}:
                p=self.player
                old_x=p.x
                if 'step_to' in self.modal:
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
                if p.animation.name == 'walk':
                    p.advance_gait(p.x - old_x)
                    self.footstep(p.x - old_x)
                else:
                    p.animation.update(dt)
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
        self.magic_cooldown = max(0,self.magic_cooldown-dt)
        self.mp = min(r.max_mp, self.mp+dt*(7 if p.mode == 'free' else 2.5))
        self.update_terrain(dt)
        old_x,old_y,old_vy=p.x,p.y,p.vy
        p.floor_y = self.floor_beneath(p)
        self.update_posture(p)
        previous_animation = p.animation.name
        p.update(dt, self.keys,limit_motion=self.keep_attack_distance)
        if p.animation.name != previous_animation and p.animation.name in {'guard_raise', 'magic_release'}:
            self.sounds.play(p.animation.name)
        self.platforms(old_y)
        self.blockers(old_x)
        if p.grounded and old_y > p.y + 1 and old_vy < -70:
            self.sounds.play('land_' + self.surface(), gain=min(1, abs(old_vy) / 550))
            if old_vy < -245:
                p.effects.burst('land',p.x,p.y,p.facing)
        sprang = False
        for o in self.objects:
            if o['kind']=='spring' and abs(p.x-o['x'])<52 and p.mode=='jump' and p.jump_launched and p.y<55 and p.vy>300 and self.time>=o.get('next_bounce',0):
                p.vy=1160;p.floor_y=0;p.mode='free';p.gait=None;p.air_dash_ready=True
                o['next_bounce']=self.time+1
                sprang = True
                self.sound_at('spring', o['x'], o['y'])
                self.burst('adv/pickup_fx__pickup',o['x'],0,.5)
            elif o['kind']=='crystal' and self.obj_uid(o) not in r.taken and abs(p.x-o['x'])<42 and abs(p.y+65-o['y'])<65:
                r.taken.append(self.obj_uid(o));self.mp=min(r.max_mp,self.mp+12)
                self.gain_xp(28)
                self.sound_at('crystal', o['x'], o['y'])
                self.burst('adv/pickup_fx__pickup',o['x'],o['y'],.3)
        p.x = max(75, min(self.world.width-75, p.x))
        p.advance_gait(p.x - old_x)
        self.footstep(p.x - old_x)
        if not sprang and p.mode == 'jump' and old_vy <= 0 < p.vy:
            self.sounds.play('jump')
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
                self.sound_at('boss_fall' if enemy.boss else 'enemy_fall', enemy.x, enemy.y)
                if enemy.uid not in r.killed:
                    r.killed.append(enemy.uid)
                    r.kills += 1
                    r.shards += 1 if enemy.boss else 0
                    self.gain_xp(140+30*r.stage if enemy.boss else 24+8*r.stage)
                    if enemy.boss:
                        self.sounds.play('victory', gain=.8)
                        self.highlight('victory', enemy.actor['name']+'을 넘어섰다')
        for shot in self.shots:
            shot.update(dt)
            for obj in self.objects:
                if obj['kind'] == 'cover' and abs(shot.x-obj['x']) < obj.get('w', 100)/2 and 0 < shot.y < obj.get('h', 72):
                    shot.age = shot.life
                    self.sound_at('bolt_impact', shot.x, shot.y)
                    self.burst('hit_impacts__hit_metal', shot.x, shot.y, .3)
            if not shot.dead and abs(shot.x-p.x) < shot.radius+20 and p.y+15 < shot.y+shot.radius and shot.y-shot.radius < p.y+p.collision_height:
                self.damage_player(shot.damage, shot.x)
                shot.age = shot.life
                self.sound_at('bolt_impact', shot.x, shot.y, gain=.55)
                kind = 'spore_burst' if 'spore' in shot.key else 'paper_break' if 'paper' in shot.key else 'thread_snap' if 'needle' in shot.key else 'night_impact'
                self.burst('projectile_impacts__'+kind, shot.x, shot.y, .4)
        self.shots = [s for s in self.shots if not s.dead and -100 < s.x < self.world.width+100]
        for hazard in self.hazards:
            hazard['age'] += dt
            if hazard['age'] >= hazard['wait'] and not hazard['hit']:
                hazard['hit'] = True
                self.sound_at('trap_' + hazard['kind'], hazard['x'], hazard['y'])
                self.burst('root_spike__root_spike' if hazard['kind'] == 'root' else 'seal_warning__seal_burst', hazard['x'], hazard['y'], .65)
                if abs(p.x-hazard['x']) < hazard['radius'] and -62<p.y-hazard['y']<125:
                    self.damage_player(hazard['damage'], hazard['x'])
        self.hazards = [h for h in self.hazards if h['age'] < h['life']]
        if self.companion:
            self.companion.update(dt, self)
        for obj in self.objects:
            if obj['kind'] == 'hazard' and abs(p.x-obj['x']) < 320 and int(self.time)%6 == 0 and not self.hazards:
                self.sound_at('trap_warn', obj['x'], obj['y'])
                self.hazards.append(dict(x=obj['x'], y=0, age=0, wait=1, life=2, hit=False, kind='rock', damage=18, radius=70))
            if obj['kind'] == 'wind' and abs(p.x-obj['x']) < obj['w']/2 and p.y < 140:
                self.sound_at('wind_zone', obj['x'], obj['y'])
                p.x += dt*35
        # 동시에 쓰러지면 승리 연출보다 HP 0의 재도전을 먼저 처리한다.
        if p.hp <= 0:
            self.keys.clear()
            return
        if self.offer_growth():
            return
        if r.stage==7 and self.region=='boss' and self.exit_ready() and not self.opened_final:
            self.opened_final=True
            r.mark('boss_won')
            self.save_checkpoint()
            self.final_choice()
            return
        if p.x<=85 and r.stage>0 and self.region=='explore':
            self.travel_stage(r.stage-1, 3400)
            return
        self.sync_stats()
        proximity=max((max(0,min(1,(900-abs(e.x-p.x))/500)) for e in self.enemies if e.alive and e.boss),default=0)
        self.camera.follow(p, self.world.width, dt,combat_wide=proximity)

    def draw(self):
        self.view.draw()

    def close(self):
        if self.modal and self.modal.get('name_entry'):
            SDL_StopTextInput()
        if self.owns_sounds:
            self.sounds.close()
