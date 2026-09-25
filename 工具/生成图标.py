# -*- coding: utf-8 -*-
"""生成系统图标（.ico），同时用作网页图标与桌面快捷方式图标。

用 PyMuPDF 绘制矢量图形再栅格化为 PNG，按 ICO 容器格式打包。
不依赖 Pillow —— 本环境的 matplotlib / Pillow 不可用。

用法：
    python 工具/生成图标.py
输出：
    app/static/favicon.ico
"""
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")

import fitz

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "app", "static", "favicon.ico")

# 尺寸：Windows 会按需缩放，256 用于大图标，16 用于任务栏小图标
SIZES = (256, 128, 64, 48, 32, 16)

# 配色：深绿底 + 白色山形 + 浅绿前景山
BG = (0.13, 0.42, 0.24)          # #216b3d 深绿
MTN_BACK = (0.72, 0.86, 0.76)    # 浅绿
MTN_FRONT = (1.0, 1.0, 1.0)      # 白


def draw(size):
    """把图标画在 size×size 的页面上，返回 PNG 字节（带透明通道）。"""
    doc = fitz.open()
    page = doc.new_page(width=size, height=size)
    s = size / 256.0            # 所有坐标按 256 基准书写，再按比例缩放

    def P(x, y):
        return fitz.Point(x * s, y * s)

    # 圆形底
    shape = page.new_shape()
    shape.draw_circle(P(128, 128), 124 * s)
    shape.finish(fill=BG, color=None)
    shape.commit()

    # 后山（浅绿）
    shape = page.new_shape()
    shape.draw_polyline([P(38, 196), P(104, 84), P(170, 196), P(38, 196)])
    shape.finish(fill=MTN_BACK, color=None, closePath=True)
    shape.commit()

    # 前山（白，偏右，形成层次）
    shape = page.new_shape()
    shape.draw_polyline([P(112, 196), P(170, 108), P(228, 196), P(112, 196)])
    shape.finish(fill=MTN_FRONT, color=None, closePath=True)
    shape.commit()

    # 太阳（白点）
    shape = page.new_shape()
    shape.draw_circle(P(186, 62), 20 * s)
    shape.finish(fill=MTN_FRONT, color=None)
    shape.commit()

    # 地平线（把山脚压平，避免两个三角形底边露白）
    shape = page.new_shape()
    shape.draw_line(P(30, 196), P(226, 196))
    shape.finish(color=BG, width=6 * s)
    shape.commit()

    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=True)
    data = pix.tobytes("png")
    doc.close()
    return data


def build_ico(pngs):
    """把若干 PNG 打包成 ICO 容器（Vista 起支持 PNG 载荷）。"""
    n = len(pngs)
    header = struct.pack("<HHH", 0, 1, n)          # reserved, type=icon, count
    entries, blobs = b"", b""
    offset = 6 + 16 * n
    for size, data in pngs:
        w = 0 if size >= 256 else size             # 0 表示 256
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32,
                               len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def main():
    pngs = [(size, draw(size)) for size in SIZES]
    data = build_ico(pngs)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as fh:
        fh.write(data)
    print("已生成图标：%s" % os.path.relpath(OUT, BASE))
    print("  尺寸：%s   总大小：%.1f KB"
          % ("、".join("%d×%d" % (s, s) for s in SIZES), len(data) / 1024))


if __name__ == "__main__":
    main()
