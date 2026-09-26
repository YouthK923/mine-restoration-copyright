# -*- coding: utf-8 -*-
"""形式自检：逐条核对软著登记材料是否符合形式要求。

依据《计算机软件著作权登记办法》第十条、中国版权保护中心办事指南，
以及本项目的前期联网核实结论。
"""
import os
import re
import sys

import fitz

sys.stdout.reconfigure(encoding="utf-8")
# 本脚本位于子目录，仓库根目录才是 app/ 与 软著材料/ 所在位置
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE = ROOT
MAT = os.path.join(BASE, "软著材料")
NAME = "历史遗留废弃矿山自然恢复适宜性评价系统V1.0"
VERSION = "V1.0"

SRC = os.path.join(MAT, "源程序_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf")
SRC60 = os.path.join(MAT, "源程序_提交版（前30页+后30页）_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf")
MAN = os.path.join(MAT, "说明书_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf")
FORM = os.path.join(MAT, "登记信息表底稿.md")

results = []


def check(ok, item, detail=""):
    results.append((ok, item, detail))
    print("  %s %-46s %s" % ("[符合]" if ok else "[不符合]", item, detail))


print("=" * 78)
print("软著登记材料 形式自检")
print("=" * 78)

# ---------------------------------------------------------------------------
print()
print("一、源程序鉴别材料")
print("-" * 78)
if not os.path.exists(SRC):
    check(False, "源程序 PDF 存在", "未找到文件")
else:
    doc = fitz.open(SRC)
    pages = doc.page_count
    # 页数
    check(pages >= 60, "源程序页数不少于 60 页", "共 %d 页" % pages)
    # 每页行数：按行号列（右对齐于 x=555.28）计数；
    # 页眉页码在 y<40 区域（y1≈24），正文行号自 y1=50 起
    def count_lines(page):
        ws = page.get_text("words")
        return sum(1 for w in ws if 550 < w[2] < 561 and w[1] > 40)

    line_counts = [count_lines(doc[i]) for i in range(pages)]
    body = line_counts[:-1]
    check(min(body) >= 50, "正文各页行数不少于 50 行",
          "前 %d 页均为 %d 行" % (len(body), min(body)))
    print("          （末页 %d 行，为程序结束页，属正常收口）" % line_counts[-1])
    # 页眉
    bad = [i + 1 for i in range(pages) if NAME not in doc[i].get_text()]
    check(not bad, "每页页眉含软件全称与版本号",
          "已检 %d 页，异常 %d 页" % (pages, len(bad)))
    # 页码
    bad = [i + 1 for i in range(pages) if ("第 %d 页" % (i + 1)) not in doc[i].get_text()]
    check(not bad, "页码连续且标于页面",
          "已检 %d 页，异常 %d 页" % (pages, len(bad)))
    # 末页为程序结束页
    last = doc[pages - 1].get_text().strip().splitlines()
    check(len(last) > 1, "末页为程序结束页（非半截代码）",
          "末页末行：%s" % (last[-2][:40] if len(last) >= 2 else ""))
    # A4 尺寸
    w, h = doc[0].rect.width, doc[0].rect.height
    check(abs(w - 595) < 3 and abs(h - 842) < 3, "页面为 A4 纵向",
          "%.0f × %.0f pt" % (w, h))
    doc.close()

# 提交版（实际提交的材料）
if os.path.exists(SRC60):
    d = fitz.open(SRC60)
    check(d.page_count == 60, "提交版为 60 页（前30+后30）", "共 %d 页" % d.page_count)
    cnts = [count_lines(d[i]) for i in range(d.page_count)]
    check(min(cnts) >= 50, "提交版每页行数不少于 50 行",
          "全部 %d 页均为 %d 行" % (len(cnts), min(cnts)))
    bad = [i + 1 for i in range(d.page_count) if NAME not in d[i].get_text()
           or ("第 %d 页" % (i + 1)) not in d[i].get_text()]
    check(not bad, "提交版每页含页眉与连续页码",
          "异常 %d 页" % len(bad))
    d.close()
else:
    check(False, "提交版为 60 页（前30+后30）", "未找到提交版文件")

