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

from app import create_app
from app.config import Config
from app.models import (db, MinePatch, MicroUnit, EvaluationResult,
                        ConstraintCheck)
from app.services import evaluation_service as ev
from app.views.evaluate import load_patch_input

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "软著材料", "截图")
PORT = 5099
HOST = "http://127.0.0.1:%d" % PORT

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_ARGS = [
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
    "--force-device-scale-factor=1",
]


class ShotConfig(Config):
    SCREENSHOT_MODE = True


def prepare_data(app):
    """确保案例与评价结果存在，供截图使用。"""
    with app.app_context():
        patch = MinePatch.query.first()
        if patch is None:
            print("  [警告] 数据库无图斑，请先运行 seed_demo.py")
            return None, None
        # 保证有一次限制性判定记录
        if ConstraintCheck.query.filter_by(patch_id=patch.id).first() is None:
            db.session.add(ConstraintCheck(
                patch_id=patch.id, policy_pass=True, location_pass=True,
                pollution_pass=True, geo_pass=True, farmland_pass=True,
                passed=True, reason="全部通过"))
            db.session.commit()
        # 保证有一次评价结果
        res = EvaluationResult.query.filter_by(patch_id=patch.id) \
            .order_by(EvaluationResult.id.desc()).first()
        if res is None:
            units = load_patch_input(patch.id)
            r = ev.score_mine(units)
            import json
            res = EvaluationResult(
                patch_id=patch.id, final_score=round(r["final_score"], 4),
                grade=r["grade"], measures=r["grade_info"]["measure"],
                unit_scores=json.dumps(
                    [{"unit_type": u["unit_type"], "ratio": u["ratio"],
                      "unit_score": round(u["unit_score"], 4)}
                     for u in r["unit_results"]], ensure_ascii=False))
            db.session.add(res)
            db.session.commit()
        return patch.id, res.id


def build_page_list(pid, rid):
    return [
        ("01_登录", "/login", 1000),
        ("02_系统首页", "/", 1000),
        ("03_项目与档案", "/project/", 900),
        ("04_矿山图斑", "/project/%d/patches" % pid, 900),
        ("05_微地质单元", "/unit/%d" % pid, 1200),
        ("06_限制性判定", "/constraint/%d" % pid, 1100),
        ("07_标准知识库", "/standard/", 1200),
        ("07b_标准规则", "/standard/1/rules", 1100),
        ("08_省际口径比对", "/standard/compare", 1400),
        ("09_AHP权重选择", "/ahp/", 900),
        ("10_判断矩阵录入", "/ahp/matrix?unit_type=碎石边坡&level=1", 1000),
        ("10b_权重计算结果",
         "/ahp/matrix?unit_type=碎石边坡&level=1&calc=1", 1300),
        ("11_指标数据列表", "/indicator/", 900),
        ("12_指标数据录入", "/indicator/2", 1300),
        ("13_适宜性评价", "/evaluate/", 800),
        ("14_评价结果", "/evaluate/result/%d" % rid, 1000),
        ("15_得分明细", "/report/%d" % pid, 1600),
        ("16_用户管理", "/users", 800),
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

    # 后台线程启动服务
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
            "--window-size=1280,%d" % height,
            "--screenshot=%s" % out,
            HOST + url,
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=60, encoding="utf-8", errors="replace")
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
