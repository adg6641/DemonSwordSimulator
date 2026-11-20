"""지역 배치와 사건 문장. 좌표·적 구성·대사를 이 파일에서 바꿀 수 있다."""

STAGE_LENGTH = 3840
PORTAL_PLATFORM_WIDTH = 1204
PORTAL_X = 3260
GROUND_PORTAL_X = 3640
PORTAL_CHEST_X = 2870
SPAWNS = [
    [(1, 1250), (1, 2150)],
    [(1, 1500), (2, 2000), (3, 2630), (2, 3250)],
    [(4, 1470), (5, 1930), (6, 2420), (16, 3320)],
    [(7, 1070), (8, 1600), (15, 2240), (6, 3180)],
    [(9, 1250), (10, 1900), (8, 2480), (17, 3320)],
    [(11, 1160), (12, 1750), (14, 2370), (18, 3320)],
    [(13, 1080), (15, 1650), (11, 2300), (19, 3320)],
    [(20, 2050), (12, 1280), (15, 2170)],
]
BOSSES = {2: 16, 4: 17, 5: 18, 6: 19, 7: 20}
PAGES = (
    ('explore',), ('explore', 'rescue'), ('explore', 'merchant', 'boss'),
    ('explore',), ('explore', 'boss'), ('explore', 'boss'),
    ('explore', 'boss'), ('explore', 'boss'),
)
PAGE_WIDTH = {'explore': STAGE_LENGTH, 'rescue': 1280, 'merchant': 1280, 'boss': 2000}
OBJECTIVES = [
    '촌장에게 검에 관해 물어보자',
    '거울 웅덩이의 소녀를 찾아가자',
    '부서진 수레 곁의 상인을 만나자',
    '폐허에 남은 밤의 기록을 찾자',
    '제단을 조사하고 달의 기록을 찾자',
    '전령의 말을 듣고 성문을 열자',
    '귀환의 기록을 얻고 마지막 쉼터로 가자',
    '밤의 왕 바르켄을 쓰러뜨리자',
]

# (가운데 x, 윗면 y, 길이). 두 경로의 끝에는 각각 모닥불과 보상 상자가 있다.
PLATFORM_ROUTES = (
    # 마을: 넓은 낮은 계단식 언덕. 숲: 좌우로 감아 오르는 나뭇가지.
    (((860,85,288),(1110,165,344),(1405,270,288),(1625,380,224),(1840,500,344)),
     ((2110,90,344),(2400,185,288),(2670,290,344),(2890,390,224),(3090,485,344))),
    (((850,100,224),(1070,220,168),(900,335,224),(1120,455,168),(1340,570,224),(1540,675,288),(1740,780,344)),
     ((2240,90,288),(2480,190,224),(2710,310,288),(2910,425,168),(3120,535,344))),
    # 깊은 숲: 뿌리를 돌아가는 발판. 폐허: 끊어진 아치와 돌아 오르는 탑.
    (((1010,130,288),(1290,250,224),(1510,370,288),(1320,490,224),(1575,615,168),(1800,740,344)),
     ((2240,95,344),(2520,215,288),(2350,335,224),(2600,455,344),(2920,575,344))),
    (((700,105,224),(970,225,288),(1250,345,224),(1080,470,168),(1335,590,288),(1580,710,224),(1850,835,344)),
     ((2490,115,288),(2300,235,168),(2560,365,288),(2820,495,224),(3090,625,344))),
    # 달의 제단: 두 곡선형 부유 섬. 성문: 높고 넓은 성벽 통로.
    (((1030,120,288),(1290,240,224),(1530,365,288),(1760,490,168),(1550,605,224),(1740,725,344)),
     ((2240,125,344),(2490,245,224),(2710,365,288),(2910,490,168),(3110,615,224),(2910,740,344))),
    (((920,100,288),(1170,220,224),(1410,345,288),(1620,470,168),(1420,595,224),(1680,720,344)),
     ((2160,120,288),(2400,250,224),(2620,380,288),(2850,510,224),(2620,640,288),(3150,770,PORTAL_PLATFORM_WIDTH))),
    # 회랑: 바람 기둥을 가로지르는 긴 상층 길. 왕좌 앞: 비대칭의 두 높은 탑.
    (((1080,110,224),(1320,235,288),(1550,355,168),(1340,475,224),(1575,600,288),(1800,730,344)),
     ((2090,125,224),(2310,250,288),(2520,375,224),(2740,500,168),(2520,620,288),(2800,750,224),(3150,880,PORTAL_PLATFORM_WIDTH))),
    (((850,130,288),(1100,255,224),(1340,380,288),(1140,505,168),(1390,630,224),(1620,755,288),(1840,880,344)),
     ((2470,140,344),(2740,270,224),(2970,400,288),(3180,535,168),(3150,670,PORTAL_PLATFORM_WIDTH))),
)

