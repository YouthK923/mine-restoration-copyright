# -*- coding: utf-8 -*-
"""清理库里残留的孤儿数据。

背景：早期「删除项目」只清了图斑与微地质单元，图斑下面的指标数据、
限制性判定、评价结果、得分明细、参照生态系统都会留下孤儿行。
删除路径已在 app/services/cleanup.py 里修好，这个脚本用来清掉**历史遗留**的那批。

默认只统计不删除；确认无误后加 --apply 真正执行。

用法：
    python 工具/清理孤儿数据.py            # 只看有多少
    python 工具/清理孤儿数据.py --apply    # 真删
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.models import db
from sqlalchemy import text

APPLY = "--apply" in sys.argv

# 表名 → (孤儿判定 SQL, 说明)
ORPHANS = [
    ("indicator_data",
     "unit_id NOT IN (SELECT id FROM micro_units)",
     "指标数据挂在已删除的微地质单元下"),
    ("constraint_checks",
     "patch_id NOT IN (SELECT id FROM mine_patches)",
     "限制性判定挂在已删除的图斑下"),
    ("reference_ecosystems",
     "patch_id NOT IN (SELECT id FROM mine_patches)",
     "参照生态系统挂在已删除的图斑下"),
    ("evaluation_results",
     "patch_id NOT IN (SELECT id FROM mine_patches)",
     "评价结果挂在已删除的图斑下"),
    ("score_details",
     "result_id NOT IN (SELECT id FROM evaluation_results)",
     "得分明细挂在已删除的评价结果下"),
    ("micro_units",
     "patch_id NOT IN (SELECT id FROM mine_patches)",
     "微地质单元挂在已删除的图斑下"),
    ("standard_rules",
     "standard_id NOT IN (SELECT id FROM standards)",
     "标准规则挂在已删除的标准下"),
    ("expert_matrices",
     "scheme_id NOT IN (SELECT id FROM weight_schemes)",
     "判断矩阵挂在已删除的权重方案下"),
    ("weight_items",
     "scheme_id NOT IN (SELECT id FROM weight_schemes)",
     "权重项挂在已删除的权重方案下"),
]


def main():
    app = create_app()
    with app.app_context():
        print("=" * 74)
        print("  孤儿数据检查%s" % ("（--apply：将真正删除）" if APPLY else "（只统计）"))
        print("=" * 74)
        total = 0
        for table, cond, note in ORPHANS:
            try:
                n = db.session.execute(
                    text("SELECT COUNT(*) FROM %s WHERE %s" % (table, cond))
                ).scalar()
            except Exception as e:
                print("  [跳过] %-22s %s" % (table, e))
                continue
            total += n
            mark = "0" if n == 0 else "**%d**" % n
            print("  %-22s %-6s %s" % (table, mark, note))
            if APPLY and n:
                db.session.execute(
                    text("DELETE FROM %s WHERE %s" % (table, cond)))
        if APPLY:
            db.session.commit()
            print("\n  已删除上述孤儿数据。")
        else:
            print("\n  合计 %d 条。确认后加 --apply 执行清理。" % total)

        # 操作日志的用户已被删除属于正常（日志要留痕），只提示不删
        n = db.session.execute(text(
            "SELECT COUNT(*) FROM operation_logs WHERE user_id IS NOT NULL "
            "AND user_id NOT IN (SELECT id FROM users)")).scalar()
        print("  提示：操作日志中有 %d 条的操作人账号已被删除。" % n)
        print("        日志需要留痕，界面会把操作人显示为「—」，不清理。")


if __name__ == "__main__":
    main()
