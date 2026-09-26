# -*- coding: utf-8 -*-
"""生成登录页的系统徽标（仿 Apple 账户页的圆点环 + 中心标识）。

Apple 的徽标是一圈圈彩色圆点围成圆形、中心放品牌标识。这里用绿色系
（呼应自然恢复主题）做同样结构的徽标：五圈圆点，半径与点径由内向外递增，
颜色沿圆周在「黄绿 → 翠绿 → 墨绿」之间渐变，中心放系统的山形标识。

输出为**模板片段**而不是静态图片：登录页用 {% include %} 把它内联进页面，
这样每一圈圆点都能被 CSS 单独控制（滚动时向四周散开并淡出）。
用 <img> 引入的外部 SVG，其内部元素无法被页面样式影响，所以必须内联。

每圈带一个 --k：滚动结束时该圈的放大倍数。由内向外递减，
使各圈相对拉开距离，视觉上是「散开」而不是整体放大。

用法：
    python 工具/生成登录徽标.py
输出：
    app/templates/_login_badge.svg
"""
import colorsys
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "app", "templates", "_login_badge.svg")

SIZE = 240.0
CENTER = SIZE / 2

# 五圈：(半径, 点数, 点径, 散开后的放大倍数)
RINGS = [
    (42.0, 14, 2.6, 2.70),
    (58.0, 20, 3.4, 2.15),
    (74.0, 26, 4.2, 1.85),
    (90.0, 32, 5.0, 1.62),
    (106.0, 38, 5.6, 1.46),
]


def dot_color(angle_deg, ring_index, ring_count):
    """沿圆周在绿色系里渐变；越靠内越淡，形成由浅入深的层次。"""
    t = (angle_deg % 360.0) / 360.0
    # 色相：100°（黄绿）→ 168°（青绿）再回到 100°
    hue = 100.0 + 68.0 * (1.0 - abs(2.0 * t - 1.0))
    # 外层饱和度略高、明度略低
    depth = ring_index / max(1, ring_count - 1)      # 0=最内 1=最外
    sat = 0.30 + 0.30 * depth
    val = 0.96 - 0.30 * depth
    r, g, b = colorsys.hsv_to_rgb(hue / 360.0, sat, val)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def build():
    parts = [
        '<svg class="lp-badge__svg" xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 %d %d" role="img" '
        'aria-label="历史遗留废弃矿山自然恢复适宜性评价系统徽标">'
        % (int(SIZE), int(SIZE)),
        "  <title>系统徽标</title>",
    ]
    n = len(RINGS)
    for i, (radius, count, dot, spread) in enumerate(RINGS):
        parts.append('  <g class="lp-ring" style="--k: %s">' % spread)
        for k in range(count):
            # 每圈错开半个步长，点阵更均匀
            angle = 360.0 * k / count + (180.0 / count if i % 2 else 0.0)
            rad = math.radians(angle)
            x = CENTER + radius * math.cos(rad)
            y = CENTER + radius * math.sin(rad)
            # 同一圈内点径也轻微变化，避免呆板
            scale = 0.82 + 0.36 * (0.5 + 0.5 * math.sin(math.radians(angle * 2 + i * 40)))
            r = dot * scale
            color = dot_color(angle, i, n)
            parts.append('    <circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>'
                         % (x, y, r, color))
        parts.append("  </g>")

    # 中心：深绿圆底 + 白色山形标识（与侧边栏、快捷方式图标同一意象）
    parts.append('  <g class="lp-badge__mark">')
    parts.append('    <circle cx="%.0f" cy="%.0f" r="27" fill="#14432f"/>' % (CENTER, CENTER))
    parts.append('    <g transform="translate(%.0f %.0f) scale(1.5) translate(-12 -12)" '
                 'fill="none" stroke="#ffffff" stroke-width="1.9" '
                 'stroke-linecap="round" stroke-linejoin="round">' % (CENTER, CENTER))
    parts.append('      <path d="m3 20 6.5-11L14 17l2.5-4L21 20z"/>')
    parts.append('      <circle cx="17" cy="6" r="2.2"/>')
    parts.append("    </g>")
    parts.append("  </g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    svg = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write(svg)
    # 旧版本放在 static/ 下作为独立图片，现已改为内联，清掉避免留孤儿文件
    stale = os.path.join(BASE, "app", "static", "login-badge.svg")
    if os.path.exists(stale):
        os.remove(stale)
        print("已移除旧文件：app/static/login-badge.svg")
    print("已生成徽标模板片段：%s" % os.path.relpath(OUT, BASE))
    print("  圆点：%d 个，分 %d 圈" % (sum(c for _r, c, _d, _s in RINGS),
                                     len(RINGS)))
    print("  大小：%.1f KB" % (len(svg.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
