# -*- coding: utf-8 -*-
"""Flask 应用工厂。"""
from flask import Flask
from flask_login import LoginManager

from app.config import Config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "请先登录"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    # 注册视图（各模块路由）
    from app.views import auth, project, unit, standard, constraint, \
        ahp, indicator, evaluate, report
    app.register_blueprint(auth.bp)
    app.register_blueprint(project.bp)
    app.register_blueprint(unit.bp)
    app.register_blueprint(standard.bp)
    app.register_blueprint(constraint.bp)
    app.register_blueprint(ahp.bp)
    app.register_blueprint(indicator.bp)
    app.register_blueprint(evaluate.bp)
    app.register_blueprint(report.bp)

    # 全局登录保护：除登录页与静态资源外，均需登录
    from flask import request, redirect, url_for
    from flask_login import current_user, login_user

    PUBLIC_ENDPOINTS = {"auth.login", "static"}

    @app.before_request
    def require_login():
        # 截图模式（仅用于生成说明书配图）：自动以管理员身份登录
        if app.config.get("SCREENSHOT_MODE"):
            if (request.endpoint not in ("auth.login", "static")
                    and not current_user.is_authenticated):
                admin = User.query.filter_by(role="admin").first()
                if admin:
                    login_user(admin)
            return None

        if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
            return None
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        return None

    # 侧边栏导航项：集中定义，模板只负责渲染；active 用于高亮当前页
    @app.context_processor
    def inject_nav():
        path = request.path or "/"
        items = [
            ("首页", "/", path == "/"),
            ("项目与档案", "/project/", path.startswith("/project")),
            ("限制性判定", "/constraint/", path.startswith("/constraint")),
            ("标准知识库", "/standard/", path.startswith("/standard")),
            ("AHP 权重", "/ahp/", path.startswith("/ahp")),
            ("指标数据", "/indicator/", path.startswith("/indicator")),
            ("适宜性评价", "/evaluate/", path.startswith("/evaluate")),
            ("报告输出", "/report/", path.startswith("/report")),
            ("用户与日志", "/users", path.startswith(("/users", "/logs"))),
        ]
        return {"nav_items": items}

    # 操作审计：统一在响应阶段记录成功的写操作（M1 操作日志）
    from app.services import audit

    @app.after_request
    def audit_writes(response):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            audit.record(request.endpoint, response.status_code)
        return response

    # 错误页：给出可读提示，而不是默认的英文错误页
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               message="没有权限执行该操作"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404,
                               message="请求的页面不存在"), 404

    return app
