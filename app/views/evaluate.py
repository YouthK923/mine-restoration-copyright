# -*- coding: utf-8 -*-
"""M8 适宜性定量评价引擎 —— 路由与页面逻辑。

从数据库加载某图斑的微地质单元与指标数据，调用评价引擎计算，
展示各单元得分、最终评价因子 F、适宜性等级与推荐措施。
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.forms import EmptyForm
from app.models import db, MinePatch, MicroUnit, IndicatorData, EvaluationResult
from app.services import evaluation_service as ev

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


@bp.route("/")
def index():
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    # 每图斑是否已有评价结果
    latest = {}
    for p in patches:
        r = EvaluationResult.query.filter_by(patch_id=p.id) \
                .order_by(EvaluationResult.id.desc()).first()
        latest[p.id] = r
    return render_template("evaluate/index.html", patches=patches, latest=latest)


@bp.route("/<int:patch_id>", methods=["GET", "POST"])
def run(patch_id):
    patch = MinePatch.query.get_or_404(patch_id)
    form = EmptyForm()
    result = None

    if request.method == "POST" and form.validate_on_submit():
        units = load_patch_input(patch_id)
        if not units:
            flash("该图斑尚无微地质单元，请先划分微地质单元", "error")
            return redirect(url_for("evaluate.index"))
        # 计算并入库
        res = ev.score_mine(units)
        import json
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

    return render_template("evaluate/run.html", patch=patch, form=form, result=result)


@bp.route("/result/<int:result_id>")
def result(result_id):
    r = EvaluationResult.query.get_or_404(result_id)
    patch = MinePatch.query.get(r.patch_id)
    import json
    unit_scores = json.loads(r.unit_scores) if r.unit_scores else []
    return render_template("evaluate/result.html", r=r, patch=patch,
                           unit_scores=unit_scores)
