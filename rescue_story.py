"""한낮의 숲에 밤을 비추는 웅덩이. 세 문양을 읽고 이름을 구하는 첫 만남."""
class RescueStory:
    def __init__(self,scene):
        self.s=scene;self.mode='careful';self.knot=0;self.mistakes=0

    def show(self,title,text,options,speaker='이야기',image='discovery',zoom=(1.0,1.06),fx=None):
        s=self.s
        previous=s.modal.get('cine',{}).get('image') if s.modal else None
        old=s.modal.get('cine',{}) if s.modal else {}
        t=min(1,s.interaction_age/5);t=t*t*(3-2*t)
        start,end=old.get('zoom',(1,1));previous_zoom=max(1,start+(end-start)*t)
        s.story_context='rescue'
        s.open(title,text,options,'portrait_lunea__lunea_worry',speaker=speaker,visual='rescue',emphasis='choice' if len(options)>1 else None)
        s.modal['cine']=dict(image=image,previous=previous,zoom=zoom,fx=fx)
        s.modal['cine'].update(previous_zoom=previous_zoom,previous_pan=(1-t)*10)
        s.modal['shot_zoom']=.86 if image=='discovery' else 1.23 if image=='reflection' else 1.05

    def start(self):
        self.show('거울 웅덩이',
          '바람이 멎었다. 나뭇잎은 밝은데, 웅덩이 안에는 별이 떠 있다.\n물가의 소녀는 움직이지 못한다. 도움을 청하는 목소리는 물속에서만 들린다.',
          [('반사 속 신호부터 살펴본다',self.listen),('마검으로 그림자를 끊어 구한다',self.force),('구조 표식을 남기고 혼자 길을 나선다',self.leave)],zoom=(1.0,1.025))

    def listen(self):
        self.mode='careful'
        self.show('밤을 비추는 물',
          '소년이 손을 내밀자 물속의 손도 따라온다. 그런데 반사 속 손에는 낯선 왕관의 그림자가 걸려 있다.\n검을 쥔 손이 차가워진다. 소녀는 손을 내밀지 말라는 듯 고개를 젓는다.',
          [('소녀가 보내는 신호를 기다린다',self.voice)],image='reflection',zoom=(1.10,1.20))

    def voice(self):
        self.show('빼앗기기 직전의 이름',
          '내 목소리를 흉내 내는 거야. 물속에서 들리는 말은 믿지 마.\n내 이름까지 빼앗기면 아무도 나를 기억하지 못해. 부적의 빛을 봐 줘.',
          [('목소리보다 부적의 빛을 따른다',self.begin_knots)],speaker='루네아',image='reflection',zoom=(1.18,1.08))

    def begin_knots(self):
        self.knot=0;self.knots()

    def knots(self,wrong=False):
        names=['초승달','별','원'];signals=['가늘게 굽은 달빛','작게 깜빡이는 별빛','천천히 닫히는 둥근 빛']
        correct=[0,1,2][self.knot]
        text=(('그림자가 손목을 잡아당겼다. 소년은 힘을 풀고 한 걸음 물러섰다.\n' if wrong else '')+
              f'부적에서 {signals[self.knot]}이 떠오른다. 물속의 목소리는 다른 문양을 잡으라 속삭인다.\n눈앞의 빛과 같은 문양을 골라 연결을 풀자.')
        options=[(name+' 문양의 빛을 잇는다',lambda i=i:self.touch(i)) for i,name in enumerate(names)]
        self.show(f'물결의 매듭 · {self.knot+1} / 3',text,options,image='reflection',zoom=(1.07,1.13),fx='seal')
        self.s.modal['correct_choice']=correct
        if wrong:self.s.modal['cine']['shake']=True

    def touch(self,index):
        if index!=self.knot:
            self.mistakes+=1;self.s.sounds.play('hurt');self.knots(True);return
        self.s.sounds.play('magic');self.knot+=1
        if self.knot==3:self.pull()
        else:self.knots()

    def force(self):
        self.show('그림자와 부적 사이',
          '검을 가까이 대자 검은 실이 날을 향해 몰려든다. 검은 그림자를 베기보다 삼키려 한다.\n지금 끊으면 소녀는 빠져나오지만, 이름을 지키던 부적도 다칠 수 있다.',
          [('위험을 감수하고 한 번에 끊는다',self.force_pull),('검을 거두고 빛의 신호를 살핀다',self.listen)],image='pull',zoom=(1.14,1.04))

    def force_pull(self):
        self.mode='force';self.pull()

    def pull(self):
        self.show('검과 달빛이 맞닿는 순간',
          ('소년이 세 빛의 매듭을 하나로 잇자 검은 실이 느슨해진다. 소녀도 반대편에서 손을 뻗는다.\n소년은 검을 낮추고 그녀의 손을 붙잡았다. 이번에는 반사가 먼저 움직이지 않았다.' if self.mode=='careful' else
           '소년이 마검을 휘두르자 검은 실이 날 속으로 빨려 들어갔다. 부적에 가느다란 금이 번진다.\n그는 빈손으로 소녀의 손목을 받치고, 물가 밖으로 힘껏 끌어올렸다.'),
          [('손을 놓지 않고 끝까지 끌어올린다',self.release)],image='pull',zoom=(1.12,.98),fx='break')

    def release(self):
        s=self.s
        s.event_result('rescue',self.mode)
        self.show('물가에 남은 두 사람',
          ('발밑이 단단해… 정말 밖으로 나온 거구나. 내 이름은 루네아야.\n네가 내 목소리보다 빛을 믿어 줘서, 이름도 부적도 지킬 수 있었어.' if self.mode=='careful' else
           '구해 줘서 고마워. 나는 루네아야. 부적은… 조금 금이 갔네.\n그래도 다시 고칠 수 있어. 네가 잡아 준 손의 온기는 잊지 않을 거야.'),
          [('검에 대해 솔직히 이야기한다',self.first_talk),('괜찮은지 묻고 곁에서 기다린다',self.wait)],speaker='루네아',image='after',zoom=(1.07,1.0))
        s.modal['cine']['previous']='pull'

    def first_talk(self):
        self.s.run.choose('첫 만남','마검에 대한 두려움을 나눔')
        self.show('같이 찾을 수 있는 길',
          '나도 그 검이 왜 반응했는지 알고 싶어. 혼자라면 힘에 휩쓸릴 때 알아채기 어렵잖아.\n네가 돌아갈 곳이 있다면, 나도 그 길을 찾는 걸 돕고 싶어.',
          [('루네아와 함께 길을 나선다',self.finish)],speaker='루네아',image='after',zoom=(1.0,.98))

    def wait(self):
        self.s.run.choose('첫 만남','루네아가 일어날 때까지 기다림')
        self.show('처음으로 남긴 온기',
          '조금만 기다려 줘서 고마워. 서두르지 않아도 되는구나.\n이제 걸을 수 있어. 나도 네 모험에 함께 가도 될까?',
          [('루네아와 함께 길을 나선다',self.finish)],speaker='루네아',image='after',zoom=(1.03,1.0))

    def leave(self):
        self.s.event_result('rescue','mark')
        self.s.rescue=None

    def finish(self):
        self.s.rescue=None;self.s.close_modal()
