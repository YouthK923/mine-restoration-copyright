# -*- coding: utf-8 -*-
"""系统启动入口。

运行：
    python run.py
然后浏览器打开 http://127.0.0.1:5000
"""
from app import create_app
from app.models import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()   # 首次运行时自动建表
    app.run(host="127.0.0.1", port=5000, debug=True)
