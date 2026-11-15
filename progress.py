"""한 판의 성장·선택·결말과 로컬 저장. 화면 코드와 분리해 규칙을 고치기 쉽게 둔다."""
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
import copy
import json
import secrets
from campaign_data import PAGES

ENDINGS = {
    'D1': ('함께 맞는 새벽', '둘은 검의 힘을 문양에 돌려주고, 평범한 사람으로 새 아침을 맞았다.'),
    'D2': ('아직 끝나지 않은 여행', '당장 모든 답을 찾지는 못했다. 그래도 두 사람은 나란히 다음 길을 걷는다.'),
    'D3': ('달이 돌아간 밤', '루네아는 자신의 뜻으로 달의 기억을 이었다. 소년은 돌아올 길에 불을 남겼다.'),
    'D4': ('끝나지 않는 밤', '소년은 왕관을 썼다. 곁의 소녀를 지켰다고 믿었지만, 그녀의 이름을 떠올리지 못했다.'),
    'S1': ('함께 맞는 새벽', '홀로 경계를 복원한 소년을 마을의 불빛들이 맞았다. 세상은 다시 아침을 기억했다.'),
    'S2': ('아직 끝나지 않은 여행', '검을 잠정 봉인한 소년은 남은 균열을 찾아 떠났다. 한 사람의 발자국이 길게 이어졌다.'),
    'S3': ('달이 돌아간 밤', '만나지 못한 달의 계승자가 의식을 마쳤다. 서로의 이름을 모르는 두 사람이 같은 밤을 지켰다.'),
    'S4': ('끝나지 않는 밤', '홀로 왕좌에 앉은 소년은 끝없는 힘을 얻었다. 돌아가려던 마을의 이름부터 지워졌다.'),
    'H1': ('어둠 끝에 마주한 진실', '투구 아래의 얼굴은 다른 세계선에서 자란 자신이었다. 검은 손이 소년을 붙잡았다.\n“너의 그 선택들에 대해 후회하지 않을 자신이 있냐?”\n두 그림자는 함께 재가 되어 사라졌다. 이번 세계선의 마지막 밤이었다.'),
}


@dataclass
class Run:
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
        if not 0 <= run.stage < 8 or not 1 <= run.level <= 99 or run.unspent < 0:
            raise ValueError('잘못된 저장 수치')
        if not 0 <= run.page < len(PAGES[run.stage]):
            raise ValueError('잘못된 구역')
        if 'page' not in data and run.stage==7 and run.has('boss_won'):
            run.page=1
        if 'growth_offered' not in data and not run.unspent and run.path:
            run.growth_offered=run.level
        if set(run.spent) != {'attack', 'magic', 'vitality', 'focus'} or any(v < 0 for v in run.spent.values()):
            raise ValueError('잘못된 능력치')
        return run

    def data(self):
        return asdict(self)

    def has(self, flag):
        return flag in self.flags

    def mark(self, flag):
        if flag not in self.flags:
            self.flags.append(flag)

    def choose(self, event, choice):
        self.choices.append([event, choice])

    @property
    def attack(self):
        return 13 + (self.level - 1) * 2 + self.spent['attack'] * 5

    @property
    def magic(self):
        return 12 + (self.level - 1) * 2 + self.spent['magic'] * 6

    @property
    def max_hp(self):
        return 100 + (self.level - 1) * 4 + self.spent['vitality'] * 20

    @property
    def max_mp(self):
        return 80 + (self.level - 1) * 2 + self.spent['focus'] * 15

    @property
    def tier(self):
        return min(7, 1 + (self.level - 1) // 2 + max(self.skills.get('dash', 0), self.skills.get('wave', 0)) // 2)

    @property
    def xp_needed(self):
        return 40 + (self.level - 1) * 20

    def gain_xp(self, amount):
        self.xp += amount
        count = 0
        while self.xp >= self.xp_needed and self.level < 99:
            self.xp -= self.xp_needed
            self.level += 1
            self.earned += 2
            self.unspent += 2
            self.skill_points += 1
            count += 1
        return count

    def allocate(self, stat):
        if stat not in self.spent or self.unspent <= 0:
            return False
        self.spent[stat] += 1
        self.unspent -= 1
        return True

    def set_path(self, path):
        if self.path or path not in {'physical', 'magic', 'balance'}:
            return False
        self.path = path
        for skill in ('dash', 'wave'):
            if path == 'balance' or path == ('physical' if skill == 'dash' else 'magic'):
                self.skills[skill] = 1
        return True

    def upgrade(self, skill):
        if self.skill_points <= 0 or self.skills.get(skill, 0) >= 6:
            return False
        self.skills[skill] = self.skills.get(skill, 0) + 1
        self.skill_points -= 1
        return True

    def all_magic(self):
        return self.earned > 0 and self.unspent == 0 and self.spent['magic'] == self.earned and sum(self.spent.values()) == self.earned

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
