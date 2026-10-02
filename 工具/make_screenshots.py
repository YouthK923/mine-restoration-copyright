# -*- coding: utf-8 -*-
"""自动生成说明书所需的界面截图。

以截图模式启动应用（自动以管理员登录），用 Chrome 无头模式逐页截图，
输出到 软著材料/截图/。

用法：
    python make_screenshots.py
"""
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
# 本脚本位于子目录，仓库根目录才是 app/ 与 软著材料/ 所在位置
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import (db, MinePatch, EvaluationResult, ConstraintCheck)
from app.views.evaluate import load_patch_input

BASE = ROOT
OUT_DIR = os.path.join(BASE, "软著材料", "截图")
PORT = 5099
HOST = "http://127.0.0.1:%d" % PORT
WIN_W = 1360          # 侧边栏布局需要更宽的视口

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_ARGS = [
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
    "--force-device-scale-factor=1",
    # 等页面动画（登录框淡入、提示浮层等）走完再截图，避免抓到中间态
    "--virtual-time-budget=2500",
]


class ShotConfig(Config):
    SCREENSHOT_MODE = True


def prepare_data(app):
    """确保案例与评价结果存在，供截图使用。

    返回 (图斑 id, 所属项目 id, 评价结果 id, 单元 id)。
    这几个 id 各有各的用途，别混：图斑列表页用**项目** id，
    指标录入页用**微地质单元** id，早期脚本写死过 2，结果截到 404。
    """
    with app.app_context():
        import seed_demo
        patch = seed_demo.demo_patch()      # 固定取演示案例，不取库中任意图斑
        if patch is None:
            print("  [警告] 数据库无图斑，请先运行 seed_demo.py")
            return None, None, None, None
        if ConstraintCheck.query.filter_by(patch_id=patch.id).first() is None:
            db.session.add(ConstraintCheck(
                patch_id=patch.id, policy_pass=True, location_pass=True,
                pollution_pass=True, geo_pass=True, farmland_pass=True,
                passed=True, reason="全部通过"))
            db.session.commit()
        res = EvaluationResult.query.filter_by(patch_id=patch.id) \
            .order_by(EvaluationResult.id.desc()).first()
        if res is None:
            # 用与网页相同的落库逻辑生成一次真实评价记录，
            # 保证结果页与报告页取到的是同一条记录
            from app.views.evaluate import save_evaluation
            res = save_evaluation(patch.id, load_patch_input(patch.id))
        from app.models import MicroUnit
        unit = MicroUnit.query.filter_by(patch_id=patch.id).first()
        if unit is None:
            print("  [警告] 演示图斑下没有微地质单元，指标录入页无法截图")
        return patch.id, patch.project_id, res.id, (unit.id if unit else None)


def build_page_list(pid, proj_id, rid, unit_id=None):
    return [
        ("01_登录", "/login", 900),
        # 带 #login 访问会直接展开登录框（见 auth/login.html 的脚本）
        ("01b_登录框", "/login#login", 900),
        ("02_系统首页", "/", 900),
        ("03_项目与档案", "/project/", 820),
        ("04_矿山图斑", "/project/%d/patches" % proj_id, 820),
        ("04b_遥感影像挂接", "/project/patch/%d/edit" % pid, 1100),
        ("05_微地质单元", "/unit/%d" % pid, 980),
        ("06_限制性判定", "/constraint/%d" % pid, 1100),
        ("07_标准知识库", "/standard/", 1100),
        ("07b_标准规则", "/standard/1/rules", 1000),
        ("08_省际口径比对", "/standard/compare", 1300),
        ("08b_结论对照", "/standard/check", 1000),
        ("09_AHP权重选择", "/ahp/", 780),
        ("09b_指标定义维护", "/ahp/indicators", 1500),
        ("09c_多专家矩阵", "/ahp/experts", 1200),
        ("10_判断矩阵录入", "/ahp/matrix?unit_type=碎石边坡&level=1", 900),
        ("10b_权重计算结果",
         "/ahp/matrix?unit_type=碎石边坡&level=1&calc=1", 1100),
        ("11_指标数据列表", "/indicator/", 900),
        ("11b_批量导入", "/indicator/import", 1100),
        ("12_指标数据录入", "/indicator/%s" % (unit_id or 1), 1400),
        ("13_适宜性评价", "/evaluate/", 760),
        ("14_评价结果", "/evaluate/result/%d" % rid, 900),
        ("15_得分明细与图表", "/report/%d" % pid, 1700),
        ("16_个人设置", "/profile", 1100),
        ("16b_个人设置_登录与安全性", "/profile?tab=security", 900),
        ("16c_账号管理", "/profile?tab=users", 900),
        ("16d_操作日志", "/profile?tab=logs", 900),
        ("16e_注册账号", "/register", 1000),
    ]


def http_status(url):
    """取页面的 HTTP 状态码。

    截图工具只看「文件有没有生成」，404 错误页同样会生成一张漂亮的截图，
    以前就是这么把「404 · 请求的页面不存在」当成「矿山图斑管理」收进材料的。
    所以每页截图前先问一次状态码，不是 200 就在输出里点名。
    """
    try:
        req = urllib.request.Request(
            urllib.parse.quote(url, safe=":/?&=%#"),
            headers={"User-Agent": "screenshot-status-check"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # 先重建演示数据，保证截图内容干净（避免测试残留数据出现在截图中）
    import seed_demo
    seed_demo.seed()
    print()

    app = create_app(ShotConfig)
    pid, proj_id, rid, unit_id = prepare_data(app)
    if pid is None:
        return
    print("图斑 ID=%s（项目 ID=%s，单元 ID=%s），评价结果 ID=%s"
          % (pid, proj_id, unit_id, rid))

    def serve():
        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    time.sleep(3)

    pages = build_page_list(pid, proj_id, rid, unit_id)
    print("开始截图，共 %d 页…" % len(pages))
    ok = 0
    bad = []
    for name, url, height in pages:
        out = os.path.join(OUT_DIR, "%s.png" % name)
        if os.path.exists(out):
            os.remove(out)
        status = http_status(HOST + url)
        cmd = [CHROME] + CHROME_ARGS + [
            "--window-size=%d,%d" % (WIN_W, height),
            "--screenshot=%s" % out,
            HOST + url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            print("  [超时] %s" % name)
            continue
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            ok += 1
            mark = ""
            if status != 200:
                bad.append((name, status))
                mark = "  <-- 状态码 %s，截到的是错误页" % status
            print("  [OK] %-18s %8.1f KB  %s%s"
                  % (name, os.path.getsize(out) / 1024, url, mark))
        else:
            print("  [失败] %-18s %s" % (name, url))

    print()
    if bad:
        print("  [警告] 以下页面不是 200，截图内容不可用：%s"
              % "、".join("%s(%s)" % (n, s) for n, s in bad))
    print("完成：%d / %d 张截图 -> %s"
          % (ok, len(pages), os.path.relpath(OUT_DIR, BASE)))


if __name__ == "__main__":
    main()
