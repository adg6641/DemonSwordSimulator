"""촌장과 이름을 정할 때의 한글 조합·입력 상태."""
from unicodedata import normalize

MAX_NAME = 10


def clean_name(value):
    if not isinstance(value,str):
        return ''
    return ''.join(c for c in normalize('NFC',value) if c.isalnum() or c=='_')[:MAX_NAME]


class NameEntry:
    def __init__(self):
        self.text=''
        self.composition=''
        self.error=''

    def insert(self,text):
        self.text=clean_name(self.text+text)
        self.composition=''
        self.error=''

    def edit(self,text):
        self.composition=text
        self.error=''

    def backspace(self):
        # 조합 중인 한글은 IME가 지우고, 확정된 글자만 여기서 지운다.
        if not self.composition:
            self.text=self.text[:-1]
        self.error=''

    def confirm(self):
        if self.composition:
            self.error='한글 입력을 마친 뒤 Enter를 한 번 더 눌러 주세요.'
            return ''
        name=clean_name(self.text)
        self.error='' if name else '이름을 한 글자 이상 적어 주세요.'
        return name
