# -*- coding: utf-8 -*-
"""适宜性评价引擎。

按加权合成公式实现：
- 单元级：F' = Σ（二级指标权重 × 该二级指标下三级指标标准化值）
- 矿山级：F = Σ（Sᵢ × F'ᵢ），Sᵢ 为各微地质单元面积占比
- 等级判定按适宜性等级划分表。
"""
from app.utils.constants import DEFAULT_WEIGHTS, grade_of
from app.services import standardization as std


def score_unit(unit_type, data, weights=None, settings=None):
    """计算单个微地质单元的评价因子 F′。

    参数
    ----
    weights  : 该单元类型的权重；不传用系统默认权重
    settings : 图斑级标准化参数（基准值与理想取值）；不传全部按代码常量

    返回
    ----
    dict：{ l1_scores: {一级指标: 得分}, unit_score: F′, details: [...] }
    若某一级指标下存在"不适用"（标准化值为 None）的二级指标，
    则按其余项权重归一化后计算，保证单元得分始终有定义。
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS[unit_type]

    std_result = std.standardize_unit(unit_type, data, weights, settings)
    l1_weights = weights["l1"]
    l1_scores = {}
    details = []

    for l1_name, items in std_result.items():
        wsum = 0.0
        acc = 0.0
        for l2_name, (raw, std_value, w2) in items.items():
            if std_value is None:
                # 不适用项：不计入
                details.append({
                    "l1": l1_name, "l2": l2_name, "raw": raw,
                    "std_value": None, "weight": w2, "contribution": None,
                })
                continue
            contribution = std_value * w2
            acc += contribution
            wsum += w2
            details.append({
                "l1": l1_name, "l2": l2_name, "raw": raw,
                "std_value": std_value, "weight": w2,
                "contribution": contribution,
            })
        l1_scores[l1_name] = acc / wsum if wsum > 0 else 0.0

    # 一级指标权重按实际参与计算的指标归一化。
    # 内置权重本身已归一（和为 1），此处为恒等变换；
    # 若某层指标缺失或自定义权重不完整，可避免单元得分被整体压低。
    lw_sum = sum(l1_weights[k] for k in l1_scores if k in l1_weights)
    if lw_sum > 0:
        unit_score = sum(l1_weights[k] * l1_scores[k]
                         for k in l1_scores if k in l1_weights) / lw_sum
    else:
        unit_score = 0.0
    return {"l1_scores": l1_scores, "unit_score": unit_score, "details": details}


def score_mine(units, weights_map=None, settings=None):
    """计算整个矿山的评价因子 F 与适宜性等级。

    参数
    ----
    units : list[dict]，每个元素：
        {unit_type, ratio, data}
        ratio 为该单元面积占比（0~1），data 为实测数据 dict。
    weights_map : dict，{单元类型: 权重结构}。未提供的单元类型
        使用系统默认权重。权重可来自 AHP 计算并经
        weight_service 保存生效，从而真正参与评价。
    settings : 图斑级标准化参数（参照生态系统基准、指标理想取值），
        由 app.services.unit_config.for_patch() 生成；不传按代码常量。

    返回
    ----
    dict：{ final_score, grade, grade_info, unit_results }
    """
    weights_map = weights_map or {}
    total = 0.0
    unit_results = []
    for u in units:
        r = score_unit(u["unit_type"], u["data"],
                       weights_map.get(u["unit_type"]), settings)
        weighted = u["ratio"] * r["unit_score"]
        total += weighted
        unit_results.append({
            "unit_type": u["unit_type"],
            "ratio": u["ratio"],
            "unit_score": r["unit_score"],
            "weighted": weighted,
            "l1_scores": r["l1_scores"],
            "details": r["details"],
        })

    grade_info = grade_of(total)
    return {
        "final_score": total,
        "grade": grade_info["grade"],
        "grade_info": grade_info,
        "unit_results": unit_results,
    }
