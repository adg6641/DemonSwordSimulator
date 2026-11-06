"""기존 시트와 모험 자산을 공통 좌표로 그린다. 텍스처는 필요한 것만 불러온다."""
from collections import OrderedDict
import json
from animation import load_pixel_image


class Assets:
    def __init__(self, root):
        self.root = root
        self.clips = {}
        self.actors = {}
        self.bodies = {}
        self.images = OrderedDict()
        for prefix, folder, manifest, key in [
            ('adv/', 'adventure', 'manifest.json', 'assets'),
            ('enemy/', 'enemies/animations', 'animations.json', 'clips'),
            ('lunea/', 'companions/lunea', 'animations.json', 'clips'),
        ]:
            data = json.loads((root / folder / manifest).read_text(encoding='utf8'))
            for clip in data[key]:
                self.clips[prefix + clip['id']] = dict(clip, path=root / folder / clip['file'])
            if prefix == 'enemy/':
                self.actors = {a['id']: a for a in data['actors']}
            if prefix == 'adv/':
                self.endings = {e['id']: e for e in data['endingCards']}
        polish = root / 'polish/manifest.json'
        if polish.exists():
            data = json.loads(polish.read_text(encoding='utf8'))
            self.bodies = data['bodies']
            for c in data['clips']:
                self.clips['polish/'+c['id']] = dict(c, path=polish.parent/c['file'])
        self.by_group = {}
        for key, clip in self.clips.items():
            self.by_group.setdefault(clip.get('group', '기존 동작'), []).append(key)

    def image(self, path):
        key = str(path)
        if key not in self.images:
            # 고해상도 채색화는 축소 시 부드럽게 표본화한다. 픽셀 지면은 별도 1:1 렌더링.
            self.images[key] = load_pixel_image(path, smooth=True)
        self.images.move_to_end(key)
        while len(self.images) > 36:
            self.images.popitem(last=False)
        return self.images[key]

    def frame(self, key, age, loop=None):
        c = self.clips[key]
        n = int(max(0, age) * c.get('fps', 0))
        looping = c.get('playback') == 'loop' if loop is None else loop
        return n % c['frameCount'] if looping else min(n, c['frameCount'] - 1)

    def duration(self, key):
        c = self.clips[key]
        return c['frameCount'] / max(1, c.get('fps', 0))

    def draw(self, key, x, y, camera=None, scale=None, age=0, facing=None, alpha=1, frame=None):
        c = self.clips[key]
        f = c['frames'][self.frame(key, age) if frame is None else min(c['frameCount'] - 1, frame)]
        image = self.image(c['path'])
        w, h = f['width'], f['height']
        s = (c.get('recommendedScale', 1) if scale is None else scale) * f.get('renderScale', 1)
        pivot = c.get('pivot', {'x': w / 2, 'y': h / 2})
        flipped = facing is not None and facing != (-1 if c.get('facing') == 'left' else 1) and c.get('flippable', True)
        px = w - pivot['x'] if flipped else pivot['x']
        cx = round(x - (camera.x if camera else 0) + (w / 2 - px) * s)
        cy = round(y - (camera.y if camera else 0) + (pivot['y'] - h / 2) * s)
        image.opacify(max(0, min(1, alpha)))
        image.clip_composite_draw(f['x'], f['pico2dY'], w, h, 0, 'h' if flipped else '', cx, cy, max(1, round(w*s)), max(1, round(h*s)))
        image.opacify(1)

    def fit(self, key, x, y, width, height, frame=0, alpha=1):
        c = self.clips[key]
        f = c['frames'][frame]
        image = self.image(c['path'])
        s = min(width / f['width'], height / f['height'])
        image.opacify(alpha)
        image.clip_draw(f['x'], f['pico2dY'], f['width'], f['height'], round(x), round(y), max(1, round(f['width']*s)), max(1, round(f['height']*s)))
        image.opacify(1)

    def panel(self, key, left, bottom, width, height, alpha=1):
        """모서리는 유지하고 가운데만 늘려 글을 올릴 틀을 만든다."""
        c = self.clips[key]
        image = self.image(c['path'])
        sw, sh = c['width'], c['height']
        border = min(26, sw//4, sh//4, int(width/4), int(height/4))
        bx = min(sw//4, 65) if 'ui_controls__button_' in key else border
        by = min(sh//3, 70) if 'ui_controls__button_' in key else border
        xs, ys = [0, bx, sw-bx], [0, by, sh-by]
        widths, heights = [bx, sw-2*bx, bx], [by, sh-2*by, by]
        dx, dy = [left, left+border, left+width-border], [bottom, bottom+border, bottom+height-border]
        dw, dh = [border, width-2*border, border], [border, height-2*border, border]
        image.opacify(alpha)
        for row in range(3):
            for col in range(3):
                image.clip_draw(xs[col], ys[row], widths[col], heights[row], round(dx[col]+dw[col]/2), round(dy[row]+dh[row]/2), max(1, round(dw[col])), max(1, round(dh[row])))
        image.opacify(1)


class Motion:
    def __init__(self, assets, key):
        self.assets = assets
        self.key, self.age, self.serial = key, 0.0, 0

    def play(self, key, restart=False):
        if restart or key != self.key:
            self.key, self.age = key, 0
            self.serial += 1

    @property
    def finished(self):
        c = self.assets.clips[self.key]
        return c.get('playback') != 'loop' and self.age >= self.assets.duration(self.key)

    def update(self, dt):
        self.age += dt

    def draw(self, x, y, camera, scale=1, facing=None, alpha=1):
        self.assets.draw(self.key, x, y, camera, scale, self.age, facing, alpha)
