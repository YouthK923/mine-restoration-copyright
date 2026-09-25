# -*- coding: utf-8 -*-
"""M4 限制性指标判定 —— 一票否决判定。

按论文表 2 与 4.1 节流程，共 5 项：政策、区位约束、土壤污染、地质灾害、耕地属性。
任一项不通过即判定为"人工辅助或生态重建"，不再进入定量评价。
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.forms import EmptyForm
from app.models import db, MinePatch, ConstraintCheck
from app.utils.constants import CONSTRAINT_ITEMS

bp = Blueprint("constraint", __name__, url_prefix="/constraint")

# 字段名 -> 中文名
FIELDS = [
    ("policy_pass", "政策约束"),
    ("location_pass", "区位约束"),
    ("pollution_pass", "土壤污染"),
    ("geo_pass", "地质灾害"),
    ("farmland_pass", "耕地属性"),
]


@bp.route("/")
@login_required
def index():
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    latest = {}
    for p in patches:
        latest[p.id] = ConstraintCheck.query.filter_by(patch_id=p.id) \
            .order_by(ConstraintCheck.id.desc()).first()
    return render_template("constraint/index.html", patches=patches, latest=latest)


@bp.route("/<int:patch_id>", methods=["GET", "POST"])
@login_required
def check(patch_id):
    patch = MinePatch.query.get_or_404(patch_id)
    form = EmptyForm()
    record = ConstraintCheck.query.filter_by(patch_id=patch_id) \
        .order_by(ConstraintCheck.id.desc()).first()

    if request.method == "POST" and form.validate_on_submit():
        if record is None:
            record = ConstraintCheck(patch_id=patch.id)
            db.session.add(record)
        for field, _ in FIELDS:
            setattr(record, field, request.form.get(field) == "1")
        record.passed = all(getattr(record, f) for f, _ in FIELDS)
        failed = [name for f, name in FIELDS if not getattr(record, f)]
        record.reason = ("全部通过" if record.passed
                         else "未通过：" + "、".join(failed))
        db.session.commit()
        flash("判定结果已保存", "ok")
        return redirect(url_for("constraint.check", patch_id=patch.id))

    # 预处理各条件的当前取值，供模板直接使用（Jinja 无 getattr）
    field_states = [(f, name, None if record is None else getattr(record, f))
                    for f, name in FIELDS]
    return render_template("constraint/check.html", patch=patch, form=form,
                           fields=FIELDS, field_states=field_states,
                           record=record)
