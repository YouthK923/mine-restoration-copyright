# -*- coding: utf-8 -*-
"""系统启动入口。

运行：
    python run.py                启动并自动打开浏览器
    python run.py --no-browser   只启动服务，不打开浏览器
    python run.py --dev          开发模式（开启代码热重载与调试器）
    python run.py --port 5001    指定端口

默认以 127.0.0.1:5000 启动，就绪后自动打开浏览器。
"""
import os
import sys
import threading
import time
import webbrowser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # 控制台中文正常显示

from app import create_app
from app.models import db

PORT = 5000
for i, a in enumerate(sys.argv):
    if a == "--port" and i + 1 < len(sys.argv):
        PORT = int(sys.argv[i + 1])

URL = "http://127.0.0.1:%d" % PORT
NO_BROWSER = "--no-browser" in sys.argv
DEV = "--dev" in sys.argv

app = create_app()


def open_browser_later(delay=1.2):
    """等服务工作起来再打开浏览器，避免打开时页面还没就绪。

    放在后台线程里，不用 sleep 阻塞服务启动；线程设为守护线程，
    用户 Ctrl+C 停止服务时不会残留。
    """
    def run():
        time.sleep(delay)
        try:
            webbrowser.open(URL)
        except Exception:
            pass        # 打开失败不影响服务本身
    t = threading.Thread(target=run, daemon=True)
    t.start()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()   # 首次运行时自动建表
        from app.utils.schema import ensure_schema
        added = ensure_schema(db)   # 旧库补齐新增字段
        if added:
            print("已补充字段：%s" % "、".join(added))

    print("=" * 58)
    print("  历史遗留废弃矿山自然恢复适宜性评价系统 V1.0")
    print("=" * 58)
    print("  访问地址：%s" % URL)
    print("  演示账号：admin    密码：admin123")
    print("  停止运行：按 Ctrl+C，或直接关闭本窗口")
    print("=" * 58)
    if not NO_BROWSER and not DEV:
        print("  正在打开浏览器……")
    print()

    # 开发模式才启用热重载（重载会二次启动进程，故此时不自动开浏览器）
    if not NO_BROWSER and not DEV:
        open_browser_later()

    app.run(host="127.0.0.1", port=PORT, debug=DEV, use_reloader=DEV)
