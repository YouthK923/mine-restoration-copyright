# -*- coding: utf-8 -*-
"""适宜性评价引擎（M8）。

按论文式(9) 实现：
- 单元级：F' = Σ（二级指标权重 × 该二级指标下三级指标标准化值）
- 矿山级：F = Σ（Sᵢ × F'ᵢ），Sᵢ 为各微地质单元面积占比
- 等级判定按论文表 4。
"""
from app.utils.constants import DEFAULT_WEIGHTS, grade_of
from app.services import standardization as std


def score_unit(unit_type, data, weights=None):
    """计算单个微地质单元的评价因子 F′。

    返回
    ----
    dict：{ l1_scores: {一级指标: 得分}, unit_score: F′, details: [...] }
    若某一级指标下存在"不适用"（标准化值为 None）的二级指标，
    则按其余项权重归一化后计算，保证单元得分始终有定义。
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS[unit_type]

    std_result = std.standardize_unit(unit_type, data, weights)
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

    unit_score = sum(l1_weights[k] * l1_scores[k] for k in l1_scores)
    return {"l1_scores": l1_scores, "unit_score": unit_score, "details": details}


def score_mine(units):
    """计算整个矿山的评价因子 F 与适宜性等级。

    参数
    ----
    units : list[dict]，每个元素：
        {unit_type, ratio, data}
        ratio 为该单元面积占比（0~1），data 为实测数据 dict。

    返回
    ----
    dict：{ final_score, grade, grade_info, unit_results }
    """
    total = 0.0
    unit_results = []
    for u in units:
        r = score_unit(u["unit_type"], u["data"])
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
