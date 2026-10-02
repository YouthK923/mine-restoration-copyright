# -*- coding: utf-8 -*-
"""标准结论对照自检：判定映射 + 页面渲染 + 数据只读。

对照功能只读取系统已有的评价数据，本身不写库；为了验证「省内文件能对上」这条
分支，测试会临时建一条河北的标准（含规则），跑完一定删掉 —— 夹具若残留在库里，
会随标准列表一起被拍进软著截图。
"""
import os
import sys
import types

sys.stdout.reconfigure(encoding="utf-8")   # 被 verify_all 以管道方式调用时避免编码报错

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app                                     # noqa: E402
from app.models import (db, Standard, StandardRule, MinePatch,   # noqa: E402
                        EvaluationResult)
from app.services import standard_check as sc                   # noqa: E402

LINE = "=" * 66
_fails = []


def ok(flag, label, extra=""):
    print("  %s %-46s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


# 与真实配置共用同一个 app.db，但关闭 CSRF 便于测试客户端
class TestConfig:
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(ROOT, "app", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(TestConfig)
client = app.test_client()
client.post("/login", data={"username": "admin", "password": "admin123"})

FIXTURE_NAME = "自检夹具标准（河北）"


def demo_patch():
    """演示图斑（玉田县案例）。

    不能图省事用 MinePatch.query.first() —— 在整套自检里跑时，前面几套
    （test_workflow / test_robustness 等）可能留下自检夹具图斑，第一个
    未必是演示图斑，断言就会随执行顺序飘。
    """
    return (MinePatch.query.filter(MinePatch.name.contains("玉田县")).first()
            or MinePatch.query.first())


def purge_fixture():
    """删掉夹具标准及其规则。"""
    with app.app_context():
        for s in Standard.query.filter_by(name=FIXTURE_NAME).all():
            StandardRule.query.filter_by(standard_id=s.id).delete()
            db.session.delete(s)
        db.session.commit()


purge_fixture()

print(LINE)
print("测试 1  比较符与数值解析")
print(LINE)
ok(sc._cmp(60, ">=", "50") is True, "60 >= 50 判为真")
ok(sc._cmp(40, ">=", "50") is False, "40 >= 50 判为假")
ok(sc._cmp(8, "<", "20") is True, "8 < 20 判为真")
ok(sc._cmp(80, ">", "75") is True, "80 > 75 判为真")
ok(sc._cmp(5, "==", "5") is True, "5 == 5 判为真")
ok(sc._cmp(5, "==", "6") is False, "5 == 6 判为假")
ok(sc._cmp(60, ">=", "阈值") is None, "阈值不是数字 → 无法判断（None）")
ok(sc._cmp(None, ">=", "50") is None, "取值缺失 → 无法判断（None）")

print()
print(LINE)
print("测试 2  判定映射（不依赖数据库）")
print(LINE)
constraint_ok = types.SimpleNamespace(pollution_pass=True, geo_pass=True)
constraint_bad = types.SimpleNamespace(pollution_pass=False, geo_pass=False)
patch = types.SimpleNamespace(responsible_entity_missing=True)
ctx = {"coverage": 62.5, "coverage_min": 48.0, "benchmark": 75.0,
       "has_reference": True, "constraint": constraint_ok, "patch": patch,
       "grade": "适宜", "score": 0.7156, "result": object()}

ok(sc._judge("植被覆盖度", ">=", "50", ctx)[0] == sc.OK, "覆盖度 62.5 ≥ 50 → 符合")
ok(sc._judge("植被覆盖度", ">", "75", ctx)[0] == sc.BAD, "覆盖度 62.5 未 > 75 → 不符合")
ok("62.50%" in sc._judge("植被覆盖度", ">=", "50", ctx)[1], "依据里写明实测覆盖度")
ok(sc._judge("植被覆盖度趋势", "==", "稳定", ctx)[0] == sc.MANUAL,
   "覆盖度趋势（需时间序列）→ 待人工判断")
ok(sc._judge("无地质灾害", "==", "是", ctx)[0] == sc.OK, "无地质灾害（判定通过）→ 符合")
ok(sc._judge("无地质灾害", "==", "是",
             dict(ctx, constraint=constraint_bad))[0] == sc.BAD,
   "存在地质灾害 → 不符合")
ok(sc._judge("地质灾害发育程度", "<=", "弱发育", ctx)[0] == sc.MANUAL,
   "发育程度分级（系统只记有无）→ 待人工判断")
ok(sc._judge("无水土污染", "==", "是", ctx)[0] == sc.OK, "无水土污染（判定通过）→ 符合")
ok(sc._judge("无水土污染", "==", "是",
             dict(ctx, constraint=constraint_bad))[0] == sc.BAD,
   "存在水土污染 → 不符合")
ok(sc._judge("责任主体", "==", "政府", ctx)[0] == sc.OK, "责任主体缺失（政府兜底）→ 符合")
ok(sc._judge("与参照系差距", "<", "20", ctx)[0] == sc.OK,
   "与参照系差距 12.5 个百分点 < 20 → 符合")
ok(sc._judge("与参照系差距", "<", "5", ctx)[0] == sc.BAD,
   "与参照系差距 12.5 个百分点 未 < 5 → 不符合")
ok(sc._judge("自然恢复适宜性分级", "==", "是", ctx)[0] == sc.OK,
   "已给出适宜性等级 → 符合")
ok(sc._judge("自然恢复适宜性指数", ">=", "阈值", ctx)[0] == sc.MANUAL,
   "文件未给具体阈值 → 待人工判断")
ok(sc._judge("自然恢复适宜性分级", "==", "是",
             dict(ctx, grade=None))[0] == sc.MANUAL,
   "尚未执行评价 → 待人工判断")
ok(sc._judge("符合国土空间规划", "==", "是", ctx)[0] == sc.MANUAL,
   "系统内无对应数据的定性要求 → 待人工判断")
ok(sc._judge("地形地貌与周边协调", "==", "是", ctx)[0] == sc.MANUAL,
   "地形地貌协调 → 待人工判断")

print()
print(LINE)
print("测试 3  省份识别与未收录提示")
print(LINE)
with app.app_context():
    demo = demo_patch()
    ok(demo is not None, "库中存在演示图斑")
    ok(sc.province_of(demo.admin_region) is None,
       "库里没有河北的标准时 → 识别为未收录", str(demo.admin_region))
    only = sc.province_of("辽宁省抚顺市")
    ok(only == "辽宁", "辽宁在库中 → 识别为 辽宁", str(only))
    not_covered = sc.compare(demo.id)
    ok(not_covered["covered"] is False, "未收录省份时 covered=False")
    ok("未收录该省份" in not_covered["message"], "给出「未收录该省份」的说明")

print()
print(LINE)
print("测试 4  收录省份后逐条对照（临时夹具）")
print(LINE)
try:
    with app.app_context():
        s = Standard(province="河北", name=FIXTURE_NAME, doc_number="自检-001",
                     category="地方标准", summary="自检夹具")
        db.session.add(s)
        db.session.flush()
        rules = [("植被覆盖度", ">=", "50", "必要条件"),
                 ("无地质灾害", "==", "是", "必要条件"),
                 ("植被覆盖度趋势", "==", "稳定或正增长", "必要条件"),
                 ("地形地貌与周边协调", "==", "是", "必要条件"),
                 ("自然恢复适宜性分级", "==", "是", "充分条件")]
        for item, op, thr, kind in rules:
            db.session.add(StandardRule(standard_id=s.id, item=item,
                                        operator=op, threshold=thr,
                                        condition_type=kind))
        db.session.commit()
        sid = s.id
        demo = demo_patch()
        result = sc.compare(demo.id)
        ok(result["covered"] is True, "收录河北标准后 covered=True")
        ok(len(result["standards"]) == 1, "对照到 1 份文件")
        verdicts = [r["verdict"] for r in result["standards"][0]["rules"]]
        ok(verdicts[0] in (sc.OK, sc.BAD), "覆盖度一条给出明确结论", str(verdicts[0]))
        ok(verdicts[1] == sc.OK, "无地质灾害一条为符合")
        ok(verdicts[2] == sc.MANUAL, "趋势类一条为待人工判断")
        ok(verdicts[3] == sc.MANUAL, "地形协调一条为待人工判断")
        ok(result["necessary"]["共计"] == 4, "必要条件计数正确",
           str(result["necessary"]))
        ok(result["totals"][sc.OK] + result["totals"][sc.BAD]
           + result["totals"][sc.MANUAL] == 5, "三种结论计数之和等于规则数")

        print()
        print(LINE)
        print("测试 5  页面渲染")
        print(LINE)
        r = client.get("/standard/check")
        body = r.get_data(as_text=True)
        ok(r.status_code == 200, "对照入口页 200")
        ok(demo.name in body, "入口页列出演示图斑")
        r2 = client.get("/standard/check/%d" % demo.id)
        body2 = r2.get_data(as_text=True)
        ok(r2.status_code == 200, "对照页 200")
        ok(FIXTURE_NAME in body2, "对照页出现该文件")
        ok("tag--ok" in body2 and "tag--muted" in body2,
           "同时出现「符合」与「待人工判断」两种标签")
        ok("对照结果" in body2 and "依据（系统内的对应数据）" in body2,
           "表格含对照结果与依据两列")
        r3 = client.get("/standard/check/999999")
        ok(r3.status_code == 302, "图斑不存在 → 跳回入口页")
        r4 = client.get("/standard/")
        ok("结论对照" in r4.get_data(as_text=True), "标准库首页有「结论对照」入口")

        print()
        print(LINE)
        print("测试 6  评价结果页也带对照内容块")
        print(LINE)
        rec = EvaluationResult.query.order_by(EvaluationResult.id.desc()).first()
        if rec is None:
            print("  [跳过] 库里还没有评价记录（由 test_web_evaluate.py 生成）")
        else:
            r5 = client.get("/evaluate/result/%d" % rec.id)
            body5 = r5.get_data(as_text=True)
            ok(r5.status_code == 200, "结果页 200")
            ok("与地方标准 / 政策文件的对照" in body5, "结果页含对照小节")
finally:
    purge_fixture()
    with app.app_context():
        left = Standard.query.filter_by(name=FIXTURE_NAME).count()
    ok(left == 0, "夹具标准已清理", "残留 %d 条" % left)

print()
print(LINE)
if _fails:
    print("未通过 %d 项：%s" % (len(_fails), "、".join(_fails)))
    sys.exit(1)
print("标准结论对照自检全部通过 ✓")
print(LINE)
