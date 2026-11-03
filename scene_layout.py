"""인트로와 시작 화면이 함께 사용하는 검·지면·연기 위치. 좌표는 왼쪽 위 기준."""


def sword_layout(weapon, layout, grip=None):
    x0, y0, x1, y1 = weapon['crop']
    visible = (y1 - y0) * layout['visibleFraction']
    cut = y0 + visible
    start, tip = weapon['bladeStart'], weapon['tip']
    axis_x = start[0] + (tip[0] - start[0]) * (cut - start[1]) / (tip[1] - start[1])
    scale = layout['visibleHeight'] / visible
    left = layout['ground'][0] - (axis_x - x0) * scale
    top = layout['ground'][1] - visible * scale
    if grip is not None:
        left = grip[0] - (weapon['grip'][0] - x0) * scale
        top = grip[1] - (weapon['grip'][1] - y0) * scale
    bottom = min(y1, y0 + max(0, (layout['ground'][1] - top) / scale))
    point = lambda p: (left + (p[0] - x0) * scale, top + (p[1] - y0) * scale)
    return {'crop': (x0, y0, x1, bottom), 'left': left, 'top': top, 'scale': scale,
            'width': (x1 - x0) * scale, 'height': (bottom - y0) * scale,
            'grip': point(weapon['grip']), 'bladeStart': point(start), 'tip': point(tip),
            'ground': tuple(layout['ground'])}


def socket_layout(socket, layout, front=False):
    x0, y0, x1, y1 = socket['crop']
    scale = layout['socketWidth'] / (x1 - x0)
    left = layout['ground'][0] - (socket['socket'][0] - x0) * scale
    top = layout['ground'][1] - (socket['socket'][1] - y0) * scale
    if front:
        top += (socket['socket'][1] - y0) * scale
        y0 = socket['socket'][1]
    return {'crop': (x0, y0, x1, y1), 'left': left, 'top': top,
            'width': (x1 - x0) * scale, 'height': (y1 - y0) * scale}


def smoke_sites(geometry, count):
    start, end = geometry['bladeStart'], geometry['ground']
    return [(start[0] + (end[0] - start[0]) * u, start[1] + (end[1] - start[1]) * u)
            for u in (.05 + .90 * i / (count - 1) for i in range(count))]
