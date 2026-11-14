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
    'elder': '그 검은 마왕의 것이란다. 짐승들이 검을 쫓고 있어. 숲에서 힘을 길러라.',
    'healer': 'H로 회복 파편을 써. 모닥불에서는 쉬고 저장할 수 있어.',
    'rescue': '도와줘! 거울 속 그림자가 나를 붙잡고 있어.\n초승달, 별, 원. 이 순서로 빛을 따라 매듭을 풀어 줘.',
    'merchant': '다리를 다쳤어. 붕대가 필요하네. 이 봉인석은 마을을 지켜 줘.',
    'mirror': '거울 속 내가 왕관을 썼다. 손등의 상처까지 같다.',
    'altar': '제단의 마력을 흡수하거나, 문양을 정화할 수 있다.',
    'memory': '잊힌 이름들이 이 부적에 남아 있어. 함께 기억해 줘.',
    'envoy': '검을 넘기기로 약속하면 추격을 멈추겠다.',
    'side_seal': '봉인 뒤에 다른 길이 있네. 사슬을 풀면 추적자 한 무리를 피할 수 있겠어.',
}

def objective(scene):
    r = scene.run
    if scene.region=='boss':
        boss = next((e for e in scene.enemies if e.boss and e.alive), None)
        if boss:
            return '문지기에게 맞서기' if r.stage<7 else '바르켄에게 맞서기', boss.x,boss.y
        door=next(o for o in scene.objects if o['id'] in {'arena_gate','final'})
        return ('열린 문으로 들어가기' if r.stage<7 else '마검의 운명 고르기',door['x'],door['y'])
    if scene.story_only:
        return '',scene.player.x,scene.player.y

    def at(label, ident):
        obj=next(o for o in scene.objects if o['id']==ident)
        return label,obj.get('actor_x',obj['x']),obj['y']

    if r.stage == 0:
        if not r.has('elder_done'): return at('촌장 만나기','elder')
        if r.level < 2:
            enemy=next((e for e in scene.enemies if e.alive),None)
            if enemy:
                return '밤의 짐승 물리치기',enemy.x,enemy.y
    elif r.stage == 1 and not (r.companion or r.has('aid_marker')):
        return at('거울 웅덩이로 가는 포탈','exit_gate')
    elif r.stage == 2 and not r.has('merchant_done'):
        return at('상인에게 가는 포탈','exit_gate')
    elif r.stage == 3:
        if not r.has('mirror_done'): return at('검은 거울 살펴보기','mirror')
        if 'night' not in r.records: return at('밤의 기록 읽기','night')
    elif r.stage == 4:
        if not r.has('altar_done'): return at('달의 제단 조사하기','altar')
        if 'moon' not in r.records: return at('달의 기록 읽기','moon')
        if r.companion and 'memory' not in r.pacts and not r.has('memory_deferred'):
            return at('루네아의 부적 살피기','memory')
    elif r.stage == 5:
        if not r.has('envoy_done'): return at('전령 만나기','envoy')
        if not r.has('gate_open'): return at('사슬 스위치 당기기','lever')
    elif r.stage == 6:
        if 'return' not in r.records: return at('귀환의 기록 읽기','return')
        if r.companion and 'plan' not in r.pacts and not r.has('plan_deferred'):
            return at('모닥불에서 계획 세우기','camp')
    if r.stage in {5,6,7}:
        return at('다음 구역 포탈','upper_gate')
    return at('다음 구역 포탈','exit_gate')
