# -*- coding: utf-8 -*-
"""生成软著申请用的源程序鉴别材料（PDF）。

按《计算机软件著作权登记办法》第十条及中国版权保护中心办事指南：
- A4 纵向、单面
- 页眉标注软件名称与版本号，须与申请表一致
- 页码标注于右上角
- 源程序每页不少于 50 行
- 最后一页应为程序的结束页

用法：
    python make_source_doc.py
输出：
    软著材料/源程序_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf
"""
import os
import sys

import fitz

sys.stdout.reconfigure(encoding="utf-8")
# 本脚本位于子目录，仓库根目录才是 app/ 与 软著材料/ 所在位置
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# 排版参数
# ---------------------------------------------------------------------------
SOFTWARE_NAME = "历史遗留废弃矿山自然恢复适宜性评价系统V1.0"
LINES_PER_PAGE = 50          # 每页行数（要求不少于 50）
FONT = "china-s"             # 内置简体中文字体（同时支持 ASCII 半角）
FONT_SIZE = 8.0
LINE_HEIGHT = 14.0

PAGE_W, PAGE_H = 595.28, 841.89        # A4
MARGIN_L = 42
MARGIN_R = 40
HEADER_Y = 34
RULE_Y = 44
CODE_TOP = 58
NUM_X = PAGE_W - MARGIN_R             # 行号右对齐位置
AVAIL_W = NUM_X - MARGIN_L - 26       # 代码文本可用宽度（右侧留出行号空间）

BASE = ROOT
OUT_DIR = os.path.join(BASE, "软著材料")

# 字体缺字替换：这些字符在当前字体中渲染为空白，替换为等价可显示字符
CHAR_SUB = {
    "ᵢ": "i",      # 下标 i，出现在注释里的 Sᵢ / F′ᵢ
    "✓": "√",
    "✔": "√",
    "✗": "×",
    "✘": "×",
}


def sanitize(text):
    """替换字体无法渲染的字符，避免出现空白。"""
    for k, v in CHAR_SUB.items():
        if k in text:
            text = text.replace(k, v)
    return text

# 纳入源程序的文件顺序（按程序结构逻辑排列）
SOURCE_ORDER = [
    "run.py",
    "app/__init__.py",
    "app/config.py",
    "app/models.py",
    "app/forms.py",
    "app/utils/constants.py",
    "app/utils/schema.py",
    "app/utils/uploads.py",
    "app/utils/charts.py",
    "app/utils/browser.py",
    "app/services/ahp_service.py",
    "app/services/standardization.py",
    "app/services/weight_service.py",
    "app/services/evaluation_service.py",
    "app/services/report_service.py",
    "app/services/indicator_service.py",
    "app/services/import_service.py",
    "app/services/workflow.py",
    "app/services/dashboard.py",
    "app/services/audit.py",
    "app/views/auth.py",
    "app/views/project.py",
    "app/views/unit.py",
    "app/views/standard.py",
    "app/views/constraint.py",
    "app/views/ahp.py",
    "app/views/indicator.py",
    "app/views/evaluate.py",
    "app/views/report.py",
    "app/views/search.py",
    "app/templates/base.html",
    "app/templates/_macros.html",
    "app/templates/_login_badge.svg",
    "app/templates/error.html",
    "app/templates/auth/login.html",
    "app/templates/auth/home.html",
    "app/templates/auth/users.html",
    "app/templates/auth/add_user.html",
    "app/templates/auth/edit_user.html",
    "app/templates/auth/logs.html",
    "app/templates/project/index.html",
    "app/templates/project/edit.html",
    "app/templates/project/patches.html",
    "app/templates/project/patch_edit.html",
    "app/templates/unit/list.html",
    "app/templates/unit/index.html",
    "app/templates/unit/edit.html",
    "app/templates/standard/index.html",
    "app/templates/standard/edit.html",
    "app/templates/standard/rules.html",
    "app/templates/standard/compare.html",
    "app/templates/constraint/index.html",
    "app/templates/constraint/check.html",
    "app/templates/ahp/index.html",
    "app/templates/ahp/matrix.html",
    "app/templates/ahp/indicators.html",
    "app/templates/ahp/indicator_edit.html",
    "app/templates/ahp/experts.html",
    "app/templates/ahp/experts_aggregate.html",
    "app/templates/indicator/index.html",
    "app/templates/indicator/edit.html",
    "app/templates/indicator/import.html",
    "app/templates/evaluate/index.html",
    "app/templates/evaluate/run.html",
    "app/templates/evaluate/result.html",
    "app/templates/report/index.html",
    "app/templates/report/detail.html",
    "app/templates/report/print.html",
    "app/templates/search.html",
    "seed_demo.py",
    "测试/test_ahp.py",
    "测试/test_evaluate.py",
    "测试/test_web_ahp.py",
    "测试/test_web_modules.py",
    "测试/test_web_evaluate.py",
    "测试/test_web_report.py",
    "测试/test_ui_fixes.py",
    "测试/test_new_features.py",
    "测试/test_workflow.py",
    "测试/test_weights.py",
]


