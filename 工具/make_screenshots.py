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
    """确保案例与评价结果存在，供截图使用。"""
    with app.app_context():
        import seed_demo
        patch = seed_demo.demo_patch()      # 固定取演示案例，不取库中任意图斑
        if patch is None:
            print("  [警告] 数据库无图斑，请先运行 seed_demo.py")
            return None, None
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
        return patch.id, res.id


def build_page_list(pid, rid):
    return [
        ("01_登录", "/login", 900),
        # 带 #login 访问会直接展开登录框（见 auth/login.html 的脚本）
        ("01b_登录框", "/login#login", 900),
        ("02_系统首页", "/", 900),
        ("03_项目与档案", "/project/", 820),
        ("04_矿山图斑", "/project/%d/patches" % pid, 820),
        ("04b_遥感影像挂接", "/project/patch/%d/edit" % pid, 1100),
        ("05_微地质单元", "/unit/%d" % pid, 980),
        ("06_限制性判定", "/constraint/%d" % pid, 1100),
        ("07_标准知识库", "/standard/", 1100),
        ("07b_标准规则", "/standard/1/rules", 1000),
        ("08_省际口径比对", "/standard/compare", 1300),
        ("09_AHP权重选择", "/ahp/", 780),
        ("09b_指标定义维护", "/ahp/indicators", 1500),
        ("09c_多专家矩阵", "/ahp/experts", 1200),
        ("10_判断矩阵录入", "/ahp/matrix?unit_type=碎石边坡&level=1", 900),
        ("10b_权重计算结果",
         "/ahp/matrix?unit_type=碎石边坡&level=1&calc=1", 1100),
        ("11_指标数据列表", "/indicator/", 900),
        ("11b_批量导入", "/indicator/import", 1100),
        ("12_指标数据录入", "/indicator/2", 1400),
        ("13_适宜性评价", "/evaluate/", 760),
        ("14_评价结果", "/evaluate/result/%d" % rid, 900),
        ("15_得分明细与图表", "/report/%d" % pid, 1700),
        ("16_用户管理", "/users", 900),
        ("16b_操作日志", "/logs", 900),
        ("16c_个人设置", "/profile", 1100),
    ]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # 先重建演示数据，保证截图内容干净（避免测试残留数据出现在截图中）
    import seed_demo
    seed_demo.seed()
    print()

    app = create_app(ShotConfig)
    pid, rid = prepare_data(app)
    if pid is None:
        return
    print("图斑 ID=%s，评价结果 ID=%s" % (pid, rid))

    def serve():
        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    time.sleep(3)

    pages = build_page_list(pid, rid)
    print("开始截图，共 %d 页…" % len(pages))
    ok = 0
    for name, url, height in pages:
        out = os.path.join(OUT_DIR, "%s.png" % name)
        if os.path.exists(out):
            os.remove(out)
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
            print("  [OK] %-18s %8.1f KB  %s"
                  % (name, os.path.getsize(out) / 1024, url))
        else:
            print("  [失败] %-18s %s" % (name, url))

    print()
    print("完成：%d / %d 张截图 -> %s"
          % (ok, len(pages), os.path.relpath(OUT_DIR, BASE)))


if __name__ == "__main__":
    main()
