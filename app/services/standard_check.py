# -*- coding: utf-8 -*-
"""评价结论与地方标准 / 政策文件的对照。

标准知识库只作文件储备与比对，**不参与评价因子 F 的计算**：评价仍按内置的
指标体系与权重算，算完之后再拿结论去对照文件里的判定项，回答
「这个结论是否符合当地文件的要求」。

对照结果有三种，映射不上的项如实标为「待人工判断」，不由系统替文件下结论：

    符合        —— 系统里有对应数据，且满足文件里的判定条件
    不符合      —— 系统里有对应数据，但不满足
    待人工判断  —— 文件里的定性要求，系统内没有对应数据（如「地形地貌与周边协调」）

对照用到的数据全部来自系统已有记录：限制性条件判定结果、各微地质单元实测值、
参照生态系统基准、最近一次评价记录。
"""
import re

from app.models import (db, MinePatch, MicroUnit, IndicatorData, ConstraintCheck,
                        Standard, StandardRule, ReferenceEcosystem, EvaluationResult)

OK = "符合"
BAD = "不符合"
MANUAL = "待人工判断"

# 结论 → 页面上的标签样式（沿用既有的 tag 样式，不新增样式）
TAG_CLASS = {OK: "tag--ok", BAD: "tag--warn", MANUAL: "tag--muted"}


def province_of(region):
    """从行政区里认出已收录的省份：「河北省唐山市玉田县」→「河北」。

    库里没有这个省份的标准时返回 None，由调用方给出「未收录」的提示。
    """
    if not region:
        return None
    provinces = {p for (p,) in db.session.query(Standard.province).distinct()
                 if p}
    for p in sorted(provinces, key=len, reverse=True):
        if p in region:
            return p
    return None


def _num(text):
    if text is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(text))
    return float(m.group(0)) if m else None


def _cmp(value, op, threshold):
    """按比较符判断；阈值不是数字或取值缺失时返回 None（无法判断）。"""
    t = _num(threshold)
    if value is None or t is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if op == ">=":
        return v >= t
    if op == ">":
        return v > t
    if op == "<=":
        return v <= t
    if op == "<":
        return v < t
    if op == "==":
        return abs(v - t) < 1e-9
    return None


def _coverage_stats(patch_id):
    """各单元植被覆盖度的面积加权值与最低值（只统计录了实测值的单元）。"""
    rows = (db.session.query(MicroUnit, IndicatorData)
            .outerjoin(IndicatorData, IndicatorData.unit_id == MicroUnit.id)
            .filter(MicroUnit.patch_id == patch_id).all())
    values, num, den = [], 0.0, 0.0
    for unit, data in rows:
        cov = getattr(data, "coverage", None) if data is not None else None
        if cov is None:
            continue
        values.append(cov)
        w = unit.ratio or 0.0
        num += cov * w
        den += w
    if not values:
        return None, None
    return (num / den if den else None), min(values)


def _context(patch):
    """把对照要用到的数据一次性取出来。"""
    check = (ConstraintCheck.query.filter_by(patch_id=patch.id)
             .order_by(ConstraintCheck.id.desc()).first())
    ref = ReferenceEcosystem.query.filter_by(patch_id=patch.id).first()
    result = (EvaluationResult.query.filter_by(patch_id=patch.id)
              .order_by(EvaluationResult.id.desc()).first())
    weighted, lowest = _coverage_stats(patch.id)
    return {
        "patch": patch,
        "constraint": check,
        "benchmark": getattr(ref, "coverage_benchmark", None) if ref else None,
        "has_reference": ref is not None,
        "result": result,
        "grade": getattr(result, "grade", None) if result else None,
        "score": getattr(result, "final_score", None) if result else None,
        "coverage": weighted,
        "coverage_min": lowest,
    }


