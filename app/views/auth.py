# -*- coding: utf-8 -*-
"""M1 用户与权限管理 —— 登录、注销、权限控制。"""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.forms import LoginForm
from app.models import db, User

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("auth/home.html")
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            flash("登录成功", "ok")
            return redirect(url_for("auth.index"))
        flash("用户名或密码错误", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/users")
@login_required
def users():
    """用户列表（管理员可管理）。"""
    all_users = User.query.order_by(User.id).all()
    return render_template("auth/users.html", users=all_users)


@bp.route("/users/add", methods=["GET", "POST"])
@login_required
def add_user():
    if current_user.role != "admin":
        flash("仅管理员可新增用户", "error")
        return redirect(url_for("auth.users"))
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
        user = User(username=username,
                    password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        db.session.commit()
        flash("用户已添加", "ok")
        return redirect(url_for("auth.users"))
    return render_template("auth/add_user.html")
