# -*- coding: utf-8 -*-
"""适宜性定量评价引擎 —— 路由与页面逻辑。

从数据库加载某图斑的微地质单元与指标数据，调用评价引擎计算，
展示各单元得分、最终评价因子 F、适宜性等级与推荐措施。

入口处按论文 4.1 节的流程顺序检查前置条件（见 app/services/workflow.py），
前置步骤未完成时不予计算，避免在条件不具备时产出评价结论。
"""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.forms import EmptyForm
from app.models import (db, MinePatch, MicroUnit, IndicatorData,
                        EvaluationResult, ScoreDetail)
from app.services import evaluation_service as ev
from app.services import workflow as wf

bp = Blueprint("evaluate", __name__, url_prefix="/evaluate")


def load_patch_input(patch_id):
    """从数据库组装评价引擎输入。"""
    units = MicroUnit.query.filter_by(patch_id=patch_id).all()
    result = []
    for u in units:
        ind = IndicatorData.query.filter_by(unit_id=u.id).first()
        data = {
            "soil_ratio": ind.soil_ratio if ind else None,
            "thickness": ind.thickness if ind else None,
            "ph": ind.ph if ind else None,
            "organic_matter": ind.organic_matter if ind else None,
            "heavy_metals": ind.heavy_metals_dict() if ind else {},
            "coverage": ind.coverage if ind else None,
            "shannon": ind.shannon if ind else None,
            "slope": ind.slope if ind else None,
            "aspect": ind.aspect if ind else None,
        }
        result.append({
            "unit_id": u.id,
            "unit_type": u.unit_type,
            "ratio": u.ratio if u.ratio is not None else 0.0,
            "data": data,
        })
    return result


def _round(v, n=6):
    return None if v is None else round(v, n)


def load_weights(units):
    """解析各单元类型当前生效的权重与来源说明。

    权重可来自 AHP 计算并保存的生效方案；未配置时用论文表 3 的默认值。
    来源一并记录，便于报告标注与事后复核。
    """
    from app.services import weight_service as ws
    weights, sources = {}, {}
    for u in units:
        ut = u["unit_type"]
        if ut not in weights:
            w, label, _ = ws.effective_weights(ut)
            weights[ut] = w
            sources[ut] = label
    return weights, sources


def pack_units(unit_results, sources=None):
    """把评价结果整理为可持久化的 JSON。

    完整保留各单元得分、一级指标得分与逐条二级指标明细，
    使结果页与报告能够复现「已记录的那一次评价」，
    而不是每次打开时重新推算。
    """
    sources = sources or {}
    out = []
    for u in unit_results:
        out.append({
            "unit_type": u["unit_type"],
            "ratio": _round(u["ratio"]),
            "unit_score": _round(u["unit_score"]),
            "weighted": _round(u["weighted"]),
            "weight_source": sources.get(u["unit_type"]),
            "l1_scores": {k: _round(v) for k, v in u["l1_scores"].items()},
            "details": [{
                "l1": d["l1"], "l2": d["l2"],
                "raw": None if d["raw"] is None else str(d["raw"]),
                "std_value": _round(d["std_value"]),
                "weight": _round(d["weight"]),
                "contribution": _round(d["contribution"]),
            } for d in u["details"]],
        })
    return out


def save_evaluation(patch_id, units):
    """执行评价并把结果与逐层明细落库，返回评价记录。

    权重取各单元类型当前生效的方案（AHP 计算结果），未配置时用
    论文表 3 的默认权重；来源一并记录。结果 JSON 保留各单元得分、
    一级指标得分与逐条二级指标明细，结果页与报告据此复现
    记录下来的那次评价，不再重新推算。
    """
    weights, sources = load_weights(units)
    res = ev.score_mine(units, weights)
    saved = EvaluationResult(
        patch_id=patch_id,
        final_score=round(res["final_score"], 4),
        grade=res["grade"],
        measures=res["grade_info"]["measure"],
        unit_scores=json.dumps(pack_units(res["unit_results"], sources),
                               ensure_ascii=False),
    )
    db.session.add(saved)
    db.session.flush()      # 先取得 result.id，再写明细

    unit_ids = {u["unit_type"]: u["unit_id"] for u in units}
    for u in res["unit_results"]:
        for d in u["details"]:
            db.session.add(ScoreDetail(
                result_id=saved.id,
                unit_id=unit_ids.get(u["unit_type"]),
                l1_name=d["l1"], l2_name=d["l2"],
                raw_value=None if d["raw"] is None else str(d["raw"]),
                std_value=d["std_value"], weight=d["weight"],
                contribution=d["contribution"]))
    db.session.commit()
    return saved


def block_reasons(progress):
    """把未满足的前置条件转成可读的拦截原因。"""
    return ["%s：%s" % (b["label"], b["reason"]) for b in progress["blocking"]]


@bp.route("/")
def index():
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    latest = {}
    progress = {}
    for p in patches:
        latest[p.id] = EvaluationResult.query.filter_by(patch_id=p.id) \
            .order_by(EvaluationResult.id.desc()).first()
        progress[p.id] = wf.patch_progress(p.id)
    return render_template("evaluate/index.html", patches=patches,
                           latest=latest, progress=progress)


@bp.route("/<int:patch_id>", methods=["GET", "POST"])
def run(patch_id):
    patch = db.get_or_404(MinePatch, patch_id)
    form = EmptyForm()
    progress = wf.patch_progress(patch_id)

    if request.method == "POST" and form.validate_on_submit():
        if not progress["ready"]:
            for reason in block_reasons(progress):
                flash("无法执行评价 —— " + reason, "error")
            return redirect(url_for("evaluate.run", patch_id=patch_id))

        units = load_patch_input(patch_id)
        saved = save_evaluation(patch.id, units)
        return redirect(url_for("evaluate.result", result_id=saved.id))

    # 展示将采用的权重来源，便于在执行前确认
    units_now = load_patch_input(patch_id)
    _, sources = load_weights(units_now) if units_now else ({}, {})
    return render_template("evaluate/run.html", patch=patch, form=form,
                           progress=progress, weight_sources=sources)


@bp.route("/result/<int:result_id>")
def result(result_id):
    r = db.get_or_404(EvaluationResult, result_id)
    patch = db.session.get(MinePatch, r.patch_id)
    unit_scores = json.loads(r.unit_scores) if r.unit_scores else []
    return render_template("evaluate/result.html", r=r, patch=patch,
                           unit_scores=unit_scores)