def _judge(item, op, threshold, ctx):
    """把一条文件规则映射到系统数据，返回 (结论, 依据说明)。"""
    name = item or ""
    cov, cov_min = ctx["coverage"], ctx["coverage_min"]
    check = ctx["constraint"]

    def cov_text():
        if cov is None:
            return "尚未录入植被覆盖度"
        return "面积加权覆盖度 %.2f%%（最低单元 %.2f%%）" % (cov, cov_min)

    # ---- 植被覆盖度（含趋势）----
    if "趋势" in name:
        return MANUAL, "需连续多年的监测数据，系统内没有时间序列"
    if "植被覆盖" in name:
        if cov is None:
            return MANUAL, cov_text()
        r = _cmp(cov, op, threshold)
        if r is None:
            return MANUAL, cov_text() + "；文件给出的条件为「%s %s」" % (op, threshold)
        return (OK if r else BAD), cov_text()

    # ---- 参照生态系统 ----
    if "参照生态系统调查" in name or "参照系调查" in name:
        return ((OK, "已录入参照生态系统的植被覆盖度与生物多样性基准")
                if ctx["has_reference"] else
                (MANUAL, "尚未录入参照生态系统基准"))
    if "参照系" in name:
        if cov is None or ctx["benchmark"] is None:
            return MANUAL, "缺参照生态系统基准或覆盖度实测值"
        gap = (ctx["benchmark"] - cov)
        gap = 0.0 if gap < 0 else gap
        r = _cmp(gap, op, threshold)
        if r is None:
            return MANUAL, "与参照系差距 %.2f 个百分点" % gap
        return (OK if r else BAD), "与参照系差距 %.2f 个百分点（基准 %.2f%%）" % (
            gap, ctx["benchmark"])

    # ---- 污染与地质灾害 ----
    if "污染" in name:
        if check is None or check.pollution_pass is None:
            return MANUAL, "尚未完成限制性条件判定"
        return ((OK, "限制性判定：土壤污染一项通过") if check.pollution_pass else
                (BAD, "限制性判定：土壤污染一项未通过"))
    if "地质灾害" in name:
        if check is None or check.geo_pass is None:
            return MANUAL, "尚未完成限制性条件判定"
        if not check.geo_pass:
            return BAD, "限制性判定：存在地质灾害"
        if "发育程度" in name:
            return MANUAL, "系统只记录「有无地质灾害」，未记录发育程度分级"
        return OK, "限制性判定：地质灾害一项通过"

    # ---- 责任主体 ----
    if "责任主体" in name:
        missing = ctx["patch"].responsible_entity_missing
        if missing is None:
            return MANUAL, "图斑档案未填写责任主体是否缺失"
        if missing:
            return OK, "图斑档案记录责任主体缺失，按文件属政府主导治理"
        if "政府" in name:
            return MANUAL, "责任主体未缺失，是否符合「政府」要求需人工核实"
        return OK, "图斑档案记录责任主体明确"

    # ---- 适宜性分级 / 指数 ----
    if "适宜性分级" in name or "适宜性评价" in name:
        # 文件只要求「做过自然恢复适宜性分级」，系统已经给出等级
        if ctx["grade"] is None:
            return MANUAL, "尚未执行定量评价"
        return OK, "系统已给出适宜性等级：%s（F=%.4f）" % (ctx["grade"], ctx["score"])
    if "适宜性指数" in name:
        # 指数是要跟阈值比的：文件没给具体阈值时不能替它下结论
        if ctx["grade"] is None:
            return MANUAL, "尚未执行定量评价"
        t = _num(threshold)
        if t is None:
            return MANUAL, ("文件未给出具体阈值，系统评价因子 F=%.4f（%s），需人工比对"
                            % (ctx["score"], ctx["grade"]))
        r = _cmp(ctx["score"], op, t)
        if r is None:
            return MANUAL, "系统评价因子 F=%.4f" % ctx["score"]
        return (OK if r else BAD), ("系统评价因子 F=%.4f，文件要求 %s %s"
                                    % (ctx["score"], op, threshold))

    # ---- 其它定性要求 ----
    return MANUAL, "系统内无对应数据，需人工核实"


def compare(patch_id):
    """生成某图斑的评价结论与当地标准 / 政策文件的对照结果。"""
    patch = db.session.get(MinePatch, patch_id)
    if patch is None:
        return None

    province = province_of(patch.admin_region)
    out = {
        "patch": patch,
        "region": patch.admin_region or "",
        "province": province,
        "covered": False,
        "message": "",
        "standards": [],
        "totals": {OK: 0, BAD: 0, MANUAL: 0},
        "necessary": {"符合": 0, "共计": 0},
    }
    if province is None:
        out["message"] = ("未收录该省份的地方标准与政策文件"
                          "（图斑所在行政区：%s）" % (patch.admin_region or "未填写"))
        return out

    standards = (Standard.query.filter_by(province=province)
                 .order_by(Standard.category.desc(), Standard.name).all())
    if not standards:
        out["message"] = "未收录该省份的地方标准与政策文件（%s）" % province
        return out

    ctx = _context(patch)
    out["covered"] = True
    for s in standards:
        rules = (StandardRule.query.filter_by(standard_id=s.id)
                 .order_by(StandardRule.id).all())
        rows = []
        for r in rules:
            verdict, evidence = _judge(r.item, r.operator, r.threshold, ctx)
            rows.append({
                "item": r.item, "operator": r.operator, "threshold": r.threshold,
                "condition_type": r.condition_type or "", "region": r.region,
                "note": r.note, "verdict": verdict, "tag": TAG_CLASS[verdict],
                "evidence": evidence,
            })
            out["totals"][verdict] = out["totals"].get(verdict, 0) + 1
            if (r.condition_type or "") == "必要条件":
                out["necessary"]["共计"] += 1
                if verdict == OK:
                    out["necessary"]["符合"] += 1
        out["standards"].append({
            "name": s.name, "doc_number": s.doc_number, "category": s.category,
            "summary": s.summary, "rules": rows,
            "counts": {k: sum(1 for x in rows if x["verdict"] == k)
                       for k in (OK, BAD, MANUAL)},
        })
    return out
