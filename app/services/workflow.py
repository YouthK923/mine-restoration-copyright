# -*- coding: utf-8 -*-
"""评价流程前置条件（M8/M9 的流程门禁）。

论文 4.1 节确定的评价流程存在严格的先后关系：
    建立图斑 → 划分微地质单元 → 限制性条件判定（通过）
    → 录入指标数据 → 计算评价因子并判定等级 → 输出报告

本模块把该顺序固化为可检查的状态。后续模块在入口处调用它，
前置步骤未完成时直接拦截并给出「缺什么、去哪补」的提示，
避免在条件不具备时产出看似合理的评价结论。
"""
from app.models import (db, MicroUnit, IndicatorData, ConstraintCheck)

# 指标数据非空字段（用于判断某单元是否已录入数据）
DATA_FIELDS = ("soil_ratio", "thickness", "ph", "organic_matter",
               "coverage", "shannon", "slope", "aspect")


def _has_data(ind):
    if ind is None:
        return False
    if any(getattr(ind, f, None) is not None for f in DATA_FIELDS):
        return True
    return bool(ind.heavy_metals_dict())


def patch_progress(patch_id):
    """检查某图斑的评价流程完成情况。

    返回 dict：
        units       {done, count, ratio_sum, detail}
        constraint  {done, passed, detail}
        data        {done, ready, missing, detail}
        blocking    未满足的前置步骤列表（按流程顺序）
        ready       是否可进入定量评价
    """
    units = MicroUnit.query.filter_by(patch_id=patch_id).all()
    ratio_sum = sum(u.ratio or 0.0 for u in units)

    # ---- 步骤一：微地质单元 ----
    units_step = {
        "done": bool(units),
        "count": len(units),
        "ratio_sum": ratio_sum,
        "detail": ("已划分 %d 个微地质单元，面积占比合计 %.2f%%"
                   % (len(units), ratio_sum * 100))
                  if units else "尚未划分微地质单元",
    }

    # ---- 步骤二：限制性条件判定 ----
    cc = ConstraintCheck.query.filter_by(patch_id=patch_id) \
        .order_by(ConstraintCheck.id.desc()).first()
    if cc is None:
        constraint_step = {"done": False, "passed": False,
                           "detail": "尚未执行限制性条件判定"}
    elif cc.passed:
        constraint_step = {"done": True, "passed": True,
                           "detail": "限制性条件判定已通过"}
    else:
        constraint_step = {"done": True, "passed": False,
                           "detail": "限制性条件判定未通过（%s）" % (cc.reason or "")}

    # ---- 步骤三：指标数据 ----
    missing = []
    for u in units:
        ind = IndicatorData.query.filter_by(unit_id=u.id).first()
        if not _has_data(ind):
            missing.append(u.unit_type)
    if not units:
        data_step = {"done": False, "ready": False, "missing": [],
                     "detail": "尚无可录入数据的微地质单元"}
    elif missing:
        data_step = {"done": False, "ready": False, "missing": missing,
                     "detail": "以下微地质单元尚未录入指标数据：%s"
                               % "、".join(missing)}
    else:
        data_step = {"done": True, "ready": True, "missing": [],
                     "detail": "全部 %d 个微地质单元的指标数据已录入" % len(units)}

    ratio_ok = ratio_sum > 0.999 if units else False
    if units and not ratio_ok:
        units_step["detail"] += "（占比合计不等于 100%，请检查面积录入）"

    # ---- 汇总未满足的前置条件（按流程顺序） ----
    blocking = []
    if not units_step["done"]:
        blocking.append({
            "step": "units", "label": "划分微地质单元",
            "reason": "该图斑尚未划分微地质单元，无法确定各单元的面积权重。",
            "fix_url": "/unit/%d" % patch_id, "fix_label": "去划分微地质单元",
        })
    elif not ratio_ok:
        blocking.append({
            "step": "units", "label": "补齐单元面积",
            "reason": "各微地质单元面积占比合计不等于 100%，加权结果会失真。",
            "fix_url": "/unit/%d" % patch_id, "fix_label": "去核对单元面积",
        })
    if not constraint_step["done"]:
        blocking.append({
            "step": "constraint", "label": "执行限制性条件判定",
            "reason": "尚未执行限制性条件判定。论文流程要求先判定政策、区位约束、"
                      "土壤污染、地质灾害与耕地属性，通过后方可进入定量评价。",
            "fix_url": "/constraint/%d" % patch_id, "fix_label": "去执行限制性判定",
        })
    elif not constraint_step["passed"]:
        blocking.append({
            "step": "constraint", "label": "限制性条件判定未通过",
            "reason": "限制性条件判定未通过。按论文流程，此类矿山应直接判定为"
                      "「人工辅助或生态重建」，不进入定量评价。",
            "fix_url": "/constraint/%d" % patch_id, "fix_label": "去复核判定结果",
        })
    if units_step["done"] and not data_step["ready"]:
        blocking.append({
            "step": "data", "label": "录入指标数据",
            "reason": data_step["detail"] + "。缺少数据时计算会把空值按不适用跳过，"
                      "得出的结论不能反映实际情况。",
            "fix_url": "/indicator/", "fix_label": "去录入指标数据",
        })

    return {
        "units": units_step,
        "constraint": constraint_step,
        "data": data_step,
        "blocking": blocking,
        "ready": not blocking,
    }
