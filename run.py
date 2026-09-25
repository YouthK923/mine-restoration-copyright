# -*- coding: utf-8 -*-
"""系统启动入口。

运行：
    python run.py
然后在浏览器打开 http://127.0.0.1:5000
"""
from app import create_app
from app.models import db

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # 控制台中文正常显示

app = create_app()

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
    print("  访问地址：http://127.0.0.1:5000")
    print("  演示账号：admin    密码：admin123")
    print("  停止运行：按 Ctrl+C")
    print("=" * 58)

    app.run(host="127.0.0.1", port=5000, debug=True)