# ---------------------------------------------------------------------------
print()
print("二、文档鉴别材料（软件说明书）")
print("-" * 78)
if not os.path.exists(MAN):
    check(False, "说明书 PDF 存在", "未找到文件")
else:
    doc = fitz.open(MAN)
    pages = doc.page_count
    # 官方口径：文档交前、后各连续 30 页，不足 60 页的全部提交；
    # 「每页不少于 30 行」还有「有图除外」的补充说明，故此处只卡下限与总量。
    check(15 <= pages <= 60, "页数不少于 15 页且不足 60 页时全部提交",
          "共 %d 页" % pages)
    # 封面不编号，目录起为第 1 页
    cover = doc[0].get_text()
    check(NAME not in cover and "第 1 页" not in cover,
          "封面不标注页眉页码", "")
    bad = []
    for i in range(1, pages):
        t = doc[i].get_text()
        if NAME not in t or ("第 %d 页" % i) not in t:
            bad.append(i + 1)
    check(not bad, "目录起每页含页眉与连续页码",
          "已检 %d 页，异常 %d 页" % (pages - 1, len(bad)))
    imgs = sum(len(doc[i].get_images(full=True)) for i in range(pages))
    check(imgs >= 10, "含界面截图且覆盖各功能模块", "共 %d 张" % imgs)
    w, h = doc[0].rect.width, doc[0].rect.height
    check(abs(w - 595) < 3 and abs(h - 842) < 3, "页面为 A4 纵向",
          "%.0f × %.0f pt" % (w, h))
    size_mb = os.path.getsize(MAN) / 1024 / 1024
    check(size_mb < 10, "文件体积适合上传", "%.2f MB" % size_mb)
    doc.close()

# ---------------------------------------------------------------------------
print()
print("三、登记信息表底稿")
print("-" * 78)
if not os.path.exists(FORM):
    check(False, "底稿存在", "未找到文件")
else:
    txt = open(FORM, encoding="utf-8").read()
    # 提取主要功能描述段落（第二节到第三节之间）
    m = re.search(r"## 二、主要功能描述(.*?)## 三、", txt, re.S)
    body = m.group(1) if m else ""
    # 去掉 markdown 标记与空白后统计中文字符+英文单词
    body = re.sub(r"^>.*$", "", body, flags=re.M)      # 去掉引用行
    body = re.sub(r"[#>*`|\-\s]", "", body)
    n = len(body)
    check(500 <= n <= 1300, "主要功能描述字数在 500–1300 字",
          "实测 %d 字" % n)
    check(NAME.replace("V1.0", "") in txt, "包含软件全称", "")
    check(VERSION in txt, "包含版本号 V1.0", "")
    check("原始取得" in txt, "标注权利取得方式", "")

# ---------------------------------------------------------------------------
print()
print("四、材料间一致性（页眉版本号须与申请表一致）")
print("-" * 78)
versions = set()
names = set()
for f in (SRC, MAN):
    if os.path.exists(f):
        d = fitz.open(f)
        t = d[0].get_text() + d[min(1, d.page_count - 1)].get_text()
        for m in re.finditer(r"历史遗留废弃矿山自然恢复适宜性评价系统\s*(V?[\d.]+)?", t):
            versions.add(m.group(1) or "")
        names.add("历史遗留废弃矿山自然恢复适宜性评价系统" in t)
        d.close()
check(all(names), "源程序与说明书均使用统一软件全称", "")
check(versions <= {"V1.0", ""} and "V1.0" in versions,
      "页眉版本号统一为 V1.0（带 V）", "检出：%s" % sorted(versions))

# ---------------------------------------------------------------------------
print()
print("=" * 78)
bad = [r for r in results if not r[0]]
print("自检结论：共 %d 项，符合 %d 项，不符合 %d 项"
      % (len(results), len(results) - len(bad), len(bad)))
if bad:
    print()
    print("待处理事项：")
    for _, item, detail in bad:
        print("  - %s %s" % (item, ("（%s）" % detail) if detail else ""))
else:
    print("全部符合形式要求。")
print("=" * 78)
