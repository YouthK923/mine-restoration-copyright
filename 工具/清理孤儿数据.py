# -*- coding: utf-8 -*-
"""清理库里残留的孤儿数据。

背景：删图斑、删项目如果绕过 app/services/cleanup.py 的级联清理，
图斑下面的指标数据、限制性判定、评价结果、得分明细、参照生态系统
都会留下孤儿行；自检夹具被中断时也会留下。

默认只统计不删除；确认无误后加 --apply 真正执行。
判定规则集中在 app/services/cleanup.py 的 ORPHAN_RULES，三处共用。

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
from app.services import cleanup
from sqlalchemy import text

APPLY = "--apply" in sys.argv


def main():
    app = create_app()
    with app.app_context():
        print("=" * 74)
        print("  孤儿数据检查%s" % ("（--apply：将真正删除）" if APPLY else "（只统计）"))
        print("=" * 74)
        report = cleanup.purge_orphans(apply=APPLY)
        total = sum(n for _, n, _ in report)
        for table, n, note in report:
            print("  %-22s %-6s %s" % (table, "0" if n == 0 else "**%d**" % n, note))
        if APPLY:
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
