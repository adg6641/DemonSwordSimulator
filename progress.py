"""한 판의 성장·선택·결말과 로컬 저장. 화면 코드와 분리해 규칙을 고치기 쉽게 둔다."""
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
import copy
import json
import secrets
from campaign_data import PAGES
from naming import clean_name

ENDINGS = {
    'D1': ('함께 맞는 새벽', '검이 식자 성창에 햇빛이 들었다. 루네아가 창을 열었다. “돌아갈 때는 큰길로 가자며?” 둘은 해가 뜬 쪽으로 걸었다.'),
    'D2': ('아직 끝나지 않은 여행', '두 사람은 검을 싸서 가방 깊숙이 넣었다. 루네아가 지도에 표시를 하나 더 했다. “일단 여기까지 가 보자.”'),
    'D3': ('달이 돌아간 밤', '루네아는 부적을 쥐고 의식에 남았다. 소년은 입구에 등불을 하나 놓았다. 돌아올 길을 볼 수 있도록.'),
    'D4': ('끝나지 않는 밤', '왕관을 쓴 소년은 곁의 소녀를 지켰다고 믿었다. 그 이름을 부르려 입을 열었지만 아무 말도 나오지 않았다.'),
    'S1': ('함께 맞는 새벽', '문양에 새벽빛이 돌자 홀로 성을 나섰다. 마을 입구에 다다르니 촌장이 불을 들고 기다리고 있었다.'),
    'S2': ('아직 끝나지 않은 여행', '검을 봉인했다. 남은 틈이 어디로 이어지는지는 아직 모른다. 소년은 지도를 접고 혼자 길을 나섰다.'),
    'S3': ('달이 돌아간 밤', '성에서 본 달이 서서히 밝아졌다. 보지 못한 곳에서 누군가 의식을 마쳤다. 소년은 그 사람의 이름을 알지 못했다.'),
    'S4': ('끝나지 않는 밤', '혼자 왕좌에 앉았다. 손에 넘치는 힘으로 무엇이든 할 수 있을 것 같았다. 그런데 돌아갈 마을의 이름이 생각나지 않았다.'),
    'H1': ('어둠 끝에 마주한 진실', '투구가 떨어졌다. 왕의 얼굴은 내 얼굴이었다. 검게 물든 손이 나를 움켜쥐었다.\n“네가 한 선택들, 정말 후회하지 않을 자신이 있냐?”\n대답하기도 전에 두 사람의 손끝부터 재가 되어 흩어졌다.'),
}


