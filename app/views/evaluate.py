# -*- coding: utf-8 -*-
"""M8 适宜性定量评价引擎 —— 路由与页面逻辑。

从数据库加载某图斑的微地质单元与指标数据，调用评价引擎计算，
展示各单元得分、最终评价因子 F、适宜性等级与推荐措施。

入口处按论文 4.1 节的流程顺序检查前置条件（见 app/services/workflow.py），
前置步骤未完成时不予计算，避免在条件不具备时产出评价结论。
"""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.forms import EmptyForm
from app.models import db, MinePatch, MicroUnit, IndicatorData, EvaluationResult
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
            "unit_type": u.unit_type,
            "ratio": u.ratio if u.ratio is not None else 0.0,
            "data": data,
        })
    return result


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
        res = ev.score_mine(units)
        saved = EvaluationResult(
            patch_id=patch.id,
            final_score=round(res["final_score"], 4),
            grade=res["grade"],
            measures=res["grade_info"]["measure"],
            unit_scores=json.dumps(
                [{"unit_type": u["unit_type"], "ratio": u["ratio"],
                  "unit_score": round(u["unit_score"], 4)}
                 for u in res["unit_results"]],
                ensure_ascii=False),
        )
        db.session.add(saved)
        db.session.commit()
        return redirect(url_for("evaluate.result", result_id=saved.id))

    return render_template("evaluate/run.html", patch=patch, form=form,
                           progress=progress)


@bp.route("/result/<int:result_id>")
def result(result_id):
    r = db.get_or_404(EvaluationResult, result_id)
    patch = db.session.get(MinePatch, r.patch_id)
    unit_scores = json.loads(r.unit_scores) if r.unit_scores else []
    return render_template("evaluate/result.html", r=r, patch=patch,
                           unit_scores=unit_scores)
