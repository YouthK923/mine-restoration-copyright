# -*- coding: utf-8 -*-
"""轻量结构迁移。

SQLite 下 `db.create_all()` 只建缺失的表，不会给已有表补列。
本模块在启动时检查目标列是否存在，缺失则 ALTER TABLE 补上，
使旧数据库无需重建即可用上新字段。
"""
from sqlalchemy import text

# (表名, 列名, 列定义)
REQUIRED_COLUMNS = [
    # 遥感影像挂接
    ("mine_patches", "image_path", "VARCHAR(256)"),
    ("mine_patches", "image_note", "VARCHAR(256)"),
    ("mine_patches", "image_uploaded_at", "DATETIME"),
    # 指标维护
    ("indicators", "enabled_units", "VARCHAR(128)"),
    ("indicators", "description", "TEXT"),
    # 多专家矩阵
    ("expert_matrices", "unit_type", "VARCHAR(32)"),
    ("expert_matrices", "l1_name", "VARCHAR(64)"),
    ("expert_matrices", "specialty", "VARCHAR(64)"),
    ("expert_matrices", "cr", "FLOAT"),
    # 用户个人资料（账户页）
    ("users", "display_name", "VARCHAR(64)"),
    ("users", "email", "VARCHAR(128)"),
    ("users", "phone", "VARCHAR(32)"),
    ("users", "gender", "VARCHAR(8)"),
    ("users", "avatar", "VARCHAR(256)"),
    # 评价结果的可追溯信息：计算参数快照与计算人
    ("evaluation_results", "params_json", "TEXT"),
    ("evaluation_results", "created_by", "INTEGER"),
]

# 职务体系由「管理员 / 评价员 / 查看者」三种收敛为「管理员 / 操作员」两种，
# 旧数据里的后两种统一归为操作员。
ROLE_MIGRATION = {"evaluator": "operator", "viewer": "operator"}

# 已经废弃的列（表名, 列名）：新库不会再建，旧库启动时删掉
RETIRED_COLUMNS = [
    # 早期版本的限制性判定字段，现行版本已不再使用
    ("constraint_checks", "farmland_pass"),
]


def _add_columns(db):
    added = []
    with db.engine.connect() as conn:
        for table, column, ddl in REQUIRED_COLUMNS:
            rows = conn.execute(text("PRAGMA table_info(%s)" % table)).fetchall()
            if not rows:
                continue                      # 表还不存在，create_all 会建
            existing = {r[1] for r in rows}
            if column in existing:
                continue
            conn.execute(text(
                "ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl)))
            conn.commit()
            added.append("%s.%s" % (table, column))
    return added


def _migrate_roles(db):
    """把旧角色名统一为新的两种，返回改动的行数。"""
    changed = 0
    with db.engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        if not rows:
            return 0
        for old, new in ROLE_MIGRATION.items():
            r = conn.execute(text("UPDATE users SET role = :new "
                                  "WHERE role = :old"),
                             {"new": new, "old": old})
            changed += r.rowcount or 0
        conn.commit()
    return changed


def _drop_retired_columns(db):
    """删掉已经废弃的列。

    RETIRED_COLUMNS 里登记的字段都是早期版本用过、现行版本不再使用的：
    新库由 create_all 直接按新模型建表，不会再有这些列；
    旧库在这里删一次，避免源码与库结构长期对不上。
    SQLite 3.35 以下不支持 DROP COLUMN，失败就跳过，不影响启动。
    """
    dropped = []
    for table, column in RETIRED_COLUMNS:
        try:
            with db.engine.connect() as conn:
                rows = conn.execute(text("PRAGMA table_info(%s)" % table)).fetchall()
                if not rows or column not in {r[1] for r in rows}:
                    continue
                conn.execute(text("ALTER TABLE %s DROP COLUMN %s" % (table, column)))
                conn.commit()
                dropped.append("%s.%s" % (table, column))
        except Exception:                          # 老版本 SQLite 不支持就跳过
            continue
    return dropped


def ensure_schema(db):
    """为已有表补齐缺失列、删掉废弃列，并做必要的数据迁移。返回变更清单。"""
    try:
        changed = _add_columns(db)
        changed += _drop_retired_columns(db)
        n = _migrate_roles(db)
        if n:
            changed.append("用户角色归一为管理员/操作员 %d 条" % n)
        return changed
    except Exception as e:                        # 迁移失败不应阻断启动
        print("[schema] 结构检查跳过：%s" % e)
        return []
