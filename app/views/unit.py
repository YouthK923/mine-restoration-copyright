# -*- coding: utf-8 -*-
"""M5 微地质单元管理 —— 岩质边坡 / 碎石边坡 / 平台的划分与面积占比。"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.forms import EmptyForm
from app.models import db, MinePatch, MicroUnit
from app.utils.constants import UNIT_TYPES

bp = Blueprint("unit", __name__, url_prefix="/unit")


def recalc_ratio(patch_id):
    """按面积重算该图斑各单元面积占比。"""
    units = MicroUnit.query.filter_by(patch_id=patch_id).all()
    total = sum(u.area or 0.0 for u in units)
    if total > 0:
        for u in units:
            u.ratio = round((u.area or 0.0) / total, 6)
    return total


@bp.route("/<int:patch_id>")
@login_required
def index(patch_id):
    patch = MinePatch.query.get_or_404(patch_id)
    units = MicroUnit.query.filter_by(patch_id=patch_id).all()
    total = sum(u.area or 0.0 for u in units)
    ratio_sum = sum(u.ratio or 0.0 for u in units)
    return render_template("unit/index.html", patch=patch, units=units,
                           total_area=total, ratio_sum=ratio_sum,
                           unit_types=UNIT_TYPES, form=EmptyForm())


@bp.route("/<int:patch_id>/add", methods=["POST"])
@login_required
def add(patch_id):
    patch = MinePatch.query.get_or_404(patch_id)
    form = EmptyForm()
    if form.validate_on_submit():
        unit_type = request.form.get("unit_type")
        area = request.form.get("area", "").strip()
        u = MicroUnit(patch_id=patch.id, unit_type=unit_type,
                      area=float(area) if area else None,
                      description=request.form.get("description", "").strip() or None)
        db.session.add(u)
        db.session.flush()
        recalc_ratio(patch.id)
        db.session.commit()
        flash("微地质单元已添加", "ok")
    return redirect(url_for("unit.index", patch_id=patch_id))


@bp.route("/edit/<int:unit_id>", methods=["POST"])
@login_required
def edit(unit_id):
    u = MicroUnit.query.get_or_404(unit_id)
    form = EmptyForm()
    if form.validate_on_submit():
        u.unit_type = request.form.get("unit_type", u.unit_type)
        area = request.form.get("area", "").strip()
        u.area = float(area) if area else None
        u.description = request.form.get("description", "").strip() or None
        recalc_ratio(u.patch_id)
        db.session.commit()
        flash("已保存", "ok")
    return redirect(url_for("unit.index", patch_id=u.patch_id))


@bp.route("/delete/<int:unit_id>", methods=["POST"])
@login_required
def delete(unit_id):
    u = MicroUnit.query.get_or_404(unit_id)
    pid = u.patch_id
    db.session.delete(u)
    db.session.flush()
    recalc_ratio(pid)
    db.session.commit()
    flash("已删除", "ok")
    return redirect(url_for("unit.index", patch_id=pid))