SIDE_PLATFORMS = (
    ((470,75,288),(3410,115,224)), ((550,145,168),(3380,130,288)),
    ((620,110,224),(3220,90,344)), ((460,145,168),(3390,135,224)),
    ((660,100,288),(3430,150,168)), ((480,125,224),(3400,110,288)),
    ((580,150,168),(3330,120,224)), ((500,95,288),(3490,145,168)),
)

# 멀리 가는 발판은 가장자리에서 점프로 닿는 위치를 기준으로 왕복한다.
BACKDROP_SUPPORTS = (
    ((1190,0,310),(2730,0,390)), ((1100,170,620),(2890,0,470)),
    ((1510,90,660),(2490,0,430)), ((1100,70,760),(2820,130,560)),
    ((1650,120,640),(2840,170,650)), ((1430,0,650),(3040,100,700)),
    ((1560,100,680),(2680,100,790)), ((1200,80,770),(3040,0,640)),
)


def platform(stage, name, x, y, width, **motion):
    return dict(id=name, kind='platform', x=x, y=y, w=width,
                visual=f'polish/platform_{stage+1}_{width}', **motion)


def objects(stage):
    """지형은 통과 가능한 발판과 실제로 부술 수 있는 엄폐물을 구분한다."""
    left_route, right_route = PLATFORM_ROUTES[stage]
    result = [
        platform(stage, 'platform_a', *SIDE_PLATFORMS[stage][0]),
        platform(stage, 'platform_b', *SIDE_PLATFORMS[stage][1]),
        dict(id='chest', kind='chest', x=right_route[0][0], y=right_route[0][1], asset='reward_chest__reward_chest'),
        dict(id='crate', kind='crate', x=(1240,1450,1395,2080,1220,1980,2370,1120)[stage], y=0, hp=24 + stage*6, asset='crate_break__crate_break'),
        dict(id='camp', kind='camp', x=(2810,3170,2460,2200,3090,2730,2460,2820)[stage], y=0, asset='campfire__campfire'),
        dict(id='sign', kind='decor', x=(390,620,440,570,710,420,700,380)[stage], y=0, asset='sign_torch__sign_sway'),
        dict(id='torch', kind='decor', x=(3350,3040,2850,3220,2490,3190,3000,3150)[stage], y=0, asset='sign_torch__torch_loop'),
    ]
    if stage == 0:
        result += [dict(id='elder', kind='event', x=700, y=0, event='elder', npc='npc_elder'),
                   dict(id='healer', kind='event', x=2700, y=0, event='healer', npc='npc_healer')]
    if stage == 1:
        result += [dict(id='pool', kind='event', x=900, y=0, event='rescue', asset='mirror_pool__mirror_pool'),
                   dict(id='root', kind='crawl', x=1850, y=0, w=440,ceiling=134,roof=172, asset='story_props__root_tunnel'),
                   platform(stage,'root_step_l',1560,52,120),
                   platform(stage,'root_step_r',2140,52,120),
                   dict(id='wood', kind='barrier', x=3070, y=0, hp=42, asset='barrier_break__barrier_break')]
    if stage == 2:
        result += [dict(id='merchant', kind='event', x=900, actor_x=1090, y=0,
                        event='merchant', asset='merchant_cart__cart_broken'),
                   dict(id='root', kind='crawl', x=1790, y=0, w=440, ceiling=140, roof=172),
                   platform(stage,'root_step_l',1515,48,120),
                   platform(stage,'root_step_r',2070,55,120)]
    if stage == 3:
        result += [dict(id='mirror', kind='event', x=740, y=0, event='mirror', asset='mirror_well__black_mirror'),
                   dict(id='night', kind='record', x=1900, y=0, record='night', asset='story_props__record_night'),
                   dict(id='well', kind='decor', x=2640, y=0, asset='mirror_well__night_well'),
                   dict(id='rock', kind='hazard', x=3020, y=0, asset='falling_stone__stone_fall')]
    if stage == 4:
        result += [dict(id='altar', kind='event', x=880, y=0, event='altar', asset='altar_states__altar_corrupt'),
                   dict(id='moon', kind='record', x=2040, y=0, record='moon', asset='story_props__record_moon'),
                   dict(id='memory', kind='event', x=2670, y=0, event='memory', asset='story_props__charm_cracked')]
    if stage == 5:
        result += [dict(id='envoy', kind='event', x=760, y=0, event='envoy', npc='npc_envoy'),
                   dict(id='lever', kind='lever', x=2670, y=0, asset='story_props__switch_up'),
                   dict(id='gate', kind='gate', x=3540, y=0, w=120, asset='gate_open__gate_open')]
    if stage == 6:
        result += [dict(id='return', kind='record', x=1990, y=0, record='return', asset='story_props__record_return'),
                   dict(id='seal', kind='event', x=2100, y=0, event='side_seal', asset='story_props__seal_cover'),
                   dict(id='wind', kind='wind', x=1530, y=75, w=260, asset='magic_wind__magic_wind')]
    if stage == 7:
        result = [o for o in result if o['id'] not in {'chest', 'crate', 'sign', 'torch'}]
        result += [dict(id='pillar', kind='pillar', x=1800, y=0, w=70, hp=35, asset='pillar_break__pillar_break'),
                   dict(id='final', kind='event', x=3150, y=0, event='final', asset='terrain__throne_seal')]
        result[2:2] = [dict(id='last_camp', kind='camp', x=580, y=0, asset='campfire__campfire')]
    # 지상 길은 이어 두고, 점프와 대시로 오르는 두 개의 상층 탐색 길을 만든다.
    for i,entry in enumerate(left_route+right_route):
        result.append(platform(stage,f'upper_{i}',*entry))
    lift_x=(835,850,1170,880,1020,940,1020,880)[stage]
    drift_x,side_y,_=SIDE_PLATFORMS[stage][1]
    drift_y=side_y+124
    gap_x,gap_base,gap_width=left_route[3]
    gap_x+=gap_width//2+104
    gap_y=gap_base+82
    spring_x=(1990,2210,2160,1970,2140,2000,1900,2320)[stage]
    result += [
        platform(stage,'lift',lift_x,114,168,motion='lift',base_x=lift_x,base_y=114,travel=225,period=9),
        platform(stage,'moving',drift_x,drift_y,224,motion='moving',base_x=drift_x,base_y=drift_y,travel=87,period=7),
        platform(stage,'crumble',gap_x,gap_y,120,motion='crumble',stepped=0,disabled_until=0),
        dict(id='spring',kind='spring',x=spring_x,y=0,asset='spring'),
        dict(id='upper_chest',kind='chest',x=right_route[-1][0],y=right_route[-1][1],asset='reward_chest__reward_chest'),
        dict(id='upper_camp',kind='camp',x=left_route[-1][0],y=left_route[-1][1],asset='campfire__campfire'),
    ]
    # 지역에 맞는 기믹만 남겨 같은 사다리 구조가 반복되지 않게 한다.
    keep={0:{'lift'},1:{'moving','spring'},2:{'moving','crumble'},3:{'lift','crumble'},
          4:{'moving','lift'},5:{'lift','crumble'},6:{'spring','moving'},7:{'crumble'}}[stage]
    result=[o for o in result if o['id'] not in {'lift','moving','spring','crumble'} or o['id'] in keep]
    if stage in {1,4,6}:
        x,y,w=left_route[3]
        result.append(platform(stage,'branch_drift',x+155,y+54,168,motion='moving',
                               base_x=x+155,base_y=y+54,travel=60,period=10-stage*.4))
    if stage in {2,3,7}:
        x,y,_=right_route[2]
        result.append(platform(stage,'broken_arch',x+175,y+55,120,motion='crumble',stepped=0,disabled_until=0))
    for i,(x,y,_) in enumerate(left_route[1:]+right_route[1:3]+right_route[-2:]):
        result.append(dict(id=f'moon_shard_{i}',kind='crystal',x=x,y=y+55,asset='crystal'))
    return result


