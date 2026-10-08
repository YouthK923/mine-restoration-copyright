# -*- coding: utf-8 -*-
"""级联清理：删图斑、删项目时，把挂在它下面的数据一并清掉。

为什么单独抽出来：`Project.patches` 与 `MinePatch.units` 上有 ORM 级联，
但图斑下面的**指标数据、限制性判定、评价结果、得分明细、参照生态系统**
都没有级联关系。原先只有「删除图斑」那条路径里手写了清理，
于是「删除项目」会留下一批孤儿行——自检实测：删一个项目后，
上面五张表各残留 1 行（项目与图斑本身都删掉了，数据却还在库里）。

两条删除路径都调用这里，才不会漏。
"""
from app.models import (db, MinePatch, MicroUnit, IndicatorData,
                        EvaluationResult, ScoreDetail, ConstraintCheck,
                        ReferenceEcosystem)
from sqlalchemy import text

# 孤儿判定：子表的某个外键指向了已经不存在的父记录。
# (表名, 孤儿条件, 说明)
# 这套规则同时被三处使用：工具/清理孤儿数据.py（人工清理）、
# 演示数据重建（seed_demo）、最终验收（verify_all 跑完自检后核对）。
ORPHAN_RULES = [
    ("indicator_data", "unit_id NOT IN (SELECT id FROM micro_units)",
     "指标数据挂在已删除的微地质单元下"),
    ("constraint_checks", "patch_id NOT IN (SELECT id FROM mine_patches)",
     "限制性判定挂在已删除的图斑下"),
    ("reference_ecosystems", "patch_id NOT IN (SELECT id FROM mine_patches)",
     "参照生态系统挂在已删除的图斑下"),
    ("evaluation_results", "patch_id NOT IN (SELECT id FROM mine_patches)",
     "评价结果挂在已删除的图斑下"),
    ("score_details", "result_id NOT IN (SELECT id FROM evaluation_results)",
     "得分明细挂在已删除的评价结果下"),
    ("micro_units", "patch_id NOT IN (SELECT id FROM mine_patches)",
     "微地质单元挂在已删除的图斑下"),
    ("standard_rules", "standard_id NOT IN (SELECT id FROM standards)",
     "标准规则挂在已删除的标准下"),
    ("expert_matrices", "scheme_id NOT IN (SELECT id FROM weight_schemes)",
     "判断矩阵挂在已删除的权重方案下"),
    ("weight_items", "scheme_id NOT IN (SELECT id FROM weight_schemes)",
     "权重项挂在已删除的权重方案下"),
]


def purge_orphans(apply=False):
    """统计（并可选删除）库里残留的孤儿行。

    为什么需要：删图斑、删项目如果绕过 delete_patch_children，
    图斑下面那几张表就会留下孤儿；自检夹具若被中断也会留下。
    返回 [(表名, 条数, 说明)]，调用方据此打印或断言。
    """
    report = []
    for table, cond, note in ORPHAN_RULES:
        try:
            n = db.session.execute(
                text("SELECT COUNT(*) FROM %s WHERE %s" % (table, cond))).scalar()
        except Exception:                      # 表还不存在（旧库）时跳过
            db.session.rollback()
            continue
        report.append((table, n, note))
        if apply and n:
            db.session.execute(text("DELETE FROM %s WHERE %s" % (table, cond)))
    if apply:
        db.session.commit()
    return report


def delete_patch_children(patch_id):
    """清掉挂在某个图斑下的全部附属数据（不含图斑本身）。

    返回各表清理条数，便于调用方打印或断言。
    """
    counts = {}
    unit_ids = [u.id for u in MicroUnit.query.filter_by(patch_id=patch_id).all()]
    if unit_ids:
        counts["indicator_data"] = IndicatorData.query.filter(
            IndicatorData.unit_id.in_(unit_ids)).delete(synchronize_session=False)

    result_ids = [r.id for r in
                  EvaluationResult.query.filter_by(patch_id=patch_id).all()]
    if result_ids:
        counts["score_details"] = ScoreDetail.query.filter(
            ScoreDetail.result_id.in_(result_ids)).delete(synchronize_session=False)

    counts["evaluation_results"] = EvaluationResult.query.filter_by(
        patch_id=patch_id).delete(synchronize_session=False)
    counts["constraint_checks"] = ConstraintCheck.query.filter_by(
        patch_id=patch_id).delete(synchronize_session=False)
    counts["micro_units"] = MicroUnit.query.filter_by(
        patch_id=patch_id).delete(synchronize_session=False)
    counts["reference_ecosystems"] = ReferenceEcosystem.query.filter_by(
        patch_id=patch_id).delete(synchronize_session=False)
    return counts


def delete_patch(patch_id):
    """删除一个图斑及其全部附属数据。图斑不存在时返回 (None, {})。"""
    patch = db.session.get(MinePatch, patch_id)
    if patch is None:
        return None, {}
    counts = delete_patch_children(patch_id)
    db.session.delete(patch)
    db.session.commit()
    return patch, counts


def delete_project(project):
    """删除一个项目：先清掉每个图斑的附属数据，再删项目本身。

    项目下的图斑由 `Project.patches` 的 ORM 级联删除，但图斑下面那五张表
    必须先手工清，否则会留孤儿。
    """
    cleaned = 0
    for patch in project.patches.all():
        counts = delete_patch_children(patch.id)
        cleaned += sum(counts.values())
    name = project.name
    db.session.delete(project)
    db.session.commit()
    return name, cleaned
