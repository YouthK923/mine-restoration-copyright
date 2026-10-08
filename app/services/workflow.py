# -*- coding: utf-8 -*-
"""评价流程前置条件（定量评价与报告输出的流程门禁）。

评价流程存在严格的先后关系：
    建立图斑 → 限制性条件判定（通过） → 划分微地质单元并计算面积占比
    → 逐单元录入指标数据 → 计算评价因子并判定等级 → 输出报告

流程约定：「先进行政策、位置约束地质灾害判断……对于满足限制性条件的
废弃矿山，按照地形地貌划分，将其划分为平台、碎石边坡和岩质边坡三种
地质微单元类型，并计算各种地形面积占比。」限制性条件判定（一票否决）
在前，微地质单元划分在后，顺序不可颠倒。

本模块把该顺序固化为可检查的状态。后续模块在入口处调用它，
前置步骤未完成时直接拦截并给出「缺什么、去哪补」的提示，
避免在条件不具备时产出看似合理的评价结论。
"""
from app.models import (db, MicroUnit, IndicatorData, ConstraintCheck,
                        EvaluationResult)
from app.services import unit_config

# 指标数据非空字段（用于判断某单元是否已录入数据）
DATA_FIELDS = ("soil_ratio", "thickness", "ph", "organic_matter",
               "coverage", "shannon", "slope", "aspect")


def _has_data(ind):
    if ind is None:
        return False
    if any(getattr(ind, f, None) is not None for f in DATA_FIELDS):
        return True
    return bool(ind.heavy_metals_dict())


def _data_of(ind):
    """把 IndicatorData 行转成标准化接口要的 dict。"""
    if ind is None:
        return {}
    data = {f: getattr(ind, f, None) for f in DATA_FIELDS}
    data["heavy_metals"] = ind.heavy_metals_dict()
    return data


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
    # 判断标准是「该单元类型启用的必填项是否齐全」，而不是「有没有填过任意一个字段」。
    # 早先只要 8 个字段里有一个非空就算齐，于是碎石边坡只填一个坡度也能跑出
    # F=0.69「基本适宜」；而 score_unit 又会把缺的项剔掉、把权重摊给其余指标，
    # 结论方向还偏乐观。污染指标按方法约定允许「未检测」，不算缺。
    settings = unit_config.for_patch(patch_id)
    missing = []            # 完全没录数据的单元类型
    incomplete = []         # 录了但不齐的单元类型 → [(单元类型, [缺的字段])]
    for u in units:
        ind = IndicatorData.query.filter_by(unit_id=u.id).first()
        data = _data_of(ind)
        gaps = settings.missing_fields(u.unit_type, data)
        if not _has_data(ind):
            missing.append(u.unit_type)
        elif gaps:
            incomplete.append((u.unit_type, gaps))

    if not units:
        data_step = {"done": False, "ready": False, "missing": [],
                     "detail": "尚无可录入数据的微地质单元"}
    elif missing:
        data_step = {"done": False, "ready": False, "missing": missing,
                     "detail": "以下微地质单元尚未录入指标数据：%s"
                               % "、".join(missing)}
    elif incomplete:
        data_step = {"done": False, "ready": False,
                     "missing": [t for t, _ in incomplete],
                     "detail": "以下微地质单元的必填指标未填齐：%s"
                               % "；".join("%s缺 %s" % (t, "、".join(g))
                                           for t, g in incomplete)}
    else:
        data_step = {"done": True, "ready": True, "missing": [],
                     "detail": "全部 %d 个微地质单元的指标数据已录入" % len(units)}

    # 占比合计必须落在 100% 附近才算通过。只挡「偏小」是不够的：
    # 库里若出现合计 1.5 的记录（手工改库、导入异常），F = Σ(Sᵢ×F′ᵢ)
    # 会被放大到 1.5 倍，所以上下都要挡。
    ratio_ok = 0.999 <= ratio_sum <= 1.001 if units else False
    if units and not ratio_ok:
        units_step["detail"] += "（占比合计不等于 100%，请检查面积录入）"

    # ---- 汇总未满足的前置条件（按评价流程的顺序：限制性判定优先） ----
    # reason 只写「缺什么」这一个事实，不写为什么重要的说明 ——
    # 缺少什么由 label 指明，怎么补由 fix_label 给出，页面不必再解释一遍。
    blocking = []
    if not constraint_step["done"]:
        blocking.append({
            "step": "constraint", "label": "限制性条件判定未执行",
            "reason": "四项限制性条件尚未逐项判定。",
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


def undetected_metals(patch_id):
    """列出该图斑各单元「未检测」的重金属，供结果页与报告如实标注。

    方法约定允许未检测的重金属按未受污染计入，但报告里必须写明是哪些 ——
    否则读报告的人会以为这些项是实测达标。
    只列启用了土壤指标的单元：岩质边坡本来就不评价土壤，列 8 项未检测是噪音。
    """
    settings = unit_config.for_patch(patch_id)
    out = []
    for u in MicroUnit.query.filter_by(patch_id=patch_id).all():
        if settings.group_enabled(u.unit_type, "土壤指标", "soil") is False:
            continue
        ind = IndicatorData.query.filter_by(unit_id=u.id).first()
        if ind is None:
            continue
        metals = settings.undetected_metals(_data_of(ind))
        if metals:
            out.append((u.unit_type, metals))
    return out


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
