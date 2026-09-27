# -*- coding: utf-8 -*-
"""标准化参数与必填项门禁自检。

两件事：
1. 界面上能改的东西必须**真的参与计算** —— 图斑的参照生态系统基准、
   指标定义里的理想取值、指标启用的单元类型。以前这三处改了没效果，
   报告还会把基准印出来，等于同一份报告两个口径。
2. 数据不齐不能出结论 —— 只填一个「坡度」曾能跑出 F=0.69「基本适宜」，
   而缺的项会被剔除、权重摊给其余指标，方向还偏乐观。

全部在副本库上跑，原库不动。
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
from app.models import (db, Project, MinePatch, MicroUnit, IndicatorData,
                        ReferenceEcosystem, Indicator)
from app.services import evaluation_service as ev
from app.services import unit_config as uc
from app.services import workflow as wf
from sqlalchemy import text

LINE = "=" * 72
_fails = []
COPY = os.path.join(os.environ.get("TEMP", ROOT), "dsh_unitcfg_check.db")
shutil.copy2(os.path.join(ROOT, "app", "app.db"), COPY)


def ok(flag, label, extra=""):
    print("  %s %-50s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


class TestConfig(Config):
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + COPY
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(TestConfig)

BASE_DATA = {
    "soil_ratio": 0.34, "thickness": 10.0, "ph": 9.24, "organic_matter": 4.89,
    "heavy_metals": {"Hg": 0.05, "As": 5.17, "Ni": 12.6, "Cu": 11.7,
                     "Cd": 0.04, "Pb": 6.5},
    "coverage": 87.92, "shannon": 0.6, "slope": 28.75, "aspect": "阳坡",
}
FULL = dict(BASE_DATA, slope=20.0, aspect="阴坡")

with app.app_context():
    # 造一个自检图斑，包含碎石边坡与岩质边坡各一个单元
    p = Project(name="参数自检", code="CFG-CHK")
    db.session.add(p)
    db.session.flush()
    m = MinePatch(project_id=p.id, name="参数自检图斑")
    db.session.add(m)
    db.session.flush()
    u1 = MicroUnit(patch_id=m.id, unit_type="碎石边坡", area=1.0, ratio=1.0)
    u2 = MicroUnit(patch_id=m.id, unit_type="岩质边坡", area=0.0, ratio=0.0)
    db.session.add_all([u1, u2])
    db.session.flush()
    db.session.add(ReferenceEcosystem(patch_id=m.id, coverage_benchmark=75.0,
                                      shannon_benchmark=0.7))
    d1 = IndicatorData(unit_id=u1.id, **{k: FULL[k] for k in
                                         ("soil_ratio", "thickness", "ph",
                                          "organic_matter", "coverage",
                                          "shannon", "slope", "aspect")})
    d1.heavy_metals = None      # 全部未检测
    d2 = IndicatorData(unit_id=u2.id, coverage=60.0, shannon=0.5, slope=20.0,
                       aspect="阴坡")
    db.session.add_all([d1, d2])
    db.session.commit()
    PID, MID, U1, U2 = p.id, m.id, u1.id, u2.id
    unit = {u["unit_type"]: u for u in
            [{"unit_type": "碎石边坡", "data": FULL, "ratio": 1.0}]}

print(LINE)
print("一、界面上的参数真的参与计算")
print(LINE)
with app.app_context():
    base = ev.score_unit("碎石边坡", FULL)
    s = uc.for_patch(MID)
    same = ev.score_unit("碎石边坡", FULL, settings=s)

    print("  基准（常量口径）F′ = %.6f" % base["unit_score"])

    # 1) 参照生态系统基准：覆盖度取 40（低于两个基准，不会饱和），
    #    基准 75 → 40/75；基准 50 → 40/50，得分应当变大
    ref = ReferenceEcosystem.query.filter_by(patch_id=MID).first()
    low = dict(FULL, coverage=40.0)
    before1 = ev.score_unit("碎石边坡", low)["unit_score"]
    ref.coverage_benchmark = 50.0
    db.session.commit()
    s2 = uc.for_patch(MID)
    after = ev.score_unit("碎石边坡", low, settings=s2)["unit_score"]
    ok(abs(after - before1) > 1e-6,
       "改覆盖度基准后单元得分随之变化",
       "%.6f → %.6f" % (before1, after))

    # 2) 指标理想取值：图斑的参照生态系统没配这一项时，用指标定义里的理想值。
    #    （图斑配了就以图斑为准 —— 上一条已证明，这里先把图斑的值清掉）
    ref.coverage_benchmark = None
    db.session.commit()
    ind = Indicator.query.filter_by(code="coverage").first()
    old_ideal = ind.ideal_value
    s3a = uc.for_patch(MID)
    score_a = ev.score_unit("碎石边坡", low, settings=s3a)["unit_score"]
    ind.ideal_value = "100"
    db.session.commit()
    s3 = uc.for_patch(MID)
    score_b = ev.score_unit("碎石边坡", low, settings=s3)["unit_score"]
    ok(abs(score_b - score_a) > 1e-6,
       "图斑未配基准时，指标理想取值生效",
       "理想 %s → 100：%.6f → %.6f" % (old_ideal, score_a, score_b))

    # 3) 启用单元：把「土壤指标」在碎石边坡下撤掉
    soil = Indicator.query.filter_by(code="soil").first()
    old_units = soil.enabled_units
    soil.enabled_units = "平台"
    db.session.commit()
    s4 = uc.for_patch(MID)
    from app.services import standardization as std
    groups = std.standardize_unit("碎石边坡", FULL, settings=s4)
    ok("土壤指标" not in groups, "撤掉某单元的启用指标后该组不再计算",
       "实际分组：%s" % list(groups))
    prev = ev.score_unit("碎石边坡", FULL, settings=s3)["unit_score"]
    now = ev.score_unit("碎石边坡", FULL, settings=s4)["unit_score"]
    ok(abs(now - prev) > 1e-6, "该变化同样体现在得分上",
       "%.6f → %.6f" % (prev, now))

    # 还原
    soil.enabled_units = old_units
    ind.ideal_value = old_ideal
    ref.coverage_benchmark = 75.0
    db.session.commit()

print()
print(LINE)
print("二、默认配置下结果与代码常量口径完全一致")
print(LINE)
with app.app_context():
    s = uc.for_patch(MID)
    a = ev.score_mine([{"unit_type": "碎石边坡", "ratio": 1.0, "data": FULL}])
    b = ev.score_mine([{"unit_type": "碎石边坡", "ratio": 1.0, "data": FULL}],
                      None, s)
    ok(abs(a["final_score"] - b["final_score"]) < 1e-12,
       "库内为默认值时两种口径结果相同",
       "%.6f vs %.6f" % (a["final_score"], b["final_score"]))

print()
print(LINE)
print("三、必填项没填齐就不放行")
print(LINE)
with app.app_context():
    # 碎石边坡的指标数据先填全：数据这一步不该拦
    prog = wf.patch_progress(MID)
    data_block = [b for b in prog["blocking"] if b["step"] == "data"]
    ok(not data_block, "数据齐全时数据这一步不拦",
       "；".join(b["label"] for b in prog["blocking"]) or "无拦截")

    # 把「土石比、pH、有机质」清空，只留覆盖度/Shannon/坡度/坡向：
    # 以前这种状态会被判成「数据已录入完整」并照常出分
    d1 = IndicatorData.query.filter_by(unit_id=U1).first()
    saved = (d1.soil_ratio, d1.ph, d1.organic_matter)
    d1.soil_ratio = d1.ph = d1.organic_matter = None
    db.session.commit()

    prog2 = wf.patch_progress(MID)
    blocked = [b for b in prog2["blocking"] if b["step"] == "data"]
    ok(bool(blocked), "缺必填项时数据这一步会拦下来",
       blocked[0]["reason"][:60] if blocked else "未拦")
    ok(not prog2["ready"], "整体判定为不可执行评价")
    names = blocked[0]["reason"] if blocked else ""
    ok(all(k in names for k in ("土石比", "pH", "有机质")),
       "拦截原因里逐项列出缺什么", names[:70])

    # 只有重金属留空不算缺（论文注记允许未检测）
    d1.soil_ratio, d1.ph, d1.organic_matter = saved
    db.session.commit()
    prog3 = wf.patch_progress(MID)
    ok(not [b for b in prog3["blocking"] if b["step"] == "data"],
       "重金属未检测不算缺项（按论文注记）")

print()
print(LINE)
print("四、未检测项如实标注")
print(LINE)
with app.app_context():
    und = wf.undetected_metals(MID)
    by_unit = dict(und)
    ok("碎石边坡" in by_unit and len(by_unit["碎石边坡"]) == 8,
       "碎石边坡重金属全未检测 → 全部列出",
       "、".join(by_unit.get("碎石边坡", [])))
    ok("岩质边坡" not in by_unit,
       "岩质边坡不评价土壤 → 不列未检测重金属（避免噪音）")

print()
print(LINE)
print("五、清理现场")
print(LINE)
with app.app_context():
    for row in Project.query.filter_by(code="CFG-CHK").all():
        for mp in row.patches.all():
            db.session.execute(text("DELETE FROM indicator_data WHERE unit_id IN "
                                    "(SELECT id FROM micro_units WHERE patch_id=:i)"),
                               {"i": mp.id})
            db.session.execute(text("DELETE FROM reference_ecosystems WHERE patch_id=:i"),
                               {"i": mp.id})
            db.session.delete(mp)
        db.session.delete(row)
    db.session.commit()
    left = Project.query.filter_by(code="CFG-CHK").count()
    print("  自检项目残留：%d 个" % left)
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
print("标准化参数与门禁自检全部通过 √")
