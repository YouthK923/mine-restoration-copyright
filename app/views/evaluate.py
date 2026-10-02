# -*- coding: utf-8 -*-
"""适宜性定量评价引擎 —— 路由与页面逻辑。

从数据库加载某图斑的微地质单元与指标数据，调用评价引擎计算，
展示各单元得分、最终评价因子 F、适宜性等级与推荐措施。

入口处按评价流程的顺序检查前置条件（见 app/services/workflow.py），
前置步骤未完成时不予计算，避免在条件不具备时产出评价结论。
"""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user

from app.forms import EmptyForm
from app.models import (db, MinePatch, MicroUnit, IndicatorData,
                        EvaluationResult, ScoreDetail)
from app.services import evaluation_service as ev
from app.services import workflow as wf
from app.services import unit_config
from app.services import standard_check

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

    权重可来自 AHP 计算并保存的生效方案；未配置时用系统默认值。
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


def pack_params(settings, sources=None):
    """把本次计算用到的参数整理成可持久化的快照。

    参数（指标理想取值、图斑参照生态系统基准、权重方案）都能在界面上改，
    所以结果记录必须连「当时用的什么参数」一起留下，否则事后无法复现。
    """
    from app.utils.constants import (IDEAL_SOIL_RATIO, IDEAL_THICKNESS,
                                     IDEAL_ORGANIC, IDEAL_COVERAGE,
                                     IDEAL_SHANNON, HEAVY_METAL_LIMIT)
    defaults = {
        "soil_ratio": IDEAL_SOIL_RATIO, "thickness": IDEAL_THICKNESS,
        "organic_matter": IDEAL_ORGANIC, "coverage": IDEAL_COVERAGE,
        "shannon": IDEAL_SHANNON,
    }
    for metal, limit in HEAVY_METAL_LIMIT.items():
        defaults["hm_" + metal] = limit

    used = {}
    for code, fallback in sorted(defaults.items()):
        value = settings.params.get(code) if settings else None
        if value is None:
            used[code] = {"value": fallback, "default": fallback,
                          "source": "系统默认取值"}
        elif abs(float(value) - float(fallback)) < 1e-9:
            # 库里存着这一项，但取值与系统默认值一致 —— 不能标成「界面配置」，
            # 否则每份报告都会声称用了自定义参数，反而看不出真正的偏离。
            used[code] = {"value": value, "default": fallback,
                          "source": "系统默认取值"}
        else:
            used[code] = {"value": value, "default": fallback,
                          "source": "界面配置（系统默认值 %.4g）" % fallback}
    return {"ideals": used, "weight_sources": dict(sources or {})}


def save_evaluation(patch_id, units):
    """执行评价并把结果与逐层明细落库，返回评价记录。

    权重取各单元类型当前生效的方案（AHP 计算结果），未配置时用
    系统默认权重；来源一并记录。结果 JSON 保留各单元得分、
    一级指标得分与逐条二级指标明细，结果页与报告据此复现
    记录下来的那次评价，不再重新推算。
    """
    weights, sources = load_weights(units)
    # 标准化参数取自该图斑的参照生态系统与指标定义（界面上可改），
    # 没配过的项自动回落到代码常量，历史结果与验证算例不受影响。
    settings = unit_config.for_patch(patch_id)
    res = ev.score_mine(units, weights, settings)
    saved = EvaluationResult(
        patch_id=patch_id,
        final_score=round(res["final_score"], 4),
        grade=res["grade"],
        measures=res["grade_info"]["measure"],
        unit_scores=json.dumps(pack_units(res["unit_results"], sources),
                               ensure_ascii=False),
        # 参数快照 + 计算人：参数现在可以在界面上改，不留快照就复现不了这次结果
        params_json=json.dumps(pack_params(settings, sources),
                               ensure_ascii=False),
        created_by=current_user.id if getattr(current_user, "is_authenticated", False)
        else None,
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


def weak_points(unit_scores, top=3):
    """从已保存的结果里挑出「提升空间最大」的指标。

    提升空间 = 权重 ×（1 − 标准化值）：标准化值越低、权重越大，抬它越划算。
    只读已保存的记录，不重新计算，保证与报告口径一致。
    """
    rows = []
    for u in unit_scores or []:
        for d in u.get("details") or []:
            std = d.get("std_value")
            weight = d.get("weight")
            if std is None or weight is None:
                continue          # 不适用项（未参与计算）不进短板
            rows.append({
                "unit_type": u.get("unit_type"),
                "l2": d.get("l2"),
                "raw": d.get("raw"),
                "std_value": std,
                "gain": weight * (1.0 - std),
            })
    rows.sort(key=lambda x: x["gain"], reverse=True)
    return [x for x in rows if x["gain"] > 1e-9][:top]


def user_label(user_id):
    """把计算人 id 换成「昵称（账户名称）」。"""
    from app.models import User
    if not user_id:
        return None
    u = db.session.get(User, user_id)
    if u is None:
        return "已删除的账号"
    return u.shown_name


def param_source_summary(params):
    """一句话说清参数从哪来：有没有偏离系统默认值。

    多数情况下全部等于系统默认值，报告应直接说明「未偏离」；
    只有真被改过时才点名，便于审阅者一眼看到差异。
    """
    ideals = (params or {}).get("ideals") or {}
    custom = sorted(k for k, v in ideals.items()
                    if v.get("source", "").startswith("界面配置"))
    if not custom:
        return "全部采用系统默认取值，未被改动"
    return "以下 %d 项被改为界面配置值：%s" % (len(custom), "、".join(custom))


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
    params = json.loads(r.params_json) if r.params_json else {}
    return render_template("evaluate/result.html", r=r, patch=patch,
                           unit_scores=unit_scores,
                           undetected=wf.undetected_metals(patch.id)
                           if patch else [],
                           weak=weak_points(unit_scores),
                           params=params.get("ideals") or {},
                           param_sources=param_source_summary(params),
                           check=standard_check.compare(patch.id) if patch else None,
                           operator=user_label(r.created_by))
