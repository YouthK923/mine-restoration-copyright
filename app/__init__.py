# -*- coding: utf-8 -*-
"""Flask 应用工厂。"""
from flask import Flask

from app.config import Config
from app.models import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # 注册视图（各模块路由，后续逐步接入）
    from app.views import auth, ahp, indicator, evaluate, report
    app.register_blueprint(auth.bp)
    app.register_blueprint(ahp.bp)
    app.register_blueprint(indicator.bp)
    app.register_blueprint(evaluate.bp)
    app.register_blueprint(report.bp)

    return app
