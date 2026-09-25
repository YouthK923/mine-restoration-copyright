# -*- coding: utf-8 -*-
"""M9 报告与结果输出 —— 得分明细、图表、Word / PDF 导出。"""
import io
from datetime import datetime

from flask import Blueprint, render_template, send_file, flash, redirect, url_for

from app.models import db, MinePatch, ReferenceEcosystem
from app.services import evaluation_service as ev
from app.services import report_service as rs
from app.services import workflow as wf
from app.utils import charts
from app.utils import browser
from app.views.evaluate import load_patch_input

bp = Blueprint("report", __name__, url_prefix="/report")


def _prepare(patch_id):
    """加载图斑、参照生态系统并执行评价，供明细页与导出复用。

    同时返回流程检查结果：前置步骤未完成时，调用方应拦截并提示，
    不应直接出报告（报告本质上是评价结论的呈现，不能先于评价产生）。
    """
    patch = db.get_or_404(MinePatch, patch_id)
    progress = wf.patch_progress(patch_id)
    if not progress["ready"]:
        return patch, None, None, None, progress
    units = load_patch_input(patch_id)
    if not units:
        return patch, None, None, None, progress
    result = ev.score_mine(units)
    reference = ReferenceEcosystem.query.filter_by(patch_id=patch_id).first()
    return patch, reference, result, units, progress


def _deny(progress, patch_id, endpoint="report.detail"):
    """前置条件未满足时的统一处理：逐条提示并退回报告列表。"""
    for b in progress["blocking"]:
        flash("暂不能生成报告 —— %s：%s" % (b["label"], b["reason"]), "error")
    if progress["blocking"]:
        flash("请先完成上述步骤后再生成报告。", "error")
    return redirect(url_for("report.index"))


def _charts(result):
    """生成两张图表：单元得分对比 + 一级指标平均得分分布。"""
    units = [(u["unit_type"], u["unit_score"],
              "%.4f" % u["unit_score"]) for u in result["unit_results"]]
    chart_units = charts.hbars(units)

    # 各一级指标在各单元上的平均得分，反映其对评价结果的实际影响
    acc, cnt = {}, {}
    for u in result["unit_results"]:
        for k, v in (u.get("l1_scores") or {}).items():
            acc[k] = acc.get(k, 0.0) + v
            cnt[k] = cnt.get(k, 0) + 1
    items = [(k, acc[k] / cnt[k], "%.4f" % (acc[k] / cnt[k])) for k in acc]
    items.sort(key=lambda x: -x[1])
    chart_weight = charts.donut(items)
    return chart_units, chart_weight


@bp.route("/")
def index():
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    progress = {p.id: wf.patch_progress(p.id) for p in patches}
    return render_template("report/index.html", patches=patches,
                           progress=progress)


@bp.route("/<int:patch_id>")
def detail(patch_id):
    patch, reference, result, units, progress = _prepare(patch_id)
    if result is None:
        return _deny(progress, patch_id)
    chart_units, chart_weight = _charts(result)
    return render_template("report/detail.html", patch=patch, result=result,
                           reference=reference, chart_units=chart_units,
                           chart_weight=chart_weight)


@bp.route("/<int:patch_id>/word")
def word(patch_id):
    patch, reference, result, units, progress = _prepare(patch_id)
    if result is None:
        return _deny(progress, patch_id)
    buf = rs.build_report(patch, result)
    filename = "自然恢复适宜性评价报告_%s.docx" % patch.name
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument."
                              "wordprocessingml.document")


@bp.route("/<int:patch_id>/pdf")
def pdf(patch_id):
    """导出 PDF 报告：服务端渲染打印模板，再交浏览器无头打印。"""
    patch, reference, result, units, progress = _prepare(patch_id)
    if result is None:
        return _deny(progress, patch_id)

    chart_units, chart_weight = _charts(result)
    html = render_template(
        "report/print.html", patch=patch, reference=reference, result=result,
        chart_units=chart_units, chart_weight=chart_weight,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
    data, err = browser.html_to_pdf(html)
    if err:
        flash("PDF 导出失败：%s" % err, "error")
        return redirect(url_for("report.detail", patch_id=patch_id))

    return send_file(io.BytesIO(data), as_attachment=True,
                     download_name="自然恢复适宜性评价报告_%s.pdf" % patch.name,
                     mimetype="application/pdf")
