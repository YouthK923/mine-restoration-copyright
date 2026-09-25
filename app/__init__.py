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

    # 侧边栏导航：按论文评价流程的顺序编排，分为「评价流程」与「系统管理」两组。
    # 不使用模块编号，避免出现与实际流程不一致的代号。
    @app.context_processor
    def inject_nav():
        path = request.path or "/"
        flow = [
            ("项目与矿山档案", "/project/", path.startswith("/project")),
            ("政策与标准知识库", "/standard/", path.startswith("/standard")),
            ("限制性指标判定", "/constraint/", path.startswith("/constraint")),
            ("微地质单元", "/unit/", path.startswith("/unit")),
            ("指标体系与权重", "/ahp/", path.startswith("/ahp")),
            ("指标数据采集", "/indicator/", path.startswith("/indicator")),
            ("适宜性定量评价", "/evaluate/", path.startswith("/evaluate")),
            ("报告与结果输出", "/report/", path.startswith("/report")),
        ]
        admin = [
            ("用户与操作日志", "/users", path.startswith(("/users", "/logs"))),
        ]
        groups = [
            {"title": "评价流程", "links": flow},
            {"title": "系统管理", "links": admin},
        ]

        # 层级引导用：项目是归档单位，图斑才是评价对象。
        # 下游各页面按图斑组织数据，因此需要提示「哪些项目下还没有图斑」。
        counts = {"project_count": 0, "patch_count": 0,
                  "projects_without_patch": []}
        if current_user.is_authenticated:
            from app.models import Project, MinePatch
            projects = Project.query.order_by(Project.id).all()
            counts["project_count"] = len(projects)
            counts["patch_count"] = MinePatch.query.count()
            counts["projects_without_patch"] = [
                p for p in projects if p.patches.count() == 0]
        counts["nav_groups"] = groups
        counts["home_active"] = path == "/"
        return counts

    # 操作审计：统一在响应阶段记录成功的写操作（操作日志）
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