def page_objects(stage, page):
    region = PAGES[stage][page]
    if region in {'rescue', 'merchant'}:
        event = 'rescue' if region=='rescue' else 'merchant'
        obj = next(o for o in objects(stage) if o.get('event')==event)
        obj['x'] = 720 if event=='rescue' else 580
        if event=='merchant':
            obj['actor_x'] = 780
        return [obj]
    if region == 'boss':
        if stage==7:
            return [dict(id='final',kind='event',x=1660,y=0,event='final',asset='terrain__throne_seal')]
        return [dict(id='arena_gate',kind='door',x=1690,y=0,lock='boss')]

    result = [o for o in objects(stage) if o.get('event') not in {'rescue','merchant','final'} and o['kind']!='gate']
    left,right = PLATFORM_ROUTES[stage]
    raised = {0:('healer', left[1]), 3:('night', left[3]), 4:('moon', right[2]),
              5:('envoy', left[3]), 6:('return', left[3])}
    if stage in raised:
        ident,(x,y,_) = raised[stage]
        next(o for o in result if o['id']==ident).update(x=x,y=y)
    if stage==5:
        x,y,_=right[4]
        next(o for o in result if o['id']=='lever').update(x=x,y=y)
    if stage==6:
        next(o for o in result if o['id']=='camp').update(x=left[-1][0],y=left[-1][1])
        result=[o for o in result if o['id']!='upper_camp']
    if stage in {5,6,7}:
        next(o for o in result if o['id']=='upper_chest')['x'] = PORTAL_CHEST_X
        result.append(dict(id='upper_gate',kind='door',x=PORTAL_X,y=right[-1][1],
                           lock='lever' if stage==5 else None))
    else:
        result.append(dict(id='exit_gate',kind='door',x=GROUND_PORTAL_X,y=0))
    # 비석이나 NPC의 바로 위에 파편이 떠서 실루엣을 가리지 않게 한다.
    occupied = [o for o in result if o['kind'] in {'event','record','door','chest','camp','lever'}]
    for o in result:
        if o['kind']=='crystal':
            if stage in {5,6,7} and o['y']==right[-1][1]+55:
                o['x']=3500
                continue
            near = next((prop for prop in occupied if abs(o['x']-prop['x'])<92
                         and 0<o['y']-prop['y']<160),None)
            if near:
                if near['id']=='upper_gate':
                    o['x']=3500
                elif near['id']=='upper_camp':
                    o['x']-=117
                elif near['id']=='upper_chest':
                    o['x']+=118
                else:
                    o['y']+=110
    return result


