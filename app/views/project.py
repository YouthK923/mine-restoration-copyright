# -*- coding: utf-8 -*-
"""项目与矿山档案 —— 项目、图斑、参照生态系统、遥感影像挂接。"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app)
from flask_login import login_required, current_user

from app.forms import EmptyForm
from app.models import db, Project, MinePatch, ReferenceEcosystem
from app.services import cleanup
from app.utils.parsing import FieldError, parse_float
from app.utils.timefmt import utcnow

bp = Blueprint("project", __name__, url_prefix="/project")


@bp.route("/")
@login_required
def index():
    projects = Project.query.order_by(Project.id.desc()).all()
    return render_template("project/index.html", projects=projects,
                           form=EmptyForm())


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        p = Project(
            name=request.form.get("name", "").strip(),
            code=request.form.get("code", "").strip() or None,
            description=request.form.get("description", "").strip() or None,
            created_by=current_user.id,
        )
        if not p.name:
            flash("项目名称不能为空", "error")
        else:
            db.session.add(p)
            db.session.commit()
            flash("项目已创建", "ok")
            return redirect(url_for("project.index"))
    return render_template("project/edit.html", form=form, project=None)


@bp.route("/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def edit(pid):
    p = db.get_or_404(Project, pid)
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        p.name = request.form.get("name", "").strip()
        p.code = request.form.get("code", "").strip() or None
        p.description = request.form.get("description", "").strip() or None
        p.status = request.form.get("status", "进行中")
        db.session.commit()
        flash("项目已保存", "ok")
        return redirect(url_for("project.index"))
    return render_template("project/edit.html", form=form, project=p)


@bp.route("/<int:pid>/delete", methods=["POST"])
@login_required
def delete(pid):
    p = db.get_or_404(Project, pid)
    # 项目下的图斑由 ORM 级联删除，但图斑下面的指标数据、限制性判定、
    # 评价结果、得分明细、参照生态系统不会跟着走，必须先逐个图斑清理，
    # 否则每删一个项目都在库里留下一批孤儿数据（见 app/services/cleanup.py）。
    cleanup.delete_project(p)
    flash("项目已删除", "ok")
    return redirect(url_for("project.index"))


# ---------------------------- 矿山图斑 ----------------------------

@bp.route("/<int:pid>/patches")
@login_required
def patches(pid):
    p = db.get_or_404(Project, pid)
    return render_template("project/patches.html", project=p,
                           form=EmptyForm())


@bp.route("/patch/<int:patch_id>/delete", methods=["POST"])
@login_required
def patch_delete(patch_id):
    """删除矿山图斑，及其微地质单元、指标数据与评价记录。"""
    patch = db.get_or_404(MinePatch, patch_id)
    pid = patch.project_id
    # 清理逻辑统一放在 app/services/cleanup.py：项目删除走的是同一个函数，
    # 免得两条删除路径各写一份、漏掉某张子表（曾经就漏过）。
    deleted, _counts = cleanup.delete_patch(patch.id)
    flash("图斑「%s」及其数据已删除" % (deleted.name if deleted else patch.name),
          "ok")
    return redirect(url_for("project.patches", pid=pid))


@bp.route("/<int:pid>/patch/add", methods=["GET", "POST"])
@login_required
def patch_add(pid):
    p = db.get_or_404(Project, pid)
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        def fv(name, cast=str):
            v = request.form.get(name, "").strip()
            return cast(v) if v != "" else None

        try:
            area_ha = parse_float(request.form.get("area_ha"), "图斑面积（公顷）",
                                  minimum=0)
            stop_years = parse_float(request.form.get("stop_years"), "停产年限",
                                     minimum=0)
        except FieldError as e:
            flash(str(e), "error")
            return redirect(url_for("project.patch_add", pid=p.id))

        patch = MinePatch(
            project_id=p.id,
            name=request.form.get("name", "").strip(),
            admin_region=fv("admin_region"),
            area_ha=area_ha,
            mineral_type=fv("mineral_type"),
            mining_method=fv("mining_method"),
            stop_years=stop_years,
            responsible_entity_missing=bool(request.form.get("responsible_entity_missing")),
        )
        if not patch.name:
            flash("图斑名称不能为空", "error")
        else:
            db.session.add(patch)
            db.session.flush()
            # 参照生态系统默认取论文值
            db.session.add(ReferenceEcosystem(
                patch_id=patch.id, coverage_benchmark=75.0, shannon_benchmark=0.7))
            db.session.commit()
            flash("图斑已创建", "ok")
            return redirect(url_for("project.patches", pid=p.id))
    return render_template("project/patch_edit.html", form=form, project=p, patch=None)


@bp.route("/patch/<int:patch_id>/edit", methods=["GET", "POST"])
@login_required
def patch_edit(patch_id):
    patch = db.get_or_404(MinePatch, patch_id)
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        def fv(name, cast=str):
            v = request.form.get(name, "").strip()
            return cast(v) if v != "" else None

        # 数值字段统一走 parse_float：填了非数字给中文提示，而不是 500
        try:
            area_ha = parse_float(request.form.get("area_ha"), "图斑面积（公顷）",
                                  minimum=0)
            stop_years = parse_float(request.form.get("stop_years"), "停产年限",
                                     minimum=0)
            cov = parse_float(request.form.get("coverage_benchmark"),
                              "植被覆盖度基准（%）", minimum=0, maximum=100)
            sha = parse_float(request.form.get("shannon_benchmark"),
                              "Shannon 基准", minimum=0)
        except FieldError as e:
            flash(str(e), "error")
            return redirect(url_for("project.patch_edit", patch_id=patch.id))

        patch.name = request.form.get("name", "").strip()
        patch.admin_region = fv("admin_region")
        patch.area_ha = area_ha
        patch.mineral_type = fv("mineral_type")
        patch.mining_method = fv("mining_method")
        patch.stop_years = stop_years
        patch.responsible_entity_missing = bool(request.form.get("responsible_entity_missing"))
        # 参照生态系统
        ref = ReferenceEcosystem.query.filter_by(patch_id=patch.id).first()
        if ref is None:
            ref = ReferenceEcosystem(patch_id=patch.id)
            db.session.add(ref)
        # 基准值：用户填 0 是合法输入（不能写成 `or 75.0`，那样 0 会被悄悄换成默认值）
        ref.coverage_benchmark = 75.0 if cov is None else cov
        ref.shannon_benchmark = 0.7 if sha is None else sha
        ref.dominant_species = fv("dominant_species")
        patch.image_note = fv("image_note")
        db.session.commit()
        flash("图斑已保存", "ok")
        return redirect(url_for("project.patches", pid=patch.project_id))
    return render_template("project/patch_edit.html", form=form,
                           project=patch.project, patch=patch,
                           reference=ReferenceEcosystem.query.filter_by(
                               patch_id=patch.id).first())


# ---------------------------- 遥感影像挂接 ----------------------------

@bp.route("/patch/<int:patch_id>/image", methods=["POST"])
@login_required
def upload_image(patch_id):
    """上传遥感底图 / 无人机正射影像并挂接到图斑。"""
    from app.utils import uploads as up
    patch = db.get_or_404(MinePatch, patch_id)
    form = EmptyForm()
    if not form.validate_on_submit():
        flash("表单校验失败，请重试", "error")
        return redirect(url_for("project.patch_edit", patch_id=patch.id))

    rel, err = up.save_upload(request.files.get("image"), "patches",
                              current_app.config["ALLOWED_IMAGE_EXT"],
                              current_app.config["UPLOAD_FOLDER"])
    if err:
        flash(err, "error")
        return redirect(url_for("project.patch_edit", patch_id=patch.id))

    # 替换旧影像时清理原文件，避免残留
    if patch.image_path:
        up.remove_upload(patch.image_path, current_app.config["UPLOAD_FOLDER"])
    patch.image_path = rel
    patch.image_uploaded_at = utcnow()
    note = request.form.get("image_note", "").strip()
    if note:
        patch.image_note = note
    db.session.commit()
    flash("遥感影像已挂接", "ok")
    return redirect(url_for("project.patch_edit", patch_id=patch.id))


@bp.route("/patch/<int:patch_id>/image/delete", methods=["POST"])
@login_required
def delete_image(patch_id):
    from app.utils import uploads as up
    patch = db.get_or_404(MinePatch, patch_id)
    form = EmptyForm()
    if form.validate_on_submit():
        up.remove_upload(patch.image_path, current_app.config["UPLOAD_FOLDER"])
        patch.image_path = None
        patch.image_uploaded_at = None
        db.session.commit()
        flash("遥感影像已移除", "ok")
    return redirect(url_for("project.patch_edit", patch_id=patch.id))
