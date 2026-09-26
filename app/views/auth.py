# -*- coding: utf-8 -*-
"""用户与权限管理 —— 登录、注销、用户维护、操作日志。"""
from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, abort)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.forms import LoginForm, EmptyForm
from app.models import db, User, OperationLog
from app.utils.constants import ROLE_LABELS

bp = Blueprint("auth", __name__)


def require_admin():
    """非管理员直接 403，避免误操作基础数据。"""
    if current_user.role != "admin":
        abort(403)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        from app.services import dashboard as dash
        return render_template("auth/home.html", dash=dash.snapshot())
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            if not user.active:
                flash("该账号已停用，请联系管理员", "error")
                return render_template("auth/login.html", form=form,
                                       **_intro_data())
            login_user(user, remember=form.remember.data)
            # 用 toast 类别：渲染为页面正中的浮层，淡入停留后淡出。
            # 登录成功只是告知性反馈，不需要用户停下来阅读。
            flash("登录成功", "toast")
            return redirect(url_for("auth.index"))
        flash("用户名或密码错误", "error")
    return render_template("auth/login.html", form=form, **_intro_data())


def _intro_data():
    """登录页下方的系统介绍所用的静态内容。"""
    from app.services import dashboard as dash
    return {"modules": dash.MODULES, "steps": dash.STEPS}


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "ok")
    return redirect(url_for("auth.login"))


# ---------------------------- 用户维护 ----------------------------

@bp.route("/users")
@login_required
def users():
    all_users = User.query.order_by(User.id).all()
    return render_template("auth/users.html", users=all_users,
                           role_labels=ROLE_LABELS, form=EmptyForm())


@bp.route("/users/add", methods=["GET", "POST"])
@login_required
def add_user():
    require_admin()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "viewer")
        if not username or not password:
            flash("用户名和密码不能为空", "error")
            return redirect(url_for("auth.add_user"))
        if User.query.filter_by(username=username).first():
            flash("用户名已存在", "error")
            return redirect(url_for("auth.add_user"))
        db.session.add(User(username=username, role=role,
                            password_hash=generate_password_hash(password)))
        db.session.commit()
        flash("用户已添加", "ok")
        return redirect(url_for("auth.users"))
    return render_template("auth/add_user.html")


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    require_admin()
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        role = request.form.get("role", user.role)
        active = request.form.get("active") == "1"

        # 保护：不能把最后一个管理员降级或停用，否则无人能管理系统
        if user.role == "admin" and (role != "admin" or not active):
            others = User.query.filter(User.role == "admin",
                                       User.id != user.id,
                                       User.active.is_(True)).count()
            if others == 0:
                flash("系统至少需保留一名启用状态的管理员", "error")
                return redirect(url_for("auth.edit_user", user_id=user.id))

        user.role = role
        user.active = active
        new_password = request.form.get("password", "").strip()
        if new_password:
            user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("用户信息已保存", "ok")
        return redirect(url_for("auth.users"))
    return render_template("auth/edit_user.html", user=user,
                           role_labels=ROLE_LABELS, form=EmptyForm())


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    require_admin()
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("不能删除当前登录的账号", "error")
        return redirect(url_for("auth.users"))
    if user.role == "admin":
        others = User.query.filter(User.role == "admin",
                                   User.id != user.id,
                                   User.active.is_(True)).count()
        if others == 0:
            flash("系统至少需保留一名启用状态的管理员", "error")
            return redirect(url_for("auth.users"))
    db.session.delete(user)
    db.session.commit()
    flash("用户「%s」已删除" % user.username, "ok")
    return redirect(url_for("auth.users"))


# ---------------------------- 操作日志 ----------------------------

@bp.route("/logs")
@login_required
def logs():
    page = request.args.get("page", 1, type=int)
    per_page = 50
    q = OperationLog.query.order_by(OperationLog.id.desc())
    total = q.count()
    records = q.offset((page - 1) * per_page).limit(per_page).all()
    users_map = {u.id: u.username for u in User.query.all()}
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template("auth/logs.html", records=records, page=page,
                           pages=pages, total=total, users_map=users_map)