EVENT_TEXT = {
    'elder': ('마을의 어른', 'portrait_npcs__elder_neutral',
              '길에서 주운 검이 밤의 짐승들을 깨웠구나. 강해지는 방법만큼 어떤 사람으로 남을지도 골라야 한다.\n먼저 길의 상자를 베어 보고, 쉼터의 불빛을 기억하렴.'),
    'healer': ('마을의 치유사', 'portrait_npcs__healer_thanks',
               '모닥불에서 쉬면 몸과 마력이 회복돼. 다친 사람을 돕는다면 우리도 네 편이 되어 줄게.\n회복 파편은 H로 사용할 수 있어. 위험할 때 아끼기만 하지는 마.'),
    'rescue': ('거울 웅덩이', 'portrait_lunea__lunea_worry',
              '물속 그림자가 소녀의 발과 반대로 움직인다. 초승달·별·원 매듭이 차례로 빛난다.\n잘못 당기면 이름이 지워진다. 소녀는 부적을 꼭 쥔 채 신호를 보내고 있다.'),
    'merchant': ('숲의 상인', 'portrait_npcs__merchant_worried',
                '짐승들에게 쫓기다 수레가 부서졌어. 이 봉인석의 힘을 가져가면 네 검이 강해지겠지만, 나는 밤을 버티지 못할 거야.\n붕대를 조금만 나눠 줄 수 있겠니?'),
    'mirror': ('왕관을 쓴 반사', 'portrait_hero__hero_doubt',
              '거울 속에는 왕관을 쓴 자신이 서 있다. 검을 쥐는 버릇도, 손등의 초승달 같은 상처도 똑같다.\n거울에 손을 대려 하자 반사 쪽의 손이 아주 조금 늦게 움직였다.'),
    'altar': ('달이 지킨 이름', 'portrait_lunea__lunea_think',
             '금 간 제단 안에 오래된 마력이 남아 있다. 힘을 흡수하면 바로 강해질 수 있다.\n문양을 정화하면 밤과 달의 경계를 읽을 단서가 남는다. 동료의 기억 복구는 별도로 할 수 있다.'),
    'memory': ('달의 기억', 'portrait_lunea__lunea_sad',
              '루네아의 부적에는 잊힌 이름들이 잠들어 있다. 검의 힘을 사람에게 묶지 않고 문양으로 돌려보낼 수 있을까?\n금 간 부적도 함께 손보면 다시 길을 기억할 수 있다.'),
    'envoy': ('마왕의 전령', 'portrait_npcs__envoy_decisive',
              '왕은 자신의 검을 원한다. 이 계약을 받으면 성채의 추격이 줄어들 것이다.\n하지만 마을은 경고를 듣지 못한다. 지금 계약을 받더라도 마지막 왕관을 받을지는 별개의 선택이다.'),
    'side_seal': ('회랑의 측면 봉인', 'portrait_lunea__lunea_focus',
                  '문양 아래 좁은 길이 보인다. 루네아의 달빛으로 풀면 전투를 우회할 수 있다.\n혼자라면 사슬 스위치를 찾아 열 수 있다. 어느 길이든 귀환의 기록은 남아 있다.'),
}

