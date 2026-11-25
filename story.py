"""한 번에 하나의 목표와, 인물의 짧은 말로 이야기를 전한다."""
CHAPTERS = ['마을의 아침', '거울 숲', '깊은 숲', '잊힌 폐허', '달의 제단', '검은 성문', '마지막 회랑', '밤의 왕좌']
INTRO = ['이 검, 촌장님이라면 아실 거야.', '숲 안쪽에서 누가 부른다.', '부서진 수레 옆에 사람이 쓰러져 있다.',
         '거울 속의 내가 왕관을 쓰고 있다.', '금이 간 제단에 달빛이 고인다.', '전령이 성문 앞에서 기다린다.',
         '왕좌로 가기 전, 마지막 모닥불.', '여기까지 왔다. 이제 검을 놓을 수 있을까?']
SPEAKERS = {'elder':'촌장', 'healer':'치유사', 'rescue':'루네아', 'merchant':'상인', 'mirror':'소년',
            'altar':'제단의 기록', 'memory':'루네아', 'envoy':'마왕의 전령', 'side_seal':'소년'}
RECORDS = {
    'night': ('밤의 기록', '나는 아직 내 이름을 안다. 어제는 어머니 이름도 알았다. 이 검을 오래 쥐고 있지 마라.'),
    'moon': ('달의 기록', '잊어버린 이름을 달빛 아래서 불러 보아라. 누군가 대답한다면, 아직 그 기억을 되찾을 수 있다.'),
    'return': ('귀환의 기록', '검의 힘을 사람이 다 받아 낼 필요는 없다. 밤과 달의 기록을 이 문양에 맞추면, 힘이 원래 자리로 돌아간다.'),
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
    if event=='성장 묶음':
        return '성장 · '+{'physical':'검술','magic':'마법','balance':'균형'}.get(value,value)
    title,values=CHOICES.get(event,(event,{}))
    return title+' · '+values.get(value,{'physical':'검술 성장','magic':'마법 성장','balance':'균형 성장',
         'restore':'마검의 힘 돌려주기','journey':'여행 계속','moon':'달의 의식','crown':'밤의 왕관'}.get(value,value))
EVENT_DIALOGUE = {
    'elder': [('소년', '촌장님, 길에서 이 검을 주웠어요. 그 뒤로 숲의 짐승들이 자꾸 따라와요.'),
              ('촌장', '잠깐, 이 문양 좀 보자. …그래, 이건 마왕의 검이란다. 짐승들이 쫓는 것도 이 검이겠구나.')],
    'healer': [('치유사', '가까이 오렴. 상처 좀 보자. 급할 땐 가지고 있는 회복 파편부터 쓰고, 모닥불을 만나면 쉬어 가.')],
    'merchant': [('소년', '수레 옆에 계신 분! 다치셨어요?'),
                 ('상인', '짐승들한테 쫓기다 바퀴가 빠졌어. 다리를 좀 감아야겠는데… 혹시 붕대 있니?'),
                 ('상인', '수레에 있는 돌은 마을을 지키는 데 쓸 거야. 네 검이 그 힘을 탐내는 것 같으니 조심해.')],
    'mirror': [('소년', '저건 내 얼굴인데… 왜 왕관을 쓰고 있지? 손등의 흉터도 나랑 똑같아.')],
    'altar': [('소년', '검을 가까이 대니까 금 사이로 빛이 새어 나와. 이 힘을 가져갈 수도 있겠지만, 문양부터 닦아 볼까?')],
    'memory': [('루네아', '잠깐, 부적이 따뜻해졌어. 여기 남은 이름들, 나 혼자 읽기엔 너무 많아. 옆에서 같이 읽어 줄래?')],
    'envoy': [('마왕의 전령', '그 검을 돌려주겠다고 약속해라. 그러면 네 뒤를 쫓는 놈들은 거둬 주지.'),
              ('소년', '그 약속을 믿을 수 있을까? 마을에 먼저 알려 두는 편이 나을지도 몰라.')],
}

EVENT_OPTIONS = {
    'elder': [('촌장의 조언을 듣는다', 'listen')],
    'healer': [('치료를 받는다', 'heal'), ('인사하고 떠난다', 'leave')],
    'merchant': [('붕대를 건넨다', 'help'), ('봉인석의 힘을 흡수한다', 'take'), ('조용히 떠난다', 'leave')],
    'mirror': [('눈에 본 것을 적어 둔다', 'remember')],
    'altar': [('제단의 문양을 정화한다', 'purify'), ('제단의 마력을 흡수한다', 'absorb')],
    'memory': [('함께 이름을 읽고 부적을 고친다', 'repair'), ('다음에 돌아온다', 'leave')],
    'envoy': [('마을에 위험을 알린다', 'warn'), ('전령과 거래한다', 'contract'), ('거래를 거절한다', 'refuse')],
}

EVENT_REPLIES = {
    ('elder','listen'): ('촌장', '숲길에 남은 짐승부터 물리쳐 보렴. 검을 익히다 보면 네 손에 맞는 기술이 생길 거야. 무리하진 말고.'),
    ('rescue','mark'): ('소년', '나뭇가지에 천을 묶어 두자. 누가 오면 여길 알아볼 거야. 나도 나중에 다시 올 수 있고.'),
    ('merchant','help'): ('상인', '아, 이제 좀 낫네. 고맙다. 수레에 회복 파편 두 개가 있으니 챙겨 가렴.'),
    ('merchant','take'): ('소년', '검이 한결 가벼워졌어. 잠깐, 수레의 불도 꺼졌잖아. 그 돌이 지키고 있던 게 정말 있었구나.'),
    ('merchant','leave'): ('상인', '…알겠다. 저기 등불만 켜 줄래? 다른 사람이 지나가면 나를 볼 수 있게.'),
    ('altar','purify'): ('소년', '문양을 닦으니까 검이 조용해졌어. 손도 아까보다 덜 아프고.'),
    ('altar','absorb'): ('소년', '힘이 손끝까지 밀려와. 그런데 내 그림자, 왜 한 박자 늦게 움직이지?'),
    ('memory','repair'): ('루네아', '들었어? 우리가 이름을 부르니까 부적이 대답하는 것 같았어. 이제 금도 다 메워졌네.'),
    ('envoy','warn'): ('소년', '멀리 마을 쪽에 불이 하나씩 켜져. 내 신호를 봤나 봐. 저 불을 따라 대피하면 돼.'),
    ('envoy','contract'): ('마왕의 전령', '약속대로 추격은 여기까지다. 검은 네가 직접 들고 와라. 왕이 기다린다.'),
    ('envoy','refuse'): ('소년', '저 사람한테 검을 넘길 순 없어. 성문 옆에 사슬이 보였지. 거기부터 가 보자.'),
    ('mirror','remember'): ('소년', '내가 검을 쥔 손까지 똑같았어. 잊기 전에 적어 두자. 폐허의 기록에 단서가 있을지도 몰라.'),
    ('healer','heal'): ('치유사', '됐어. 손 한번 펴 보렴. 괜찮지? 아프면 또 와.'),
    ('side_seal','open'): ('소년', '열렸다. 발소리가 저쪽에서 들려. 이 틈으로 가면 마주치지 않겠어.'),
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