def wrap_line(line):
    """按实际渲染宽度折行，保证不侵入右侧行号列。"""
    if fitz.get_text_length(line, fontname=FONT, fontsize=FONT_SIZE) <= AVAIL_W:
        return [line]
    out = []
    rest = line
    while fitz.get_text_length(rest, fontname=FONT, fontsize=FONT_SIZE) > AVAIL_W:
        # 二分查找可容纳的最大前缀
        lo, hi = 1, len(rest)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fitz.get_text_length(rest[:mid], fontname=FONT,
                                    fontsize=FONT_SIZE) <= AVAIL_W:
                lo = mid
            else:
                hi = mid - 1
        cut = lo
        # 尽量在空格处断开，避免把词切断
        sp = rest.rfind(" ", 0, cut)
        if sp > cut * 0.6:
            cut = sp
        out.append(rest[:cut])
        rest = "    " + rest[cut:].lstrip()
    out.append(rest)
    return out


def collect_lines():
    """收集全部源码行（去除空行，保证每页均为有效行）。

    SOURCE_ORDER 决定文件顺序；未被列出的 .py/.html 自动补在末尾，
    避免新增文件漏收（漏收会导致材料与实际代码不一致）。
    """
    listed = [p for p in SOURCE_ORDER if os.path.exists(os.path.join(BASE, p))]
    seen = set(listed)
    extra = []
    # 只在 app/ 下自动补齐：根目录多为文档生成与核对工具，不属于软件本体，
    # 需要收录的根目录脚本已在 SOURCE_ORDER 中显式列出。
    for root, dirs, files in os.walk(os.path.join(BASE, "app")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            if not f.endswith((".py", ".html")):
                continue
            rel = os.path.relpath(os.path.join(root, f), BASE).replace("\\", "/")
            if rel not in seen:
                extra.append(rel); seen.add(rel)

    lines = []
    for rel in listed + sorted(extra):
        path = os.path.join(BASE, rel)
        if not os.path.exists(path):
            print("  [警告] 文件不存在，跳过:", rel)
            continue
        banner = "# ==== %s ====" % rel
        lines.append(banner)
        with open(path, encoding="utf-8") as f:
            for raw in f:
                s = raw.rstrip("\r\n")
                if not s.strip():
                    continue          # 去空行：保证每页均为有效代码行
                lines.extend(wrap_line(sanitize(s)))
    return lines


def draw_page(doc, page_no, chunk):
    """渲染一页。"""
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    # 页眉：软件名称 + 版本号（左），页码（右上角）
    page.insert_text((MARGIN_L, HEADER_Y), SOFTWARE_NAME,
                     fontname=FONT, fontsize=10)
    pn = "第 %d 页" % page_no
    tw = fitz.get_text_length(pn, fontname=FONT, fontsize=10)
    page.insert_text((PAGE_W - MARGIN_R - tw, HEADER_Y), pn,
                     fontname=FONT, fontsize=10)
    page.draw_line(fitz.Point(MARGIN_L, RULE_Y),
                   fitz.Point(PAGE_W - MARGIN_R, RULE_Y),
                   color=(0, 0, 0), width=0.6)

    # 代码正文
    y = CODE_TOP
    for ln, text in chunk:
        page.insert_text((MARGIN_L, y), text, fontname=FONT, fontsize=FONT_SIZE)
        ns = str(ln)
        nw = fitz.get_text_length(ns, fontname=FONT, fontsize=FONT_SIZE)
        page.insert_text((NUM_X - nw, y), ns, fontname=FONT, fontsize=FONT_SIZE)
        y += LINE_HEIGHT
    return page


def build_pdf(all_lines, out_path):
    doc = fitz.open()
    pages = 0
    for i in range(0, len(all_lines), LINES_PER_PAGE):
        chunk = all_lines[i:i + LINES_PER_PAGE]
        pages += 1
        draw_page(doc, pages, chunk)
    doc.save(out_path)
    doc.close()
    return pages


def extract_60(all_lines, out_path):
    """程序超过 60 页时，另出一份「前 30 页 + 后 30 页」的提交版。"""
    per = LINES_PER_PAGE
    front = all_lines[:30 * per]
    back = all_lines[-30 * per:]
    doc = fitz.open()
    for i in range(0, len(front), per):
        draw_page(doc, i // per + 1, front[i:i + per])
    for k, i in enumerate(range(0, len(back), per)):
        draw_page(doc, 31 + k, back[i:i + per])
    doc.save(out_path)
    doc.close()
    return 60


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("收集源程序…")
    lines = collect_lines()
    numbered = [(i + 1, t) for i, t in enumerate(lines)]
    print("  有效代码行数：%d" % len(numbered))
    print("  文件数：%d" % len(SOURCE_ORDER))

    full = os.path.join(OUT_DIR,
                        "源程序_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf")
    pages = build_pdf(numbered, full)
    print()
    print("已生成源程序全文：%s" % os.path.relpath(full, BASE))
    print("  总页数：%d（每页固定 %d 行）" % (pages, LINES_PER_PAGE))

    if pages > 60:
        sub = os.path.join(
            OUT_DIR,
            "源程序_提交版（前30页+后30页）_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf")
        extract_60(numbered, sub)
        print("已生成提交版（前 30 页 + 后 30 页）：%s"
              % os.path.relpath(sub, BASE))
    else:
        print("总页数不足 60 页，按登记要求应提交全部源程序。")

    # 校验
    chk = fitz.open(full)
    print()
    print("校验：")
    print("  页数：%d" % chk.page_count)
    p0 = chk[0].get_text().strip().splitlines()
    print("  首页首行（页眉）：%s" % p0[0] if p0 else "  （空）")
    print("  首页含页码：%s" % ("第 1 页" in chk[0].get_text()))
    last = chk[chk.page_count - 1].get_text().strip().splitlines()
    print("  末页末行：%s" % (last[-2] if len(last) >= 2 else "(空)"))
    chk.close()


if __name__ == "__main__":
    main()
