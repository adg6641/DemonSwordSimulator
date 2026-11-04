"""검에서 천천히 피어오르는 오라. 좌표는 화면 왼쪽 위 기준."""

from math import exp, hypot, pi, sin


def smoke_draws(weapon, layout, clip, seconds, front=False):
    """현재·다음 시트 프레임을 섞어 그릴 위치와 투명도를 돌려준다.

    반환값마다 image.opacify(item['opacity']) 후 item['geometry']를 그린다.
    같은 함수를 인트로 합성과 실제 시작 화면에서 함께 사용할 수 있다.
    """
    count = 2 if front else layout.get('bladeEmitters', 5)
    start, end = weapon['bladeStart'], weapon['ground']
    points = [(start[0] + (end[0] - start[0]) * (i + .5) / count,
               start[1] + (end[1] - start[1]) * (i + .5) / count) for i in range(count)]
    if not front:
        points.append(end)
    frames = clip['frames']
    cycle = clip.get('cycleSeconds', len(frames) / clip.get('fps', 6))
    opacity = layout.get('frontSmokeOpacity', .08) if front else layout.get('smokeOpacity', .40)
    draws = []
    for i, (source_x, source_y) in enumerate(points):
        age = (seconds / cycle + i * .137) % 1
        position = age * len(frames)
        current, blend = int(position), position % 1
        scale = layout.get('socketSmokeScale', 2.4) if not front and i == len(points) - 1 else layout.get('smokeScale', 2.0)
        if front:
            scale *= .62
        # 검 가까이의 연기는 발생 위치에 고정한다. 바깥 연기만 느리게 흩어진다.
        bands = [(0.0, 0.0, scale, opacity)]
        if not front:
            direction = -1 if i % 2 else 1
            dx, dy = direction * 18 * age, -12 * age
            fade = sin(pi * age) ** 2 * exp(-hypot(dx, dy) / 36)
            bands.append((dx, dy, scale * 1.16, opacity * .24 * fade))
        for dx, dy, size, alpha in bands:
            for index, weight in ((current, 1 - blend), ((current + 1) % len(frames), blend)):
                if alpha * weight < .0001:
                    continue
                frame = frames[index]
                emitter_x, emitter_y = frame.get('emitter', clip['emitter'])
                draws.append({'frameIndex': index, 'opacity': alpha * weight,
                    'geometry': {'crop': (frame['x'], frame['y'], frame['x'] + frame['w'], frame['y'] + frame['h']),
                        'left': source_x + dx - emitter_x * size,
                        'top': source_y + dy - emitter_y * size,
                        'width': frame['w'] * size, 'height': frame['h'] * size}})
    return draws
