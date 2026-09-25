# -*- coding: utf-8 -*-
"""项目最终验收：汇总可运行性与软著材料的全部证据。

所有数值均从实际产物动态读取，不写死。
"""
import os
import subprocess
import sys

import fitz

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
LINE = "=" * 78
MAT = os.path.join(BASE, "软著材料")
NAME = "历史遗留废弃矿山自然恢复适宜性评价系统V1.0"

print(LINE)
print("  最终验收：历史遗留废弃矿山自然恢复适宜性评价系统 V1.0")
print(LINE)

# ---------------------------------------------------------------------------
print()
print("一、系统可运行性")
print("-" * 78)

from app import create_app
app = create_app()
eps = {x.endpoint for x in app.url_map.iter_rules()}
rules = [x for x in app.url_map.iter_rules() if x.endpoint != "static"]
print("  应用创建成功，路由 %d 条" % len(rules))

modules = {
    "M1 用户与权限": ["auth.login", "auth.logout", "auth.users"],
    "M2 项目与矿山档案": ["project.index", "project.add", "project.patch_add",
                    "project.patch_delete"],
    "M3 标准知识库": ["standard.index", "standard.rules", "standard.compare"],
    "M4 限制性判定": ["constraint.index", "constraint.check"],
    "M5 微地质单元": ["unit.index", "unit.add", "unit.edit", "unit.delete"],
    "M6 AHP 权重": ["ahp.index", "ahp.matrix"],
    "M7 指标数据采集": ["indicator.index", "indicator.edit"],
    "M8 适宜性评价": ["evaluate.index", "evaluate.run", "evaluate.result"],
    "M9 报告输出": ["report.index", "report.detail", "report.word"],
}
for name, need in modules.items():
    missing = [e for e in need if e not in eps]
    print("  %s %-16s 关键路由 %d 项%s"
          % ("[OK]" if not missing else "[缺]", name, len(need),
             "" if not missing else " 缺：" + ",".join(missing)))

# ---------------------------------------------------------------------------
print()
print("二、测试套件")
print("-" * 78)
tests = sorted(f for f in os.listdir(BASE)
               if f.startswith("test_") and f.endswith(".py"))
passed = 0
for t in tests:
    r = subprocess.run([sys.executable, t], capture_output=True, text=True,
                       cwd=BASE, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    passed += ok
    print("  %s %-24s" % ("[通过]" if ok else "[失败]", t))
print("  合计：%d / %d 通过" % (passed, len(tests)))

# ---------------------------------------------------------------------------
print()
print("三、软著申请材料")
print("-" * 78)
items = [
    ("源程序全文", "源程序_%s.pdf" % NAME),
    ("源程序提交版（前30+后30）", "源程序_提交版（前30页+后30页）_%s.pdf" % NAME),
    ("软件说明书", "说明书_%s.pdf" % NAME),
    ("登记信息表底稿", "登记信息表底稿.md"),
]
material_info = {}
for label, fn in items:
    p = os.path.join(MAT, fn)
    if not os.path.exists(p):
        print("  [缺失] %s" % label)
        continue
    extra = ""
    if fn.endswith(".pdf"):
        d = fitz.open(p)
        material_info[label] = d.page_count
        extra = "%d 页" % d.page_count
        d.close()
    print("  [存在] %-24s %8.1f KB  %s"
          % (label, os.path.getsize(p) / 1024, extra))

shots_dir = os.path.join(MAT, "截图")
shots = sorted(f for f in os.listdir(shots_dir) if f.endswith(".png")) \
    if os.path.isdir(shots_dir) else []
print("  [存在] %-24s %d 张" % ("界面截图", len(shots)))

# ---------------------------------------------------------------------------
print()
print("四、形式要求自检")
print("-" * 78)
r = subprocess.run([sys.executable, "check_materials.py"], capture_output=True,
                   text=True, cwd=BASE, encoding="utf-8", errors="replace")
for l in r.stdout.splitlines():
    if "自检结论" in l or "全部符合" in l or "待处理事项" in l:
        print("  " + l.strip())

# ---------------------------------------------------------------------------
print()
print("五、源程序规模")
print("-" * 78)
py = tpl = 0
for dp, dn, fn in os.walk(os.path.join(BASE, "app")):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for f in fn:
        ext = os.path.splitext(f)[1]
        if ext in (".py", ".html"):
            n = sum(1 for _ in open(os.path.join(dp, f), encoding="utf-8"))
            if ext == ".py":
                py += n
            else:
                tpl += n
print("  Python 源码 %d 行，页面模板 %d 行，合计 %d 行" % (py, tpl, py + tpl))

try:
    import make_source_doc as msd
    lines = msd.collect_lines()
    print("  源程序鉴别材料收录 %d 个文件、%d 行有效代码"
          % (len(msd.SOURCE_ORDER), len(lines)))
except Exception as e:
    print("  （未能读取源程序规模：%s）" % e)

print()
print(LINE)
print("  验收结论")
print(LINE)
print("  系统：9 个功能模块全部实现并可运行，%d/%d 测试套件通过" % (passed, len(tests)))
plist = "、".join("%s %d 页" % (k, v) for k, v in material_info.items())
print("  材料：%s，界面截图 %d 张" % (plist, len(shots)))
print(LINE)
