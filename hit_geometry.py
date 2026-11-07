"""보이는 이펙트의 픽셀 띠와 검날 선분으로 타격을 확인한다."""
from math import cos, sin, ceil


def overlaps(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _polygon_rect(polygon, rectangle):
    """회전된 네모와 픽셀 띠가 겹치는지 분리축으로 검사한다."""
    left, top, right, bottom = rectangle
    corners = ((left, top), (right, top), (right, bottom), (left, bottom))
    axes = [(1, 0), (0, 1)]
    for i in range(2):
        a, b = polygon[i], polygon[i+1]
        axes.append((a[1]-b[1], b[0]-a[0]))
    for x, y in axes:
        p = [a*x+b*y for a, b in polygon]
        q = [a*x+b*y for a, b in corners]
        if max(p) < min(q) or max(q) < min(p):
            return False
    return True


def effect_hits(geometry, anchor, facing, target, masks):
    """그릴 때 쓰는 원점·배율·회전을 그대로 뒤집어 알파 마스크와 비교한다."""
    if not geometry or geometry.get('alpha', 1) < .025:
        return False
    ox, oy = geometry['origin']
    scale = geometry['scale']
    ca, sa = cos(geometry['angle']), sin(geometry['angle'])
    polygon = []
    for x, y in ((target[0], target[1]), (target[2], target[1]),
                 (target[2], target[3]), (target[0], target[3])):
        dx = (x-anchor[0])*facing-geometry['x']
        dy = anchor[1]-y-geometry['y']
        polygon.append(((dx*ca+dy*sa)/scale+ox, (-dx*sa+dy*ca)/scale+oy))
    bounds = (min(p[0] for p in polygon), min(p[1] for p in polygon),
              max(p[0] for p in polygon), max(p[1] for p in polygon))
    if not overlaps(bounds, geometry['bounds']):
        return False
    rectangles = masks[geometry['name']][geometry['frame']]
    return any(overlaps(bounds, rect) and _polygon_rect(polygon, rect) for rect in rectangles)


def blade_hits(hand, tip, target, radius=4.5):
    """기울어진 검의 빈 사각 모서리는 제외하고 실제 칼날에만 두께를 준다."""
    left, bottom, right, top = target
    dx, dy = tip[0]-hand[0], tip[1]-hand[1]
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, hand[0]-left+radius), (dx, right-hand[0]+radius),
                 (-dy, hand[1]-bottom+radius), (dy, top-hand[1]+radius)):
        if abs(p) < 1e-9:
            if q < 0:
                return False
        elif p < 0:
            lo = max(lo, q/p)
        else:
            hi = min(hi, q/p)
        if lo > hi:
            return False
    return True


def sweep_ages(start, end, speed, spacing=6):
    count = max(1, ceil(abs(end-start)*speed/spacing))
    return [start+(end-start)*i/count for i in range(count+1)]
