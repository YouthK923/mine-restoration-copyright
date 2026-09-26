# -*- coding: utf-8 -*-
"""用户与权限管理 —— 登录、注销、用户维护、操作日志。"""
from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, abort, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.forms import LoginForm, EmptyForm, ProfileForm, PasswordForm
from app.models import db, User, OperationLog
from app.utils import uploads as up
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
    return {"modules": dash.MODULES}


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "ok")
    return redirect(url_for("auth.login"))


# ---------------------------- 个人设置 ----------------------------
# 与「用户管理」的区别：那里是管理员维护别人，这里是任何登录用户维护自己。

@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # 两个表单放在同一页，用字段前缀区分，避免 submit / csrf_token 重名
    info_form = ProfileForm(prefix="info", obj=current_user)
    pwd_form = PasswordForm(prefix="pwd")

    if request.method == "POST":
        action = request.form.get("action")
        if action == "info" and info_form.validate_on_submit():
            current_user.display_name = (info_form.display_name.data or "").strip() or None
            current_user.title = (info_form.title.data or "").strip() or None
            current_user.email = (info_form.email.data or "").strip() or None
            current_user.phone = (info_form.phone.data or "").strip() or None
            db.session.commit()
            flash("个人资料已保存", "ok")
            return redirect(url_for("auth.profile"))
        if action == "password" and pwd_form.validate_on_submit():
            if not check_password_hash(current_user.password_hash,
                                       pwd_form.old_password.data):
                pwd_form.old_password.errors.append("当前密码不正确")
            else:
                current_user.password_hash = generate_password_hash(
                    pwd_form.new_password.data)
                db.session.commit()
                flash("密码已修改", "ok")
                return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html", info_form=info_form,
                           pwd_form=pwd_form, avatar_form=EmptyForm(),
                           role_labels=ROLE_LABELS)


def _avatar_length_ok(file_storage):
    """按字节检查头像大小。超限时 werkzeug 读到内存里的内容也能量出来。"""
    limit = current_app.config.get("MAX_AVATAR_LENGTH", 4 * 1024 * 1024)
    stream = file_storage.stream
    pos = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(pos)
    return size <= limit, size


@bp.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("表单校验失败，请重试", "error")
        return redirect(url_for("auth.profile"))

    file = request.files.get("avatar")
    if file is None or not file.filename:
        flash("请选择头像图片", "error")
        return redirect(url_for("auth.profile"))

    ok, size = _avatar_length_ok(file)
    if not ok:
        flash("头像不能超过 %.0f MB（当前 %.1f MB）"
              % (current_app.config["MAX_AVATAR_LENGTH"] / 1024 / 1024,
                 size / 1024 / 1024), "error")
        return redirect(url_for("auth.profile"))

    rel, err = up.save_upload(file, "avatars",
                              current_app.config["ALLOWED_AVATAR_EXT"],
                              current_app.config["UPLOAD_FOLDER"])
    if err:
        flash(err, "error")
        return redirect(url_for("auth.profile"))

    # 换新头像时删掉旧文件，避免残留
    up.remove_upload(current_user.avatar, current_app.config["UPLOAD_FOLDER"])
    current_user.avatar = rel
    db.session.commit()
    flash("头像已更新", "ok")
    return redirect(url_for("auth.profile"))


@bp.route("/profile/avatar/delete", methods=["POST"])
@login_required
def delete_avatar():
    form = EmptyForm()
    if form.validate_on_submit():
        up.remove_upload(current_user.avatar, current_app.config["UPLOAD_FOLDER"])
        current_user.avatar = None
        db.session.commit()
        flash("头像已移除", "ok")
    return redirect(url_for("auth.profile"))


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
