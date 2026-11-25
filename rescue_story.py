"""루네아 구출은 한 번의 선택과 짧은 대화로 이어진다."""


class RescueStory:
    def __init__(self, scene):
        self.s=scene

    def start(self):
        s=self.s
        s.sounds.play('rescue_pool')
        s.story_context='rescue'
        s.talk([('소년','방금 누구 소리였지? 거기, 물가에 있는 사람! 내 손 잡을 수 있어?'),
                ('루네아','잠깐, 더 오면 너도 잡혀. 내 발에 감긴 줄 보여? 부적이 비추는 매듭부터 풀어 줘.')],
               [('빛나는 매듭을 차례로 푼다',lambda:self.rescue('careful')),
                ('마검으로 줄을 자른다',lambda:self.rescue('force')),
                ('표식을 남기고 도움을 찾는다',self.leave)],title='거울 웅덩이')
        obj=next(o for o in s.objects if o.get('event')=='rescue')
        s.modal['step_to']=obj['x']-150

    def rescue(self, mode):
        s=self.s
        s.sounds.play('seal_break')
        obj=next(o for o in s.objects if o.get('event')=='rescue')
        s.burst('lunea/fx_heal',obj['x'],0,.55)
        s.event_result('rescue',mode)
        s.companion.x=obj['x']+35
        line = ('풀렸다. 휴… 부적도 멀쩡해. 고마워.' if mode=='careful'
                else '이제 움직일 수 있어. 어… 부적에 금이 갔네. 괜찮아, 달의 제단에 가면 고칠 수 있어.')
        s.talk([('루네아',line),
                ('소년','발 디딜 수 있어? 저 나무까지 같이 가자. 이 검 때문에 여기까지 왔는데 너도 위험하게 할 뻔했네.'),
                ('루네아','나 루네아야. 그 검, 전에 본 적 있어. 나도 같이 갈래. 네가 위험할 땐 내 달빛으로 막아 줄게.')],
               [('함께 출발',self.finish)])

    def leave(self):
        self.s.event_result('rescue','mark')
        self.s.rescue=None

    def finish(self):
        self.s.rescue=None
        if self.s.story_only:
            self.s.leave_story()
        else:
            self.s.close_modal()