PERKS = [
    ('dash', '대시 베기', '공격력 계수가 높은 돌진 베기. 미해금 기술도 배울 수 있다.', 'dash_level'),
    ('wave', '마검파', '마력 계수가 높은 원거리 검기. Z 집중 후 C로 발사한다.', 'wave_level'),
    ('dash_distance', '긴 대시', '대시의 이동 속도와 공격 도달 거리가 늘어난다.', 'dash_distance'),
    ('recovery', '빠른 회수', '베기와 공격 후 회복 동작이 빨라진다.', 'quick_recover'),
    ('single', '집중 타격', '베기의 한 번 피해를 높인다.', 'single_hit'),
    ('wide_slash', '넓은 베기', '근접 공격의 판정 범위가 늘어난다.', 'wide_slash'),
    ('pierce', '관통 검기', '한 마검파가 더 많은 적을 통과한다.', 'piercing'),
    ('wide', '큰 마검파', '마검파의 상하 판정 폭이 넓어진다.', 'wide_wave'),
    ('quick', '빠른 집중', 'Z의 준비 동작이 빨라지고 소비 마력이 줄어든다.', 'fast_focus'),
    ('duration', '긴 집중', '마검파를 사용할 수 있는 시간이 길어진다.', 'long_duration'),
    ('hybrid', '검과 파동의 연결', '대시 공격 직후 다음 마검파의 위력이 높아진다.', 'hybrid_link'),
    ('supply', '여행자의 보급', '회복 파편을 얻고 회복 효율을 높인다.', 'common_supply'),
]
