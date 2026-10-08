# -*- coding: utf-8 -*-
"""工作台数据：统计数字、评价流程步骤状态、侧边栏待办角标。

首页（工作台）需要把「现在有哪些数据」「流程走到哪一步」「哪一步还差活」
一次算清楚，供模板直接渲染。集中在此，避免在视图与模板里各算一遍。
"""
from flask import g

from app.models import (db, Project, MinePatch, MicroUnit, IndicatorData,
                        ConstraintCheck, EvaluationResult, Standard)
from app.services import workflow as wf

# 评价流程的八个步骤（顺序即评价流程的作业顺序）
#   key        步骤标识
#   no         步骤编号（01~08）
#   title      名称
#   icon       图标名（见 templates/_macros.html 的 ICONS）
#   desc       一句话说明
#   href       入口地址
STEPS = [
    dict(key="project", no="01", title="项目与矿山档案", icon="folder",
         href="/project/",
         desc="建立评价项目、录入矿山图斑、挂接遥感影像、设置参照生态系统"),
    dict(key="standard", no="02", title="政策与标准知识库", icon="book",
         href="/standard/",
         desc="收录地方标准与政策文件，结构化判定规则，支持省际口径比对"),
    dict(key="constraint", no="03", title="限制性指标判定", icon="shield",
         href="/constraint/",
         desc="政策、区位约束、土壤污染、地质灾害四项一票否决"),
    dict(key="unit", no="04", title="微地质单元", icon="layers",
         href="/unit/",
         desc="划分岩质边坡、碎石边坡、平台三类单元，自动计算面积占比"),
    dict(key="ahp", no="05", title="指标体系与权重", icon="sliders",
         href="/ahp/",
         desc="指标定义维护，判断矩阵录入、权重计算与一致性检验、多专家汇总"),
    dict(key="indicator", no="06", title="指标数据采集", icon="database",
         href="/indicator/",
         desc="按微地质单元录入土壤、植被、地形指标，支持 CSV / Excel 批量导入"),
    dict(key="evaluate", no="07", title="适宜性定量评价", icon="target",
         href="/evaluate/",
         desc="指标标准化、分单元赋分、面积加权合成，判定适宜性等级"),
    dict(key="report", no="08", title="报告与结果输出", icon="file",
         href="/report/",
         desc="结果图表与逐层得分明细，导出 PDF 与 Word 评价报告"),
]


def _has_data(ind):
    return wf._has_data(ind)


# 系统的九个功能模块（登录页介绍用，含不在评价流程内的账号与权限管理）
MODULES = [
    ("01", "账号与权限管理", "自助注册与登录注销、管理员与操作员两种职务、写操作自动留痕"),
    ("02", "项目与矿山档案", "建立项目、录入图斑、挂接遥感影像、设置参照生态系统"),
    ("03", "政策与标准知识库", "标准判定条件结构化为规则，支持省际口径比对"),
    ("04", "限制性指标判定", "政策、区位、污染、地质灾害四项一票否决"),
    ("05", "微地质单元管理", "划分岩质边坡、碎石边坡、平台，自动算面积占比"),
    ("06", "指标体系与权重", "指标定义维护、AHP 判断矩阵与一致性检验、多专家汇总"),
    ("07", "指标数据采集", "按单元类型录入土壤、植被、地形指标，支持批量导入"),
    ("08", "适宜性定量评价", "四类标准化、分单元赋分、面积加权、等级判定"),
    ("09", "报告与结果输出", "结果图表与逐层得分明细，导出 PDF 与 Word 报告"),
]


def snapshot():
    """一次算出工作台需要的全部数据（同一请求内只算一次）。

    返回 dict：
        stats     {projects, patches, unit_types, standards}
        steps     八个步骤，附 available / pending / note
        badges    {key: 待办数量}，仅含有待办的项
        progress  {patches, units, data_units, ready, evaluated}
    """
    cached = getattr(g, "_dash_snapshot", None)
    if cached is None:
        cached = _compute()
        g._dash_snapshot = cached
    return cached


def _compute():
    projects = Project.query.count()
    patches = MinePatch.query.all()
    patch_ids = [p.id for p in patches]

    units = MicroUnit.query.filter(
        MicroUnit.patch_id.in_(patch_ids)).all() if patch_ids else []
    unit_by_patch = {}
    for u in units:
        unit_by_patch.setdefault(u.patch_id, []).append(u)
    unit_ids = [u.id for u in units]
    data_unit_ids = set()
    if unit_ids:
        for ind in IndicatorData.query.filter(
                IndicatorData.unit_id.in_(unit_ids)).all():
            if _has_data(ind):
                data_unit_ids.add(ind.unit_id)

    passed_constraint = set()
    if patch_ids:
        for c in ConstraintCheck.query.filter(
                ConstraintCheck.patch_id.in_(patch_ids)).all():
            if c.passed:
                passed_constraint.add(c.patch_id)

    evaluated = set()
    if patch_ids:
        for r in EvaluationResult.query.filter(
                EvaluationResult.patch_id.in_(patch_ids)).all():
            evaluated.add(r.patch_id)

    # ---- 各步骤的待办数量 ----
    pending = {
        "constraint": sum(1 for p in patches if p.id not in passed_constraint),
        "unit": sum(1 for p in patches if not unit_by_patch.get(p.id)),
        "indicator": 0,
        "evaluate": 0,
    }
    ready_patches = 0
    for p in patches:
        us = unit_by_patch.get(p.id, [])
        if us and any(u.id not in data_unit_ids for u in us):
            pending["indicator"] += 1
        pr = wf.patch_progress(p.id)
        if pr["ready"]:
            ready_patches += 1
            if p.id not in evaluated:
                pending["evaluate"] += 1

    # ---- 步骤可用性：前置数据不具备时置灰 ----
    avail = {
        "project": True,
        "standard": True,
        "constraint": bool(patches),
        "unit": bool(patches),
        "ahp": True,
        "indicator": bool(units),
        "evaluate": ready_patches > 0,
        "report": bool(evaluated),
    }
    notes = {
        "constraint": "需先建立矿山图斑",
        "unit": "需先建立矿山图斑",
        "indicator": "需先划分微地质单元",
        "evaluate": "需前置步骤齐备的图斑",
        "report": "需先执行适宜性评价",
    }

    steps = []
    for s in STEPS:
        steps.append(dict(
            s,
            available=avail[s["key"]],
            pending=pending.get(s["key"], 0),
            note=None if avail[s["key"]] else notes.get(s["key"], ""),
        ))

    unit_types = len({u.unit_type for u in units})
    stats = {
        "projects": projects,
        "patches": len(patches),
        "unit_types": unit_types,
        "standards": Standard.query.count(),
    }
    return {
        "stats": stats,
        "steps": steps,
        "badges": {k: v for k, v in pending.items() if v},
        "progress": {
            "patches": len(patches),
            "units": len(units),
            "data_units": len(data_unit_ids),
            "ready": ready_patches,
            "evaluated": len(evaluated),
        },
    }


def nav_badges():
    """侧边栏待办角标：{入口地址前缀: 数量}，只含有待办的项。"""
    snap = snapshot()
    return {
        "/constraint/": snap["badges"].get("constraint", 0),
        "/unit/": snap["badges"].get("unit", 0),
        "/indicator/": snap["badges"].get("indicator", 0),
        "/evaluate/": snap["badges"].get("evaluate", 0),
    }
