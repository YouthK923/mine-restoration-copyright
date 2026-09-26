# -*- coding: utf-8 -*-
"""账号与权限 —— 登录、注册、个人资料、用户维护、操作日志。

页面组织：
  /login      登录页（含「点我注册」入口）
  /register   自助注册（默认「操作员」）
  /profile    个人设置，分类切换：info / security / users / logs
              后两个分类仅管理员可见，由本模块统一管控。
"""
from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, abort, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.forms import (LoginForm, EmptyForm, ProfileForm, PasswordForm,
                       RegisterForm, email_ok)
from app.models import db, User, OperationLog
from app.utils import uploads as up
from app.utils.constants import ROLE_LABELS, DEFAULT_ROLE, GENDERS

bp = Blueprint("auth", __name__)

# 「个人设置」的四个分类；后两个是管理员专属
PROFILE_TABS = ("info", "security", "users", "logs")
ADMIN_TABS = ("users", "logs")


def require_admin():
    """非管理员直接 403，避免误操作基础数据。"""
    if current_user.role != "admin":
        abort(403)


def _intro_data():
    """登录页下方的系统介绍所用的静态内容。"""
    from app.services import dashboard as dash
    return {"modules": dash.MODULES}


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
    # 登录失败的原因直接交给模板，渲染在登录框内部。
    # 不用 flash：flash 的提示条在正文顶部，会被登录框的渐变遮罩盖住，用户看不到。
    error = None
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            if not user.active:
                error = "该账号已停用，请联系管理员"
            else:
                login_user(user, remember=form.remember.data)
                # 用 toast 类别：渲染为页面正中的浮层，淡入停留后淡出。
                # 登录成功只是告知性反馈，不需要用户停下来阅读。
                flash("登录成功", "toast")
                return redirect(url_for("auth.index"))
        else:
            error = "账户名称或密码错误"
    return render_template("auth/login.html", form=form, error=error,
                           **_intro_data())


