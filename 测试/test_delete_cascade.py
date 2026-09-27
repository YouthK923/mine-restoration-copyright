# -*- coding: utf-8 -*-
"""删除连带清理自检：删项目 / 删图斑以后，图斑下面的数据不能留在库里。

背景：`Project.patches` 与 `MinePatch.units` 上有 ORM 级联，但指标数据、
限制性判定、评价结果、得分明细、参照生态系统没有级联。原先只有「删除图斑」
那条路径手写了清理，于是「删除项目」会留下五张表的孤儿行（实测各留 1 行）。
本脚本把两条删除路径都固定下来，防止再退化。
"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import (db, User, Project, MinePatch, MicroUnit, IndicatorData,
                        ConstraintCheck, ReferenceEcosystem, EvaluationResult,
                        ScoreDetail)
from sqlalchemy import text

LINE = "=" * 72
_fails = []
COPY = os.path.join(os.environ.get("TEMP", ROOT), "dsh_cascade_check.db")


def ok(flag, label, extra=""):
    print("  %s %-46s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


class TestConfig(Config):
    SECRET_KEY = "test"
    # 用副本库：本脚本要删数据，不能动 app/app.db
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + COPY
    WTF_CSRF_ENABLED = False
    TESTING = True


shutil.copy2(os.path.join(ROOT, "app", "app.db"), COPY)
app = create_app(TestConfig)

with app.app_context():
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        raise SystemExit("库里没有 admin 账号，无法自检")

client = app.test_client()
with client.session_transaction() as s:
    s["_user_id"] = str(admin.id)
    s["_fresh"] = True
if not admin.is_admin:
    raise SystemExit("admin 不是管理员，无法自检")


def build(tag):
    """造一套「项目 → 图斑 → 单元 → 各类子表」数据，返回各 id。"""
    p = Project(name="连带清理自检-%s" % tag, code="CASCADE-%s" % tag)
    db.session.add(p)
    db.session.flush()
    m = MinePatch(project_id=p.id, name="自检图斑-%s" % tag)
    db.session.add(m)
    db.session.flush()
    u = MicroUnit(patch_id=m.id, unit_type="平台", area=1.0, ratio=1.0)
    db.session.add(u)
    db.session.flush()
    db.session.add(IndicatorData(unit_id=u.id, coverage=60.0))
    db.session.add(ConstraintCheck(patch_id=m.id, passed=True, reason="自检"))
    db.session.add(ReferenceEcosystem(patch_id=m.id))
    r = EvaluationResult(patch_id=m.id, final_score=0.5, grade="基本适宜")
    db.session.add(r)
    db.session.flush()
    db.session.add(ScoreDetail(result_id=r.id, l1_name="植被指标",
                               l2_name="植被覆盖度", raw_value="60",
                               std_value=1.0, weight=1.0, contribution=1.0))
    db.session.commit()
    return {"project": p.id, "patch": m.id, "unit": u.id, "result": r.id}


def leftovers(ids):
    def q(sql, **kw):
        return db.session.execute(text(sql), kw).scalar()
    return {
        "项目": q("SELECT COUNT(*) FROM projects WHERE id=:i", i=ids["project"]),
        "图斑": q("SELECT COUNT(*) FROM mine_patches WHERE id=:i", i=ids["patch"]),
        "微地质单元": q("SELECT COUNT(*) FROM micro_units WHERE id=:i", i=ids["unit"]),
        "指标数据": q("SELECT COUNT(*) FROM indicator_data WHERE unit_id=:i",
                  i=ids["unit"]),
        "限制性判定": q("SELECT COUNT(*) FROM constraint_checks WHERE patch_id=:i",
                   i=ids["patch"]),
        "参照生态系统": q("SELECT COUNT(*) FROM reference_ecosystems WHERE patch_id=:i",
                    i=ids["patch"]),
        "评价结果": q("SELECT COUNT(*) FROM evaluation_results WHERE id=:i",
                  i=ids["result"]),
        "得分明细": q("SELECT COUNT(*) FROM score_details WHERE result_id=:i",
                  i=ids["result"]),
    }


print(LINE)
print("一、删除项目：图斑下面的数据必须一起走")
print(LINE)
with app.app_context():
    ids = build("proj")
    r = client.post("/project/%d/delete" % ids["project"], follow_redirects=True)
    ok(r.status_code == 200, "删除项目请求被受理", "HTTP %d" % r.status_code)
    left = leftovers(ids)
    for name, n in left.items():
        ok(n == 0, "删项目后「%s」不留孤儿" % name, "残留 %d 行" % n)

print()
print(LINE)
print("二、删除图斑：同样不能留孤儿")
print(LINE)
with app.app_context():
    ids = build("patch")
    r = client.post("/project/patch/%d/delete" % ids["patch"],
                    follow_redirects=True)
    ok(r.status_code == 200, "删除图斑请求被受理", "HTTP %d" % r.status_code)
    left = leftovers(ids)
    for name, n in left.items():
        if name == "项目":
            continue          # 只删图斑，项目应保留
        ok(n == 0, "删图斑后「%s」不留孤儿" % name, "残留 %d 行" % n)
    ok(left["项目"] == 1, "所属项目本身保留", "残留 %d 行" % left["项目"])

print()
print(LINE)
print("三、清理现场")
print(LINE)
with app.app_context():
    left = Project.query.filter(Project.code.like("CASCADE-%")).all()
    for p in left:
        for m in p.patches.all():
            db.session.delete(m)
        db.session.delete(p)
    db.session.commit()
    rest = Project.query.filter(Project.code.like("CASCADE-%")).count()
    print("  自检项目残留：%d 个" % rest)
    # 先放开连接，否则 Windows 上删不掉副本文件
    db.session.remove()
    db.engine.dispose()

try:
    os.remove(COPY)
    print("  副本库已删除")
except OSError as e:
    print("  副本库暂时删不掉（%s），下次运行会覆盖" % e)

print()
if _fails:
    print("未通过：%s" % "、".join(_fails))
    sys.exit(1)
print("删除连带清理自检全部通过 √")
