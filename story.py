"""한 번에 하나의 목표와, 인물의 짧은 말로 이야기를 전한다."""
CHAPTERS = ['마을의 아침', '거울 숲', '깊은 숲', '잊힌 폐허', '달의 제단', '검은 성문', '마지막 회랑', '밤의 왕좌']
INTRO = ['주운 검을 아는 사람을 찾아서', '물결 속에서 들려오는 구조 신호', '힘을 얻는 방법도 선택이다',
         '왕관을 쓴 나의 그림자', '잊힌 이름을 지키는 달빛', '마을과 계약 사이의 갈림길', '돌아갈 길을 함께 기억하다', '이제, 힘의 주인을 정할 시간']
SPEAKERS = {'elder':'촌장', 'healer':'치유사', 'rescue':'루네아', 'merchant':'상인', 'mirror':'소년',
            'altar':'제단의 기록', 'memory':'루네아', 'envoy':'마왕의 전령', 'side_seal':'소년'}
RECORDS = {
    'night': ('밤의 기록', '밤은 사람의 기억을 삼킨다. 마검의 힘을 계속 받아들이면 나도 나를 잊을 수 있다.'),
    'moon': ('달의 기록', '달빛은 잊힌 이름을 지킨다. 빼앗긴 기억을 되찾으면 밤의 경계도 고칠 수 있다.'),
    'return': ('귀환의 기록', '마검의 힘을 사람 대신 옛 문양에 돌려주자. 세 기록을 모으면 그 방법을 알 수 있다.'),
}
CHOICES = {
    'elder':('촌장',{'listen':'검의 정체를 듣고 출발'}),
    'rescue':('거울 숲',{'careful':'매듭을 풀어 루네아 구출','force':'마검으로 루네아 구출','mark':'표식을 남기고 단독 출발'}),
    'merchant':('상인',{'help':'붕대를 나눔','take':'봉인석의 힘을 가져감','leave':'수레를 그대로 둠'}),
    'mirror':('검은 거울',{'remember':'자신을 닮은 반사를 기억'}),
    'altar':('제단',{'purify':'문양을 정화함','absorb':'마력을 흡수함'}),
    'memory':('달의 기억',{'repair':'루네아의 부적을 복구함','leave':'나중에 돌아오기로 함'}),
    'envoy':('전령',{'warn':'마을에 경고를 보냄','contract':'추격을 멈추는 계약','refuse':'계약을 거절함'}),
    'side_seal':('측면 길',{'open':'봉인을 풀고 우회함'}),
    'healer':('치유사',{'heal':'몸과 마력을 회복함','leave':'다시 출발함'}),
}

def choice_label(event,value):
    title,values=CHOICES.get(event,(event,{}))
    return title+' · '+values.get(value,{'physical':'물리 특화','magic':'마법 특화','balance':'균형 성장',
         'restore':'경계 복원','journey':'여행 계속','moon':'달의 의식','crown':'밤의 왕관'}.get(value,value))
EVENT_LINES = {
    'elder': '그 검은 마왕의 것이란다. 밤의 짐승들도 검을 쫓고 있어.\n마왕이 오기 전에 숲길에서 힘을 길러라. 다만, 힘 때문에 너 자신을 잃지는 말거라.',
    'healer': '다쳤을 땐 회복 파편을 써. H를 누르면 돼.\n모닥불에서 쉬면 몸과 마력이 모두 회복되고, 그곳부터 다시 시작할 수 있어.',
    'rescue': '도와줘! 거울 속 그림자가 나를 붙잡고 있어.\n초승달, 별, 원. 이 순서로 빛을 따라 매듭을 풀어 줘.',
    'merchant': '짐승들을 피하다 수레가 부서졌어. 붕대를 나눠 줄 수 있겠니?\n수레의 봉인석은 마을을 지키는 물건이야. 그 힘을 가져가면 마을은 더 위험해져.',
    'mirror': '거울 속의 저 사람… 나잖아? 왜 왕관을 쓰고 있지?\n손등의 상처까지 똑같아. 그런데 내가 손을 내린 뒤에야 그림자도 따라 움직였어.',
    'altar': '이 제단에는 오래된 힘이 남아 있다.\n힘을 빼앗으면 검은 강해진다. 문양을 정화하면 밤을 되돌릴 단서를 지킬 수 있다.',
    'memory': '내 부적에는 잊힌 사람들의 이름이 남아 있어.\n함께 기억해 줘. 부적을 고치면 마검의 힘을 돌려보낼 길도 찾을 수 있을 거야.',
    'envoy': '왕께서 검을 돌려받길 원하신다. 계약하면 성채의 추격을 멈추겠다.\n마을에 먼저 경고를 보내도 좋다. 그 대신, 이곳의 적은 네가 넘어야 한다.',
    'side_seal': '봉인 뒤에 다른 길이 있네. 사슬을 풀면 추적자 한 무리를 피할 수 있겠어.',
}

def objective(scene):
    r = scene.run
    if r.stage == 0:
        if not r.has('elder_done'): return '촌장에게 검에 관해 물어보기', 700
        if r.level < 2: return 'C로 밤의 짐승을 물리치기', 1250
        if not r.path: return '성장 방향 고르기', scene.player.x
    elif r.stage == 1 and not (r.companion or r.has('aid_marker')):
        return '거울에 갇힌 소녀 살펴보기', 900
    elif r.stage == 2 and not r.has('merchant_done'):
        return '부서진 수레의 상인 만나기', 900
    elif r.stage == 3:
        if not r.has('mirror_done'): return '검은 거울 살펴보기', 740
        if 'night' not in r.records: return '밤의 기록 읽기', 1900
    elif r.stage == 4:
        if not r.has('altar_done'): return '달의 제단 조사하기', 880
        if 'moon' not in r.records: return '달의 기록 읽기', 2040
        if r.companion and 'memory' not in r.pacts: return '루네아와 부적의 기억 되찾기', 2670
    elif r.stage == 5:
        if not r.has('envoy_done'): return '전령의 제안 듣기', 760
        if not r.has('gate_open'): return '사슬 스위치로 성문 열기', 2670
    elif r.stage == 6:
        if 'return' not in r.records: return '귀환의 기록 읽기', 1990
        if r.companion and 'plan' not in r.pacts: return '쉼터에서 마지막 계획 나누기', 2500
    elif r.stage == 7 and r.has('boss_won'):
        return '마검의 힘을 어디로 돌려줄지 선택하기', 3150
    boss = next((e for e in scene.enemies if e.boss and e.alive), None)
    if boss: return boss.actor['name']+' 물리치기', boss.x
    return '오른쪽 길로 다음 지역에 가기', 3740