@bp.route("/register", methods=["GET", "POST"])
def register():
    """自助注册。新账号一律为「操作员」，权限只能由管理员事后调整。"""
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            form.username.errors.append("该账户名称已被使用")
        else:
            user = User(username=username,
                        role=DEFAULT_ROLE,
                        password_hash=generate_password_hash(form.password.data),
                        display_name=(form.display_name.data or "").strip() or None,
                        gender=(form.gender.data or "").strip() or None,
                        email=(form.email.data or "").strip() or None,
                        phone=(form.phone.data or "").strip() or None)
            rel, err = _save_avatar(request.files.get("avatar"))
            if err:
                flash(err, "error")
            else:
                user.avatar = rel
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("注册成功，欢迎使用", "toast")
                return redirect(url_for("auth.index"))
    return render_template("auth/register.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "ok")
    return redirect(url_for("auth.login"))


# ---------------------------- 个人设置 ----------------------------
# 任何登录用户在这里维护自己；管理员额外能管理账号与查看日志。
# 「用户与操作日志」不再是独立菜单，而是本页的管理员分类。

@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    is_admin = current_user.role == "admin"
    tab = request.values.get("tab") or "info"
    if tab not in PROFILE_TABS or (tab in ADMIN_TABS and not is_admin):
        tab = "info"

    # 表单放在同一页，用字段前缀区分，避免 submit / csrf_token 重名
    info_form = ProfileForm(prefix="info", obj=current_user)
    pwd_form = PasswordForm(prefix="pwd")

    if request.method == "POST":
        action = request.form.get("action")
        # 校验失败要重新渲染本页，此时必须回到提交表单所在的那个分类，
        # 否则错误提示会出现在另一个分类里，用户根本看不到。
        if action == "password":
            tab = "security"
        elif action == "info":
            tab = "info"

        if action == "info" and info_form.validate_on_submit():
            current_user.display_name = (info_form.display_name.data or "").strip() or None
            current_user.gender = (info_form.gender.data or "").strip() or None
            current_user.email = (info_form.email.data or "").strip() or None
            current_user.phone = (info_form.phone.data or "").strip() or None
            db.session.commit()
            flash("个人资料已保存", "ok")
            return redirect(url_for("auth.profile", tab="info"))
        if action == "password" and pwd_form.validate_on_submit():
            if not check_password_hash(current_user.password_hash,
                                       pwd_form.old_password.data):
                pwd_form.old_password.errors.append("当前密码不正确")
            else:
                current_user.password_hash = generate_password_hash(
                    pwd_form.new_password.data)
                db.session.commit()
                flash("密码已修改", "ok")
                return redirect(url_for("auth.profile", tab="security"))

    ctx = dict(info_form=info_form, pwd_form=pwd_form, avatar_form=EmptyForm(),
               tab=tab, role_labels=ROLE_LABELS, genders=GENDERS)
    if tab == "users":
        ctx.update(_users_context())
    elif tab == "logs":
        ctx.update(_logs_context())
    return render_template("auth/profile.html", **ctx)


def _users_context():
    """管理员分类「账号」所需的数据。"""
    return {"users": User.query.order_by(User.id).all(),
            "form": EmptyForm()}


def _logs_context():
    """管理员分类「操作日志」所需的数据。"""
    page = request.args.get("page", 1, type=int)
    per_page = 50
    q = OperationLog.query.order_by(OperationLog.id.desc())
    total = q.count()
    records = q.offset((page - 1) * per_page).limit(per_page).all()
    users_map = {u.id: u.username for u in User.query.all()}
    pages = max(1, (total + per_page - 1) // per_page)
    return {"records": records, "page": page, "pages": pages,
            "total": total, "users_map": users_map}


# ---------------------------- 头像 ----------------------------

def _avatar_length_ok(file_storage):
    """按字节检查头像大小。超限时 werkzeug 读到内存里的内容也能量出来。"""
    limit = current_app.config.get("MAX_AVATAR_LENGTH", 4 * 1024 * 1024)
    stream = file_storage.stream
    pos = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(pos)
    return size <= limit, size


def _save_avatar(file):
    """保存头像文件，返回 (相对路径, 错误信息)。没有文件时返回 (None, None)。"""
    if file is None or not file.filename:
        return None, None
    ok, size = _avatar_length_ok(file)
    if not ok:
        return None, ("头像不能超过 %.0f MB（当前 %.1f MB）"
                      % (current_app.config["MAX_AVATAR_LENGTH"] / 1024 / 1024,
                         size / 1024 / 1024))
    return up.save_upload(file, "avatars",
                          current_app.config["ALLOWED_AVATAR_EXT"],
                          current_app.config["UPLOAD_FOLDER"])


@bp.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    form = EmptyForm()
    back = url_for("auth.profile", tab=request.form.get("tab") or "info")
    if not form.validate_on_submit():
        flash("表单校验失败，请重试", "error")
        return redirect(back)

    rel, err = _save_avatar(request.files.get("avatar"))
    if err:
        flash(err, "error")
        return redirect(back)
    if rel is None:
        flash("请选择头像图片", "error")
        return redirect(back)

    # 换新头像时删掉旧文件，避免残留
    up.remove_upload(current_user.avatar, current_app.config["UPLOAD_FOLDER"])
    current_user.avatar = rel
    db.session.commit()
    flash("头像已更新", "ok")
    return redirect(back)


@bp.route("/profile/avatar/delete", methods=["POST"])
@login_required
def delete_avatar():
    form = EmptyForm()
    back = url_for("auth.profile", tab=request.form.get("tab") or "info")
    if form.validate_on_submit():
        up.remove_upload(current_user.avatar, current_app.config["UPLOAD_FOLDER"])
        current_user.avatar = None
        db.session.commit()
        flash("头像已移除", "ok")
    return redirect(back)


# ---------------------------- 账号维护（仅管理员） ----------------------------

@bp.route("/users")
@login_required
def users():
    """旧地址保留，统一并入「个人设置 · 账号」。"""
    return redirect(url_for("auth.profile", tab="users"))


@bp.route("/users/add", methods=["GET", "POST"])
@login_required
def add_user():
    require_admin()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", DEFAULT_ROLE)
        if role not in ROLE_LABELS:
            role = DEFAULT_ROLE
        if not username or not password:
            flash("账户名称和密码不能为空", "error")
            return redirect(url_for("auth.add_user"))
        if User.query.filter_by(username=username).first():
            flash("账户名称已存在", "error")
            return redirect(url_for("auth.add_user"))
        db.session.add(User(
            username=username, role=role,
            password_hash=generate_password_hash(password),
            display_name=request.form.get("display_name", "").strip() or None,
            gender=request.form.get("gender", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None))
        db.session.commit()
        flash("账号已添加", "ok")
        return redirect(url_for("auth.profile", tab="users"))
    return render_template("auth/add_user.html", role_labels=ROLE_LABELS,
                           genders=GENDERS, default_role=DEFAULT_ROLE,
                           form=EmptyForm())


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    require_admin()
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        role = request.form.get("role", user.role)
        if role not in ROLE_LABELS:
            role = user.role
        active = request.form.get("active") == "1"

        # 保护：不能把最后一个管理员降级或停用，否则无人能管理系统
        if user.role == "admin" and (role != "admin" or not active):
            others = User.query.filter(User.role == "admin",
                                       User.id != user.id,
                                       User.active.is_(True)).count()
            if others == 0:
                flash("系统至少需保留一名启用状态的管理员", "error")
                return redirect(url_for("auth.edit_user", user_id=user.id))

        # 个人资料字段（用户自己也能在「个人设置」里改，管理员在此代改）
        email = request.form.get("email", "").strip()
        if not email_ok(email):
            flash("邮箱格式不正确", "error")
            return redirect(url_for("auth.edit_user", user_id=user.id))

        user.role = role
        user.active = active
        user.display_name = request.form.get("display_name", "").strip() or None
        user.gender = request.form.get("gender", "").strip() or None
        user.email = email or None
        user.phone = request.form.get("phone", "").strip() or None

        new_password = request.form.get("password", "").strip()
        if new_password:
            user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("账号信息已保存", "ok")
        return redirect(url_for("auth.profile", tab="users"))
    return render_template("auth/edit_user.html", user=user,
                           role_labels=ROLE_LABELS, genders=GENDERS,
                           form=EmptyForm())


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    require_admin()
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("不能删除当前登录的账号", "error")
        return redirect(url_for("auth.profile", tab="users"))
    if user.role == "admin":
        others = User.query.filter(User.role == "admin",
                                   User.id != user.id,
                                   User.active.is_(True)).count()
        if others == 0:
            flash("系统至少需保留一名启用状态的管理员", "error")
            return redirect(url_for("auth.profile", tab="users"))
    db.session.delete(user)
    db.session.commit()
    flash("账号「%s」已删除" % user.username, "ok")
    return redirect(url_for("auth.profile", tab="users"))


# ---------------------------- 操作日志（仅管理员） ----------------------------

@bp.route("/logs")
@login_required
def logs():
    """旧地址保留，统一并入「个人设置 · 操作日志」。"""
    return redirect(url_for("auth.profile", tab="logs"))
