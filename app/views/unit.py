# -*- coding: utf-8 -*-
"""微地质单元管理 —— 岩质边坡 / 碎石边坡 / 平台的划分与面积占比。"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.forms import EmptyForm
from app.models import db, MinePatch, MicroUnit, IndicatorData
from app.utils.constants import UNIT_TYPES
from app.utils.parsing import FieldError, parse_float

bp = Blueprint("unit", __name__, url_prefix="/unit")


def recalc_ratio(patch_id):
    """按面积重算该图斑各单元面积占比。"""
    units = MicroUnit.query.filter_by(patch_id=patch_id).all()
    total = sum(u.area or 0.0 for u in units)
    if total > 0:
        for u in units:
            u.ratio = round((u.area or 0.0) / total, 6)
    return total


@bp.route("/")
@login_required
def list_patches():
    """微地质单元入口：列出各图斑及其单元划分情况。"""
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    rows = []
    for p in patches:
        units = MicroUnit.query.filter_by(patch_id=p.id).all()
        rows.append({
            "patch": p,
            "count": len(units),
            "ratio_sum": sum(u.ratio or 0.0 for u in units),
        })
    return render_template("unit/list.html", rows=rows)


@bp.route("/<int:patch_id>")
@login_required
def index(patch_id):
    patch = db.get_or_404(MinePatch, patch_id)
    units = MicroUnit.query.filter_by(patch_id=patch_id).all()
    total = sum(u.area or 0.0 for u in units)
    ratio_sum = sum(u.ratio or 0.0 for u in units)
    return render_template("unit/index.html", patch=patch, units=units,
                           total_area=total, ratio_sum=ratio_sum,
                           unit_types=UNIT_TYPES, form=EmptyForm())


@bp.route("/<int:patch_id>/add", methods=["POST"])
@login_required
def add(patch_id):
    patch = db.get_or_404(MinePatch, patch_id)
    form = EmptyForm()
    if form.validate_on_submit():
        unit_type = request.form.get("unit_type")
        if unit_type not in UNIT_TYPES:
            flash("微地质单元类型不正确", "error")
            return redirect(url_for("unit.index", patch_id=patch_id))
        # 评价流程规定将图斑分为平台、碎石边坡、岩质边坡三类，每类至多一个。
        # 允许重复会让面积占比与按单元类型组织的指标数据对不上号。
        if MicroUnit.query.filter_by(patch_id=patch.id,
                                     unit_type=unit_type).first():
            flash("该图斑已存在「%s」，同一类型只能划分一个" % unit_type, "error")
            return redirect(url_for("unit.index", patch_id=patch_id))

        area = request.form.get("area", "").strip()
        try:
            area_value = parse_float(area, "面积（公顷）", minimum=0)
        except FieldError as e:
            flash(str(e), "error")
            return redirect(url_for("unit.index", patch_id=patch_id))
        u = MicroUnit(patch_id=patch.id, unit_type=unit_type,
                      area=area_value,
                      description=request.form.get("description", "").strip() or None)
        db.session.add(u)
        db.session.flush()
        recalc_ratio(patch.id)
        db.session.commit()
        flash("微地质单元已添加", "ok")
    return redirect(url_for("unit.index", patch_id=patch_id))


@bp.route("/edit/<int:unit_id>", methods=["GET", "POST"])
@login_required
def edit(unit_id):
    """单个微地质单元的编辑页。"""
    u = db.get_or_404(MicroUnit, unit_id)
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        new_type = request.form.get("unit_type", u.unit_type)
        if new_type not in UNIT_TYPES:
            flash("微地质单元类型不正确", "error")
            return redirect(url_for("unit.edit", unit_id=u.id))
        # 改类型时同样不允许与本图斑已有的其他单元重复
        dup = MicroUnit.query.filter_by(patch_id=u.patch_id,
                                        unit_type=new_type).first()
        if dup is not None and dup.id != u.id:
            flash("该图斑已存在「%s」，同一类型只能划分一个" % new_type, "error")
            return redirect(url_for("unit.edit", unit_id=u.id))

        u.unit_type = new_type
        area = request.form.get("area", "").strip()
        try:
            u.area = parse_float(area, "面积（公顷）", minimum=0)
        except FieldError as e:
            flash(str(e), "error")
            return redirect(url_for("unit.edit", unit_id=u.id))
        u.description = request.form.get("description", "").strip() or None
        recalc_ratio(u.patch_id)
        db.session.commit()
        flash("微地质单元已保存", "ok")
        return redirect(url_for("unit.index", patch_id=u.patch_id))
    return render_template("unit/edit.html", unit=u, patch=u.patch,
                           unit_types=UNIT_TYPES, form=form)


@bp.route("/delete/<int:unit_id>", methods=["POST"])
@login_required
def delete(unit_id):
    u = db.get_or_404(MicroUnit, unit_id)
    pid = u.patch_id
    name = u.unit_type
    # 一并删除该单元的指标数据，避免残留
    IndicatorData.query.filter_by(unit_id=u.id).delete(synchronize_session=False)
    db.session.delete(u)
    db.session.flush()
    recalc_ratio(pid)
    db.session.commit()
    flash("微地质单元「%s」已删除" % name, "ok")
    return redirect(url_for("unit.index", patch_id=pid))
