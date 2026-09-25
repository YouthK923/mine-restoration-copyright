# -*- coding: utf-8 -*-
"""流程门禁自检：前置步骤未完成时，后续模块必须拦得住。

论文 4.1 节确定的评价流程存在先后关系，缺任何一环都不应产出评价结论。
本测试逐个构造「缺前置」的场景，验证系统不会放行。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from app import create_app
from app.models import (db, Project, MinePatch, MicroUnit, IndicatorData,
                        ConstraintCheck, EvaluationResult)
from app.services import workflow as wf

LINE = "=" * 72
BASE = os.path.dirname(os.path.abspath(__file__))


class TestConfig:
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE, "app", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(TestConfig)
c = app.test_client()
c.post("/login", data={"username": "admin", "password": "admin123"})

_fails = []


def ok(flag, label, extra=""):
    print("  %s %-46s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


def new_patch(tag):
    with app.app_context():
        p = Project(name="门禁-" + tag, code="WF-" + tag)
        db.session.add(p); db.session.flush()
        patch = MinePatch(project_id=p.id, name="门禁图斑-" + tag)
        db.session.add(patch); db.session.flush()
        pid = patch.id
        db.session.commit()
    return pid


def add_units(pid):
    with app.app_context():
        db.session.add(MicroUnit(patch_id=pid, unit_type="碎石边坡",
                                 area=1.0, ratio=1.0))
        db.session.commit()


def add_constraint(pid, passed=True):
    with app.app_context():
        db.session.add(ConstraintCheck(
            patch_id=pid, policy_pass=True, location_pass=passed,
            pollution_pass=True, geo_pass=True, farmland_pass=True,
            passed=passed, reason="全部通过" if passed else "未通过：区位约束"))
        db.session.commit()


def add_data(pid):
    with app.app_context():
        u = MicroUnit.query.filter_by(patch_id=pid).first()
        db.session.add(IndicatorData(unit_id=u.id, soil_ratio=0.34, thickness=10,
                                     ph=9.24, organic_matter=4.89, coverage=87.92,
                                     shannon=0.60, slope=28.75, aspect="阳坡"))
        db.session.commit()


def cleanup(pid, tag):
    with app.app_context():
        EvaluationResult.query.filter_by(patch_id=pid).delete()
        ConstraintCheck.query.filter_by(patch_id=pid).delete()
        uids = [u.id for u in MicroUnit.query.filter_by(patch_id=pid)]
        if uids:
            IndicatorData.query.filter(IndicatorData.unit_id.in_(uids)).delete(
                synchronize_session=False)
        MicroUnit.query.filter_by(patch_id=pid).delete()
        m = db.session.get(MinePatch, pid)
        if m:
            db.session.delete(m)
        pr = Project.query.filter_by(name="门禁-" + tag).first()
        if pr:
            db.session.delete(pr)
        db.session.commit()


def results_of(pid):
    with app.app_context():
        return EvaluationResult.query.filter_by(patch_id=pid).count()


def post_eval(pid):
    return c.post("/evaluate/%d" % pid, data={}, follow_redirects=False)


def get_report(pid):
    return c.get("/report/%d" % pid, follow_redirects=False)


# ---------------------------------------------------------------------------
print(LINE)
print("一、前置条件缺失时，评价必须被拦住")
print(LINE)

print()
print("场景 1：连微地质单元都没划分")
pid = new_patch("1")
r = post_eval(pid)
n = results_of(pid)
ok(r.status_code == 302 and n == 0, "未划分单元 → 不产生评价结果",
   "HTTP %d，结果数 %d" % (r.status_code, n))
with app.app_context():
    pr = wf.patch_progress(pid)
ok(not pr["ready"] and pr["blocking"][0]["step"] == "units",
   "拦原因指向「划分微地质单元」")
cleanup(pid, "1")

print()
print("场景 2：有单元，但未做限制性条件判定")
pid = new_patch("2"); add_units(pid); add_data(pid)
r = post_eval(pid)
n = results_of(pid)
ok(r.status_code == 302 and n == 0, "未做限制性判定 → 不产生评价结果",
   "结果数 %d" % n)
with app.app_context():
    pr = wf.patch_progress(pid)
ok(any(b["step"] == "constraint" for b in pr["blocking"]),
   "拦原因指向「执行限制性条件判定」")
cleanup(pid, "2")

print()
print("场景 3：限制性条件判定【未通过】")
pid = new_patch("3"); add_units(pid); add_data(pid); add_constraint(pid, passed=False)
r = post_eval(pid)
n = results_of(pid)
ok(r.status_code == 302 and n == 0, "判定未通过 → 不进入定量评价",
   "结果数 %d" % n)
with app.app_context():
    pr = wf.patch_progress(pid)
ok(not pr["constraint"]["passed"], "流程状态显示判定未通过")
blocked = [b for b in pr["blocking"] if b["step"] == "constraint"]
ok(bool(blocked) and "人工辅助" in blocked[0]["reason"],
   "拦原因说明了按论文应判「人工辅助或生态重建」")
cleanup(pid, "3")

print()
print("场景 4：判定通过，但指标数据全空")
pid = new_patch("4"); add_units(pid); add_constraint(pid, passed=True)
r = post_eval(pid)
n = results_of(pid)
ok(r.status_code == 302 and n == 0, "数据未录入 → 不产生评价结果",
   "结果数 %d" % n)
with app.app_context():
    pr = wf.patch_progress(pid)
ok(any(b["step"] == "data" for b in pr["blocking"]),
   "拦原因指向「录入指标数据」")
ok(pr["data"]["missing"] == ["碎石边坡"],
   "指出具体缺哪个单元的数据", "、".join(pr["data"]["missing"]))
cleanup(pid, "4")

print()
print("场景 5：单元面积占比合计不为 100%")
pid = new_patch("5"); add_constraint(pid, passed=True)
with app.app_context():
    u = MicroUnit(patch_id=pid, unit_type="碎石边坡", area=1.0, ratio=0.5)
    db.session.add(u); db.session.commit()
    db.session.add(IndicatorData(unit_id=u.id, soil_ratio=0.3, thickness=10,
                                 ph=8.0, organic_matter=5.0, coverage=80.0,
                                 shannon=0.6, slope=20.0, aspect="阳坡"))
    db.session.commit()
r = post_eval(pid)
ok(results_of(pid) == 0, "占比不足 100% → 不产生评价结果")
cleanup(pid, "5")

print()
print(LINE)
print("二、前置条件齐备时才放行")
print(LINE)
pid = new_patch("OK"); add_units(pid); add_constraint(pid, passed=True); add_data(pid)
with app.app_context():
    pr = wf.patch_progress(pid)
ok(pr["ready"], "单元 + 判定通过 + 数据齐备 → 判定为可执行")
r = post_eval(pid)
n = results_of(pid)
ok(n == 1, "此时执行评价成功产生结果", "结果数 %d" % n)
print("  重定向到:", r.headers.get("Location"))

print()
print(LINE)
print("三、报告不得先于评价产生")
print(LINE)
pid2 = new_patch("R")   # 什么都不做
r = get_report(pid2)
ok(r.status_code == 302 and "/report/" == (r.headers.get("Location") or ""),
   "前置缺失时 /report/<id> 被退回列表", "HTTP %d" % r.status_code)
for suffix in ("/pdf", "/word"):
    rr = c.get("/report/%d%s" % (pid2, suffix), follow_redirects=False)
    ok(rr.status_code == 302, "导出 %s 同样被拦住" % suffix, "HTTP %d" % rr.status_code)
cleanup(pid2, "R")
cleanup(pid, "OK")

print()
print(LINE)
if _fails:
    print("存在未通过项：")
    for f in _fails:
        print("  -", f)
    sys.exit(1)
print("流程门禁自检全部通过 √")
print(LINE)
