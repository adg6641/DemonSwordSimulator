"""지역 배치와 사건 문장. 좌표·적 구성·대사를 이 파일에서 바꿀 수 있다."""

STAGE_LENGTH = 3840
SPAWNS = [
    [(1, 1250), (1, 2150)],
    [(1, 1500), (2, 2000), (3, 2630), (2, 3250)],
    [(4, 1470), (5, 1930), (6, 2420), (16, 3320)],
    [(7, 1070), (8, 1600), (15, 2240), (6, 3180)],
    [(9, 1250), (10, 1900), (8, 2480), (17, 3320)],
    [(11, 1160), (12, 1750), (14, 2370), (18, 3320)],
    [(13, 1080), (15, 1650), (11, 2300), (19, 3320)],
    [(20, 2050)],
]
BOSSES = {2: 16, 4: 17, 5: 18, 6: 19, 7: 20}
OBJECTIVES = [
    '촌장과 이야기하고 검을 다뤄 보자. C로 적을 물리치고 첫 성장을 선택하자.',
    '거울 웅덩이를 살피자. 위험한 소녀를 도울지는 나의 선택이다.',
    '수레 곁의 상인을 만나고, 숲의 문지기를 넘어가자.',
    '검은 거울과 밤의 기록을 찾아 폐허의 진실을 읽자.',
    '제단을 조사하고 달의 기록을 얻자. 파수자의 예고를 보고 피하자.',
    '전령의 제안을 듣고 성문을 열자. 마을에 보낼 경고도 결정하자.',
    '귀환의 기록과 마지막 쉼터를 살피자. 세계선의 결말을 준비하자.',
    '바르켄의 돌진·내려치기·마력파를 넘고, 왕좌 뒤의 선택과 마주하자.',
]

# 같은 지역의 색·재질을 가진 두 발판. 오른쪽 길은 항상 지상으로도 지나갈 수 있다.
TERRAIN = [
    ('village_wood', 'village_step'), ('forest_log', 'forest_root'),
    ('forest_bridge', 'forest_earth'), ('ruin_platform', 'ruin_cover'),
    ('altar_step', 'altar_plinth'), ('gate_grate', 'gate_bastion'),
    ('hall_pillar', 'hall_threshold'), ('throne_plinth', 'throne_seal'),
]


def objects(stage):
    """지형은 통과 가능한 발판과 실제로 부술 수 있는 엄폐물을 구분한다."""
    result = [
        dict(id='platform_a', kind='platform', x=1330, y=125, w=240, asset='terrain__'+TERRAIN[stage][0]),
        dict(id='platform_b', kind='platform', x=2330, y=145, w=230, asset='terrain__'+TERRAIN[stage][1]),
        dict(id='chest', kind='chest', x=2330, y=145, asset='reward_chest__reward_chest'),
        dict(id='crate', kind='crate', x=1120, y=0, hp=24 + stage*6, asset='crate_break__crate_break'),
        dict(id='camp', kind='camp', x=2500 if stage in {2, 4, 5, 6} else 2850, y=0, asset='campfire__campfire'),
        dict(id='sign', kind='decor', x=380, y=0, asset='sign_torch__sign_sway'),
        dict(id='torch', kind='decor', x=3150, y=165, asset='sign_torch__torch_loop'),
    ]
    if stage == 0:
        result += [dict(id='elder', kind='event', x=700, y=0, event='elder', npc='npc_elder'),
                   dict(id='healer', kind='event', x=2700, y=0, event='healer', npc='npc_healer')]
    if stage == 1:
        result += [dict(id='pool', kind='event', x=900, y=0, event='rescue', asset='mirror_pool__mirror_pool'),
                   dict(id='root', kind='crawl', x=1850, y=0, w=170, asset='story_props__root_tunnel'),
                   dict(id='wood', kind='barrier', x=3070, y=0, hp=42, asset='barrier_break__barrier_break')]
    if stage == 2:
        result += [dict(id='merchant', kind='event', x=900, y=0, event='merchant', asset='merchant_cart__cart_broken'),
                   dict(id='log', kind='cover', x=1690, y=0, w=170, h=72, asset='story_props__log_cover')]
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
