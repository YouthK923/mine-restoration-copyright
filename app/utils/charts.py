# -*- coding: utf-8 -*-
"""轻量图表。

用纯 SVG 输出，不依赖任何绘图库或前端脚本：
- 服务端渲染，页面与打印（PDF）中都能稳定显示
- 每个图元都带数值标签，黑白打印时仍可读（不单靠颜色区分）
- 单色方案，符合界面「一个视图一个强调色」的约定
"""
from html import escape

ACCENT = "#559FCF"
ACCENT_SOFT = "#64BBE0"
INK = "#23262b"
MUTED = "#6b7280"
LINE = "#dfe3e8"

# 科研顶刊配色
GRAYS = ["#6FAE47", "#FCE5D6", "#FFF2CC", "#DAE3F2", "#E9C9C9", "#559FCF"]


def _num(v):
    """图表里容忍空值：None / 非数字按 0 处理，避免一条脏数据把页面打成 500。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _fmt(v, digits=4):
    try:
        return ("%%.%df" % digits) % float(v)
    except (TypeError, ValueError):
        return str(v)


def hbars(items, width=620, bar_h=22, gap=12, label_w=150, value_w=76):
    """水平条形图。items: [(标签, 数值, 显示文本)]"""
    if not items:
        return '<p class="muted">暂无数据</p>'
    n = len(items)
    height = n * (bar_h + gap) + 10
    max_v = max((abs(_num(v)) for _, v, _ in items), default=1) or 1
    body_w = width - label_w - value_w

    parts = ['<svg viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="条形图" '
             'style="max-width:%dpx;font-family:inherit;">' % (width, height, height, width)]
    for i, (label, value, disp) in enumerate(items):
        y = i * (bar_h + gap) + 5
        frac = (abs(_num(value)) / max_v) if max_v else 0
        w = max(2.0, body_w * frac)
        fill = GRAYS[i % len(GRAYS)]
        parts.append(
            '<text x="%d" y="%d" text-anchor="end" font-size="12" fill="%s">%s</text>'
            % (label_w - 10, y + bar_h * 0.72, INK, escape(str(label))))
        parts.append(
            '<rect x="%d" y="%d" width="%.1f" height="%d" rx="3" fill="%s"/>'
            % (label_w, y, w, bar_h, fill))
        parts.append(
            '<text x="%d" y="%d" font-size="12" fill="%s" '
            'style="font-variant-numeric:tabular-nums;">%s</text>'
            % (label_w + w + 8, y + bar_h * 0.72, MUTED, escape(str(disp))))
    parts.append('</svg>')
    return "".join(parts)


def donut(items, size=210, thickness=34):
    """环形图（权重分布）。items: [(标签, 数值, 显示文本)]

    图例中给出数值与占比，黑白打印时靠图例与灰度深浅区分。
    """
    vals = [(l, _num(v), d) for l, v, d in items if _num(v) > 0]
    if not vals:
        return '<p class="muted">暂无数据</p>'
    total = sum(v for _, v, _ in vals) or 1
    r = (size - thickness) / 2
    cx = cy = size / 2
    import math
    parts = ['<svg viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
             'aria-label="权重分布环形图">' % (size, size, size, size)]
    angle = -math.pi / 2
    for i, (label, v, disp) in enumerate(vals):
        sweep = 2 * math.pi * (v / total)
        a0, a1 = angle, angle + sweep
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        large = 1 if sweep > math.pi else 0
        parts.append(
            '<path d="M %.2f %.2f A %.2f %.2f 0 %d 1 %.2f %.2f" '
            'fill="none" stroke="%s" stroke-width="%d"/>'
            % (x0, y0, r, r, large, x1, y1, GRAYS[i % len(GRAYS)], thickness))
        angle = a1
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="12" '
                 'fill="%s">合计</text>' % (cx, cy - 2, MUTED))
    parts.append('<text x="%d" y="%d" text-anchor="middle" font-size="15" '
                 'fill="%s" style="font-variant-numeric:tabular-nums;">%s</text>'
                 % (cx, cy + 18, INK, _fmt(total, 4)))
    parts.append('</svg>')

    legend = ['<table style="width:auto;margin-top:10px;"><thead><tr>'
              '<th scope="col">项目</th><th scope="col">数值</th>'
              '<th scope="col">占比</th></tr></thead><tbody>']
    for i, (label, v, disp) in enumerate(vals):
        legend.append(
            '<tr><td style="text-align:left;">'
            '<span style="display:inline-block;width:10px;height:10px;'
            'border-radius:2px;background:%s;margin-right:6px;"></span>%s</td>'
            '<td class="mono">%s</td><td class="mono">%.1f%%</td></tr>'
            % (GRAYS[i % len(GRAYS)], escape(str(label)), escape(str(disp)),
               100.0 * v / total))
    legend.append('</tbody></table>')
    return ('<div style="display:flex;flex-wrap:wrap;gap:20px;align-items:center;">'
            + "".join(parts) + "".join(legend) + '</div>')