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
