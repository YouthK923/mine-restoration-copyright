# -*- coding: utf-8 -*-
"""Flask 应用工厂。"""
from datetime import date

from flask import Flask
from flask_login import LoginManager

from app.config import Config
from app.models import db, User
from app.utils.constants import ROLE_LABELS

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
        ahp, indicator, evaluate, report, search
    app.register_blueprint(auth.bp)
    app.register_blueprint(project.bp)
    app.register_blueprint(unit.bp)
    app.register_blueprint(standard.bp)
    app.register_blueprint(constraint.bp)
    app.register_blueprint(ahp.bp)
    app.register_blueprint(indicator.bp)
    app.register_blueprint(evaluate.bp)
    app.register_blueprint(report.bp)
    app.register_blueprint(search.bp)

    # 全局登录保护：除登录页与静态资源外，均需登录
    from flask import request, redirect, url_for, send_from_directory
    from flask_login import current_user, login_user

    PUBLIC_ENDPOINTS = {"auth.login", "static", "favicon"}

    # 浏览器默认会请求根路径下的 /favicon.ico。
    # 页面里虽已用 <link rel="icon"> 指向 static 目录，但出错页等场景仍会
    # 回退到这个路径，补一条路由免得日志里一直刷 404。
    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(app.static_folder, "favicon.ico",
                                   mimetype="image/vnd.microsoft.icon")

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
    # 每项带图标名（内联 SVG，见 templates/_macros.html 的 ICONS）
    # 与可选的待办角标（该步骤还没做完的图斑数）。
    FLOW_LINKS = [
        ("项目与矿山档案", "/project/", "folder"),
        ("政策与标准知识库", "/standard/", "book"),
        ("限制性指标判定", "/constraint/", "shield"),
        ("微地质单元", "/unit/", "layers"),
        ("指标体系与权重", "/ahp/", "sliders"),
        ("指标数据采集", "/indicator/", "database"),
        ("适宜性定量评价", "/evaluate/", "target"),
        ("报告与结果输出", "/report/", "file"),
    ]
    ADMIN_LINKS = [
        ("用户与操作日志", "/users", "users"),
    ]

    @app.context_processor
    def inject_nav():
        path = request.path or "/"

        def hit(prefix):
            """当前路径是否属于某个入口（/unit/ 也匹配 /unit/3）。"""
            return path.startswith(prefix.rstrip("/"))

        badges = {}
        if current_user.is_authenticated:
            from app.services import dashboard as dash
            badges = dash.nav_badges()

        def build(links):
            return [{"label": label, "href": href, "icon": icon,
                     "active": hit(href), "badge": badges.get(href, 0)}
                    for label, href, icon in links]

        groups = [
            {"title": "评价流程", "links": build(FLOW_LINKS)},
            {"title": "系统管理", "links": build(ADMIN_LINKS)},
        ]

        # 面包屑用的当前页名：按路径命中的入口取，未命中时给个通用名
        if path == "/":
            page_title = "工作台"
        elif path.startswith(("/users", "/logs")):
            page_title = "用户与操作日志"
        elif path.startswith("/search"):
            page_title = "搜索结果"
        else:
            page_title = "工作台"
            for label, href, _icon in FLOW_LINKS:
                if hit(href):
                    page_title = label
                    break

        # 层级引导用：项目是归档单位，图斑才是评价对象。
        # 下游各页面按图斑组织数据，因此需要提示「哪些项目下还没有图斑」。
        from app.models import Project, MinePatch
        projects = Project.query.order_by(Project.id).all()
        return {
            "nav_groups": groups,
            "home_active": path == "/",
            "page_title": page_title,
            "today": date.today().strftime("%Y-%m-%d"),
            "search_q": request.args.get("q", ""),
            "role_labels": ROLE_LABELS,
            "project_count": len(projects),
            "patch_count": MinePatch.query.count(),
            "projects_without_patch": [p for p in projects
                                       if p.patches.count() == 0],
        }

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
