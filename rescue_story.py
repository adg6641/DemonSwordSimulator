"""루네아 구출은 한 번의 선택과 짧은 대화로 이어진다."""


class RescueStory:
    def __init__(self, scene):
        self.s=scene

    def start(self):
        s=self.s
        s.sounds.play('rescue_pool')
        s.story_context='rescue'
        s.talk([('소년','물속에 사람이 있어!'),
                ('루네아','그림자가 발을 붙잡았어. 내 부적의 빛을 따라와 줘.')],
               [('빛을 따라 구한다',lambda:self.rescue('careful')),
                ('검으로 줄을 벤다',lambda:self.rescue('force')),
                ('도움을 부르고 떠난다',self.leave)],title='거울 웅덩이')
        obj=next(o for o in s.objects if o.get('event')=='rescue')
        s.modal['step_to']=obj['x']-150

    def rescue(self, mode):
        s=self.s
        s.sounds.play('seal_break')
        obj=next(o for o in s.objects if o.get('event')=='rescue')
        s.burst('lunea/fx_heal',obj['x'],0,.55)
        s.event_result('rescue',mode)
        s.companion.x=obj['x']+35
        line='부적도 무사해. 정말 고마워!' if mode=='careful' else '고마워. 부적은 금이 갔지만 나중에 고치면 돼.'
        s.talk([('루네아',line),('소년','다친 곳은 없어? 난 이 검의 정체를 찾고 있어.'),
                ('루네아','난 루네아야. 달빛으로 널 도울 수 있어. 함께 가자.')],
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
