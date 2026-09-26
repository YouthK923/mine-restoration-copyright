# -*- coding: utf-8 -*-
"""评价流程前置条件（定量评价与报告输出的流程门禁）。

论文 4.1 节确定的评价流程存在严格的先后关系：
    建立图斑 → 限制性条件判定（通过） → 划分微地质单元并计算面积占比
    → 逐单元录入指标数据 → 计算评价因子并判定等级 → 输出报告

论文原文：「先进行政策、位置约束地质灾害判断……对于满足限制性条件的
废弃矿山，按照地形地貌划分，将其划分为平台、碎石边坡和岩质边坡三种
地质微单元类型，并计算各种地形面积占比。」限制性条件判定（一票否决）
在前，微地质单元划分在后，顺序不可颠倒。

本模块把该顺序固化为可检查的状态。后续模块在入口处调用它，
前置步骤未完成时直接拦截并给出「缺什么、去哪补」的提示，
避免在条件不具备时产出看似合理的评价结论。
"""
from app.models import (db, MicroUnit, IndicatorData, ConstraintCheck,
                        EvaluationResult)

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

    # ---- 汇总未满足的前置条件（按论文 4.1 节的流程顺序：限制性判定优先） ----
    # reason 只写「缺什么」这一个事实，不写为什么重要的说明 ——
    # 缺少什么由 label 指明，怎么补由 fix_label 给出，页面不必再解释一遍。
    blocking = []
    if not constraint_step["done"]:
        blocking.append({
            "step": "constraint", "label": "限制性条件判定未执行",
            "reason": "五项限制性条件尚未逐项判定。",
            "fix_url": "/constraint/%d" % patch_id, "fix_label": "去执行判定",
        })
    elif not constraint_step["passed"]:
        blocking.append({
            "step": "constraint", "label": "限制性条件判定未通过",
            "reason": cc.reason or "",
            "fix_url": "/constraint/%d" % patch_id, "fix_label": "去复核判定结果",
        })
    if not units_step["done"]:
        blocking.append({
            "step": "units", "label": "未划分微地质单元",
            "reason": "该图斑下没有任何微地质单元。",
            "fix_url": "/unit/%d" % patch_id, "fix_label": "去划分",
        })
    elif not ratio_ok:
        blocking.append({
            "step": "units", "label": "面积占比合计不为 100%",
            "reason": "当前合计 %.2f%%。" % (ratio_sum * 100),
            "fix_url": "/unit/%d" % patch_id, "fix_label": "去核对面积",
        })
    if units_step["done"] and not data_step["ready"]:
        blocking.append({
            "step": "data", "label": "指标数据未录入完整",
            "reason": data_step["detail"],
            "fix_url": "/indicator/", "fix_label": "去录入",
        })

    return {
        "units": units_step,
        "constraint": constraint_step,
        "data": data_step,
        "blocking": blocking,
        "ready": not blocking,
    }


def latest_result(patch_id):
    """取该图斑最近一次的评价记录。"""
    return EvaluationResult.query.filter_by(patch_id=patch_id) \
        .order_by(EvaluationResult.id.desc()).first()


def report_progress(patch_id):
    """报告输出的前置条件：评价流程齐备，且已有评价记录。

    报告本质上是评价结论的呈现，因此必须先真实执行过定量评价，
    导出时读取已保存的评价结果，而不是在导出环节重新计算。
    否则评价完成后再修改指标数据，报告会与系统记录的评价结论不一致，
    同一份评价出现两个数字，结论无法追溯。

    返回 dict：{ready, blocking, result, flow}
        result 为最近一次评价记录（EvaluationResult），无记录时为空。
    """
    flow = patch_progress(patch_id)
    blocking = list(flow["blocking"])
    record = latest_result(patch_id)
    if not blocking and record is None:
        blocking.append({
            "step": "evaluate", "label": "尚未执行适宜性评价",
            "reason": "该图斑还没有评价记录。",
            "fix_url": "/evaluate/%d" % patch_id,
            "fix_label": "去执行评价",
        })
    return {
        "ready": not blocking,
        "blocking": blocking,
        "result": record,
        "flow": flow,
    }
