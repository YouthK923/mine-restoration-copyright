# -*- coding: utf-8 -*-
"""M9 报告与结果输出 —— 路由与页面逻辑。

提供完整得分明细页（每一层指标的权重、标准化值、加权贡献），
并支持导出 Word 评价报告。
"""
from flask import Blueprint, render_template, send_file, flash, redirect, url_for

from app.models import MinePatch
from app.services import evaluation_service as ev
from app.services import report_service as rs
from app.views.evaluate import load_patch_input

bp = Blueprint("report", __name__, url_prefix="/report")


@bp.route("/")
def index():
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    return render_template("report/index.html", patches=patches)


@bp.route("/<int:patch_id>")
def detail(patch_id):
    patch = MinePatch.query.get_or_404(patch_id)
    units = load_patch_input(patch_id)
    if not units:
        flash("该图斑尚无微地质单元，无法生成报告", "error")
        return redirect(url_for("report.index"))
    result = ev.score_mine(units)
    return render_template("report/detail.html", patch=patch, result=result)


@bp.route("/<int:patch_id>/word")
def word(patch_id):
    patch = MinePatch.query.get_or_404(patch_id)
    units = load_patch_input(patch_id)
    if not units:
        flash("该图斑尚无微地质单元，无法生成报告", "error")
        return redirect(url_for("report.index"))
    result = ev.score_mine(units)
    buf = rs.build_report(patch, result)
    filename = "自然恢复适宜性评价报告_%s.docx" % patch.name
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "wordprocessingml.document")
