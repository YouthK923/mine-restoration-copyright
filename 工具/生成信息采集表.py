# -*- coding: utf-8 -*-
r"""生成代办方的《软件著作权信息采集表》填写稿（对应附件1）。

- 字段顺序与附件1完全一致，逐项给出本软件应填内容
- 只有申请人才能确定的四项（著作权人、开发完成日期、首次发表日期、申请人）
  标为「待填」并用红色显示
- 「软件的主要功能」直接从 软著材料/登记信息表底稿.md 里取，避免两处不一致

用法：python 工具/生成信息采集表.py
输出：软著材料/附件1_软件著作权信息采集表_填写稿.docx
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "软著材料" / "附件1_软件著作权信息采集表_填写稿.docx"
DRAFT = ROOT / "软著材料" / "登记信息表底稿.md"

CN = "宋体"
HEI = "黑体"
RED = RGBColor(0xC0, 0x00, 0x00)


def style_run(run, size=10.5, bold=False, name=CN, color=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = name
    run.font.color.rgb = color or RGBColor(0, 0, 0)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def main_features():
    """从底稿里取出「软件的主要功能」正文。"""
    text = DRAFT.read_text(encoding="utf-8")
    body = text.split("## 二、主要功能描述", 1)[1].split("---", 1)[0]
    lines = [ln.strip() for ln in body.splitlines()
             if ln.strip() and not ln.strip().startswith(">")]
    return "\n".join(lines)


ROWS = [
    ("一、软件基本信息", None),
    ("软件全称", "历史遗留废弃矿山自然恢复适宜性评价系统"),
    ("软件简称", "（无简称，留空）"),
    ("版本号", "V1.0"),
    ("软件分类", "应用软件"),
    ("软件作品说明", "原创"),
    ("开发完成日期", "待填"),
    ("发表状态", "已发表（建议；对权利保护最充分）"),
    ("首次发表日期", "待填"),
    ("首次发表地点", "待填（例：2026.10.8  河北  唐山）"),
    ("开发方式", "独立开发"),
    ("二、著作权人", None),
    ("姓名或名称", "待填（单位填工商登记全称，个人填身份证姓名）"),
    ("证件类型", "待填"),
    ("证件号码", "待填（统一社会信用代码或身份证号）"),
    ("省份/城市", "待填"),
    ("三、权利说明", None),
    ("权利取得方式", "原始取得"),
    ("权利范围", "全部"),
    ("四、软件鉴别材料", None),
    ("交存方式", "一般交存"),
    ("源程序", "《源程序_提交版（前30页+后30页）_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf》"
             "共 60 页，每页 50 行"),
    ("文档", "一种文档：《历史遗留废弃矿山自然恢复适宜性评价系统V1.0 操作使用手册》，"
           "共 31 页（不足 60 页全部提交），含 29 张界面插图"),
    ("五、软件功能和技术特点", None),
    ("开发的硬件环境", "x86-64 计算机，四核 CPU 及以上，内存 8GB 及以上"),
    ("运行的硬件环境", "x86-64 计算机，双核 CPU 及以上，内存 4GB 及以上，磁盘可用 500MB"),
    ("开发该软件的操作系统", "Windows 10 64 位 / Windows 11 64 位"),
    ("软件开发环境 / 开发工具", "Python 3.12、Flask 3.0、SQLAlchemy 2.0、Jinja2、VS Code"),
    ("该软件的运行平台 / 操作系统", "Windows 10 / Windows 11 64 位（Python 3.10 及以上）"),
    ("软件运行支撑环境 / 支持软件", "Flask、SQLAlchemy、NumPy、openpyxl；SQLite 数据库"),
    ("编程语言", "Python"),
    ("源程序量", "11883 行（不含空行；含空行 13330 行，源程序材料共 279 页）"),
    ("开发目的", "为历史遗留废弃矿山自然恢复适宜性评价提供定量计算与标准对照工具，支撑生态修复决策"),
    ("面向领域 / 行业", "矿山生态修复、自然资源调查监测、国土空间生态治理"),
    ("软件的主要功能", None),          # 由底稿填入
    ("软件的技术特点", "以层次分析法自动定权并按微地质单元分别赋权，四类标准化与面积加权合成，"
                    "地方标准规则化对照，评价过程逐层可追溯、结果可复核"),
]
LIMITS = {"开发的硬件环境": 50, "运行的硬件环境": 50, "开发该软件的操作系统": 50,
          "软件开发环境 / 开发工具": 50, "该软件的运行平台 / 操作系统": 50,
          "软件运行支撑环境 / 支持软件": 50, "开发目的": 50, "面向领域 / 行业": 50,
          "软件的技术特点": 100, "软件的主要功能": 1300}


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Pt(56)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_run(t.add_run("计算机软件著作权登记 · 信息采集表（填写稿）"), 15, True, HEI)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_run(sub.add_run("对应代办方《附件1-新系统-软件著作权信息采集表》，"
                          "字段与顺序一致，可直接照抄填写"), 9)

    tb = doc.add_table(rows=1, cols=2)
    tb.style = "Table Grid"
    hdr = tb.rows[0].cells
    for c, text in zip(hdr, ("字段", "填写内容")):
        c.text = ""
        style_run(c.paragraphs[0].add_run(text), 10.5, True, HEI)
    tb.columns[0].width = Pt(150)

    warns = []
    for field, value in ROWS:
        row = tb.add_row().cells
        if value is None and field.endswith(("信息", "说明", "材料", "特点")) and field[0] in "一二三四五":
            # 分组标题行：跨两列
            row[0].merge(row[1])
            p = row[0].paragraphs[0]
            style_run(p.add_run(field), 11, True, HEI)
            continue
        style_run(row[0].paragraphs[0].add_run(field), 10.5, True)
        content = value if value is not None else main_features()
        p = row[1].paragraphs[0]
        is_todo = content.startswith("待填")
        style_run(p.add_run(content), 10.5, False, CN, RED if is_todo else None)
        lim = LIMITS.get(field)
        if lim:
            n = len(re.sub(r"\s", "", content))
            if n > lim:
                warns.append("%s：实际 %d 字，超出上限 %d 字" % (field, n, lim))
            else:
                warns.append("%s：%d/%d 字" % (field, n, lim))

    tail = doc.add_paragraph()
    style_run(tail.add_run("待申请人确定：著作权人（名称、证件类型、证件号码、省份/城市）、"
                           "开发完成日期、首次发表日期与地点。"), 10.5, True, CN, RED)
    note = doc.add_paragraph()
    style_run(note.add_run("说明：手册与源程序材料已按代办方模板制作——"
                           "手册封面为《操作使用手册》（版本 V1.0，含申请人栏），"
                           "章节为「一、系统简介 / 二、主要功能 / 三、计算方法与口径说明」，"
                           "插图按 图1…图29 编号；源程序提交版与前 30 页 + 后 30 页共 3000 行，"
                           "另有全文 Word（13901 行）备查。"), 9)

    doc.save(str(OUT))
    print("已生成：%s" % OUT.name)
    print("  行数：%d" % len(ROWS))
    print("  字数校验：")
    for w in warns:
        print("    " + w)


if __name__ == "__main__":
    main()