@dataclass
class Run:
    nickname: str = ''
    progression_version: int = 2
    seed: int = field(default_factory=lambda: secrets.randbelow(2**31))
    stage: int = 0
    page: int = 0
    unlocked: int = 0
    level: int = 1
    growth_offered: int = 1
    xp: int = 0
    earned: int = 0
    unspent: int = 0
    skill_points: int = 0
    growth_builds: dict = field(default_factory=lambda: dict(physical=0, magic=0, balance=0))
    spent: dict = field(default_factory=lambda: dict(attack=0, magic=0, vitality=0, focus=0))
    skills: dict = field(default_factory=lambda: dict(dash=0, wave=0))
    path: str = ''
    trust: int = 0
    erosion: int = 0
    companion: bool = False
    fracture: bool = False
    records: list = field(default_factory=list)
    pacts: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    choices: list = field(default_factory=list)
    killed: list = field(default_factory=list)
    broken: list = field(default_factory=list)
    taken: list = field(default_factory=list)
    shards: int = 2
    kills: int = 0
    hits: int = 0
    seconds: float = 0
    hidden_entry: bool | None = None
    ending: str = ''

    @classmethod
    def from_dict(cls, data):
        run = cls(**{f.name: data[f.name] for f in fields(cls) if f.name in data})
        run.nickname=clean_name(run.nickname)
        if not 0 <= run.stage < 8 or not 1 <= run.level <= 100 or run.unspent < 0:
            raise ValueError('잘못된 저장 수치')
        if not 0 <= run.page < len(PAGES[run.stage]):
            raise ValueError('잘못된 구역')
        if 'page' not in data and run.stage==7 and run.has('boss_won'):
            run.page=1
        if 'growth_offered' not in data and not run.unspent and run.path:
            run.growth_offered=run.level
        if set(run.spent) != {'attack', 'magic', 'vitality', 'focus'} or any(v < 0 for v in run.spent.values()):
            raise ValueError('잘못된 능력치')
        if 'progression_version' not in data:
            if run.path:
                run.growth_builds[run.path] = 1
            run.unspent = run.level//10 + int(run.level >= 2 and not run.path)
            run.skill_points = 0
            run.growth_offered = 1
            run.xp = min(run.xp, run.xp_needed-1)
        if set(run.growth_builds) != {'physical', 'magic', 'balance'} or any(
                not isinstance(v,int) or v < 0 for v in run.growth_builds.values()):
            raise ValueError('잘못된 성장 방향')
        return run

    def data(self):
        return asdict(self)

    @property
    def display_name(self):
        return self.nickname or '소년'

    def has(self, flag):
        return flag in self.flags

    def mark(self, flag):
        if flag not in self.flags:
            self.flags.append(flag)

    def choose(self, event, choice):
        self.choices.append([event, choice])

    @property
    def attack(self):
        return round(13 + (self.level-1)*(.35 if self.path in {'physical','balance'} else .12)
                     + self.spent['attack']*3, 1)

    @property
    def magic(self):
        return round(12 + (self.level-1)*(.35 if self.path in {'magic','balance'} else .12)
                     + self.spent['magic']*3, 1)

    @property
    def max_hp(self):
        return round(100 + (self.level-1)*(.8 if self.path=='physical' else .4)
                     + self.spent['vitality']*10)

    @property
    def max_mp(self):
        return round(80 + (self.level-1)*(.8 if self.path=='magic' else .4)
                     + self.spent['focus']*10)

    @property
    def tier(self):
        return min(7, 1 + max(self.skills.get('dash',0),self.skills.get('wave',0))//2
                   + (self.level-1)//20)

    @property
    def xp_needed(self):
        return 120 + (self.level-1)*50 + (self.level-1)**2*8

    @property
    def dash_recharge(self):
        # 첫 습득은 5초. 대시 베기 강화마다 1초씩 줄어든다.
        rank = max(1, self.skills.get('dash', 0))
        return max(1, 6 - rank)

    def gain_xp(self, amount):
        if self.level >= 100:
            self.xp = 0
            return 0
        self.xp += max(0, amount)
        count = 0
        while self.xp >= self.xp_needed and self.level < 100:
            self.xp -= self.xp_needed
            self.level += 1
            if self.level == 2 or self.level % 10 == 0:
                self.earned += 1
                self.unspent += 1
            count += 1
        if self.level == 100:
            self.xp = 0
        return count

    def choose_bundle(self, path):
        """한 번 고르면 기술·관련 능력치가 함께 오른다."""
        if path not in self.growth_builds or self.unspent <= 0:
            return False
        self.unspent -= 1
        self.growth_builds[path] += 1
        if not self.path:
            self.path = path
        for skill in ('dash','wave'):
            if path == 'balance' or path == ('physical' if skill == 'dash' else 'magic'):
                self.skills[skill] = min(6,self.skills.get(skill,0)+1)
        additions = {'physical': {'attack':2,'vitality':2},
                     'magic': {'magic':2,'focus':2},
                     'balance': {'attack':1,'magic':1,'vitality':1,'focus':1}}[path]
        for key,value in additions.items():
            self.spent[key] += value
        return True

    def all_magic(self):
        return (self.path=='magic' and self.unspent==0 and self.growth_builds['magic']>0
                and not self.growth_builds['physical'] and not self.growth_builds['balance']
                and self.spent['attack']==0)

    def missing_restore(self):
        missing = []
        if self.trust < 2:
            missing.append('마을 신뢰 2')
        if self.erosion > 1:
            missing.append('침식 1 이하')
        for key, title in [('night', '밤의 기록'), ('moon', '달의 기록'), ('return', '귀환의 기록')]:
            if key not in self.records:
                missing.append(title)
        if self.companion:
            for key, title in [('secret', '비밀 공유'), ('memory', '기억 복구'), ('plan', '함께 세운 계획')]:
                if key not in self.pacts:
                    missing.append(title)
            if self.fracture:
                missing.append('부적 균열 복구')
        return missing

    def resolve_ending(self, choice, alive=True):
        if not alive:
            return None
        if self.hidden_entry is True:
            return 'H1'
        number = {'crown': 4, 'restore': 1, 'moon': 3, 'journey': 2}.get(choice)
        if number is None or choice == 'restore' and self.missing_restore():
            return None
        return ('D' if self.companion else 'S') + str(number)


class SaveStore:
    def __init__(self, root):
        self.folder = Path(root) / 'userdata'
        self.checkpoint = None
        self.history = []
        self.error = ''
        self._load()

    def _load(self):
        try:
            file = self.folder / 'save.json'
            if not file.exists():
                return
            data = json.loads(file.read_text(encoding='utf8'))
            if data.get('version') != 1:
                raise ValueError('저장 버전')
            self.history = data.get('history', [])[-100:]
            point = data.get('checkpoint')
            if point:
                Run.from_dict(point['run'])
                self.checkpoint = point
        except (OSError, ValueError, TypeError, KeyError):
            self.error = '저장 파일을 읽지 못했습니다. 새 모험으로 시작할 수 있습니다.'

    def _write(self):
        file = self.folder / 'save.json'
        temporary = self.folder / 'save.tmp'
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(dict(version=1, checkpoint=self.checkpoint, history=self.history), ensure_ascii=False, indent=2), encoding='utf8')
            temporary.replace(file)
            self.error = ''
        except OSError:
            self.error = '디스크에 저장하지 못했습니다. 현재 실행 중에는 체크포인트가 유지됩니다.'

    def save(self, run, x, y, hp, mp, enemies):
        self.checkpoint = copy.deepcopy(dict(run=run.data(), x=x, y=y, hp=hp, mp=mp, enemies=enemies))
        self._write()

    def restore(self):
        return copy.deepcopy(self.checkpoint)

    def discard_checkpoint(self):
        previous=self.checkpoint
        self.checkpoint = None
        self._write()
        if self.error:
            self.checkpoint=previous
        return not self.error

    def finish(self, run):
        if not any(r.get('seed') == run.seed for r in self.history):
            self.history.append(run.data())
        self.history = self.history[-100:]
        self.checkpoint = None
        self._write()
