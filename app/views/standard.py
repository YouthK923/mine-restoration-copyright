# -*- coding: utf-8 -*-
"""M3 政策与标准知识库 —— 标准/政策文件的结构化规则与省际口径比对。"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.forms import EmptyForm
from app.models import db, Standard, StandardRule

bp = Blueprint("standard", __name__, url_prefix="/standard")


@bp.route("/")
@login_required
def index():
    standards = Standard.query.order_by(Standard.category, Standard.province).all()
    local = [s for s in standards if s.category == "地方标准"]
    policy = [s for s in standards if s.category != "地方标准"]
    return render_template("standard/index.html", local=local, policy=policy)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        s = Standard(
            province=request.form.get("province", "").strip(),
            name=request.form.get("name", "").strip(),
            doc_number=request.form.get("doc_number", "").strip() or None,
            publish_date=request.form.get("publish_date", "").strip() or None,
            implement_date=request.form.get("implement_date", "").strip() or None,
            category=request.form.get("category", "地方标准"),
            summary=request.form.get("summary", "").strip() or None,
        )
        if not s.province or not s.name:
            flash("省份与名称不能为空", "error")
        else:
            db.session.add(s)
            db.session.commit()
            flash("标准已添加", "ok")
            return redirect(url_for("standard.index"))
    return render_template("standard/edit.html", form=form, standard=None)


@bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def edit(sid):
    s = Standard.query.get_or_404(sid)
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        s.province = request.form.get("province", "").strip()
        s.name = request.form.get("name", "").strip()
        s.doc_number = request.form.get("doc_number", "").strip() or None
        s.publish_date = request.form.get("publish_date", "").strip() or None
        s.implement_date = request.form.get("implement_date", "").strip() or None
        s.category = request.form.get("category", "地方标准")
        s.summary = request.form.get("summary", "").strip() or None
        db.session.commit()
        flash("已保存", "ok")
        return redirect(url_for("standard.rules", sid=s.id))
    return render_template("standard/edit.html", form=form, standard=s)


@bp.route("/<int:sid>/delete", methods=["POST"])
@login_required
def delete(sid):
    s = Standard.query.get_or_404(sid)
    StandardRule.query.filter_by(standard_id=sid).delete()
    db.session.delete(s)
    db.session.commit()
    flash("已删除", "ok")
    return redirect(url_for("standard.index"))


@bp.route("/<int:sid>/rules", methods=["GET", "POST"])
@login_required
def rules(sid):
    s = Standard.query.get_or_404(sid)
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        r = StandardRule(
            standard_id=s.id,
            item=request.form.get("item", "").strip(),
            operator=request.form.get("operator", ">="),
            threshold=request.form.get("threshold", "").strip() or None,
            condition_type=request.form.get("condition_type", "必要条件"),
            region=request.form.get("region", "").strip() or None,
            note=request.form.get("note", "").strip() or None,
        )
        if not r.item:
            flash("判定项不能为空", "error")
        else:
            db.session.add(r)
            db.session.commit()
            flash("规则已添加", "ok")
        return redirect(url_for("standard.rules", sid=s.id))
    rs = StandardRule.query.filter_by(standard_id=s.id).all()
    return render_template("standard/rules.html", form=form, standard=s, rules=rs)


@bp.route("/rule/<int:rid>/delete", methods=["POST"])
@login_required
def rule_delete(rid):
    r = StandardRule.query.get_or_404(rid)
    sid = r.standard_id
    db.session.delete(r)
    db.session.commit()
    flash("规则已删除", "ok")
    return redirect(url_for("standard.rules", sid=sid))


@bp.route("/compare")
@login_required
def compare():
    """省际口径比对：同一指标在不同省份的阈值横向对比。"""
    rules = StandardRule.query.join(Standard).all()
    groups = {}
    for r in rules:
        groups.setdefault(r.item, []).append(r)
    return render_template("standard/compare.html", groups=groups)
