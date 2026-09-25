# -*- coding: utf-8 -*-
"""项目与矿山档案 —— 项目、图斑、参照生态系统、遥感影像挂接。"""
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app)
from flask_login import login_required, current_user

from app.forms import EmptyForm
from app.models import db, Project, MinePatch, ReferenceEcosystem

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
    db.session.delete(p)
    db.session.commit()
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
    """删除矿山图斑，及其微地质单元与指标数据。"""
    from app.models import MicroUnit, IndicatorData, EvaluationResult, \
        ScoreDetail, ConstraintCheck, ReferenceEcosystem
    patch = db.get_or_404(MinePatch, patch_id)
    pid = patch.project_id
    unit_ids = [u.id for u in MicroUnit.query.filter_by(patch_id=patch.id).all()]
    if unit_ids:
        IndicatorData.query.filter(IndicatorData.unit_id.in_(unit_ids)).delete(
            synchronize_session=False)
    for r in EvaluationResult.query.filter_by(patch_id=patch.id).all():
        ScoreDetail.query.filter_by(result_id=r.id).delete(
            synchronize_session=False)
    EvaluationResult.query.filter_by(patch_id=patch.id).delete(
        synchronize_session=False)
    ConstraintCheck.query.filter_by(patch_id=patch.id).delete(
        synchronize_session=False)
    MicroUnit.query.filter_by(patch_id=patch.id).delete(synchronize_session=False)
    ReferenceEcosystem.query.filter_by(patch_id=patch.id).delete(
        synchronize_session=False)
    db.session.delete(patch)
    db.session.commit()
    flash("图斑「%s」及其数据已删除" % patch.name, "ok")
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

        patch = MinePatch(
            project_id=p.id,
            name=request.form.get("name", "").strip(),
            admin_region=fv("admin_region"),
            area_ha=fv("area_ha", float),
            mineral_type=fv("mineral_type"),
            mining_method=fv("mining_method"),
            stop_years=fv("stop_years", float),
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

        patch.name = request.form.get("name", "").strip()
        patch.admin_region = fv("admin_region")
        patch.area_ha = fv("area_ha", float)
        patch.mineral_type = fv("mineral_type")
        patch.mining_method = fv("mining_method")
        patch.stop_years = fv("stop_years", float)
        patch.responsible_entity_missing = bool(request.form.get("responsible_entity_missing"))
        # 参照生态系统
        ref = ReferenceEcosystem.query.filter_by(patch_id=patch.id).first()
        if ref is None:
            ref = ReferenceEcosystem(patch_id=patch.id)
            db.session.add(ref)
        ref.coverage_benchmark = fv("coverage_benchmark", float) or 75.0
        ref.shannon_benchmark = fv("shannon_benchmark", float) or 0.7
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
    patch.image_uploaded_at = datetime.utcnow()
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
