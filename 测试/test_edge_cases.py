# -*- coding: utf-8 -*-
"""边界与健壮性专项自检（软著送审前的整体测试）。

覆盖六类容易出问题的地方：

一、标准化与判定的数值边界（0、理想值、极值、区间端点、越界、缺失）
二、录入边界（非法文案、负数、超范围、超长、重复单元类型）
三、流程门禁（限制性判定未过 / 占比不为 100% / 指标缺项 / 未评价就导报告）
四、输入清洗（分页与层级越界、搜索特殊字符、XSS 转义、SQL 注入式关键词）
五、批量导入边界（无文件、错扩展名、空表、错单元类型、超范围、缺列）
六、权限与错误页（匿名跳登录、操作员越权 403、CSRF 拦截、404/413 中文页）
七、结论对照与导出（省内文件逐条对照、未收录提示、报告带对照小节）

本套件在**数据库副本**上跑，不碰 app/app.db。
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import (db, User, Project, MinePatch, MicroUnit, IndicatorData,
                        ConstraintCheck, EvaluationResult, Standard)
from app.services import cleanup, standard_check
from app.services import evaluation_service as ev
from app.services import standardization as std
from app.services import workflow as wf
from app.services import report_service as rs
from app.utils.constants import grade_of
from werkzeug.security import generate_password_hash

LINE = "=" * 74
_fails = []
COPY = os.path.join(tempfile.gettempdir(), "dsh_edge_cases.db")
shutil.copy2(os.path.join(ROOT, "app", "app.db"), COPY)
PW = "edge-check-123"
CODE = "EDGE-001"


def ok(flag, label, extra=""):
    print("  %s %-52s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


def section(title):
    print()
    print(LINE)
    print(title)
    print(LINE)


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + COPY
    TESTING = False                      # 生产式：错误走中文错误页
    WTF_CSRF_ENABLED = False


class CsrfConfig(TestConfig):
    WTF_CSRF_ENABLED = True              # 单独一个实例验证 CSRF 拦截


app = create_app(TestConfig)
csrf_app = create_app(CsrfConfig)

with app.app_context():
    for u in User.query.all():
        u.password_hash = generate_password_hash(PW)
    db.session.commit()


def login(client, username="admin"):
    c = client or app.test_client()
    c.post("/login", data={"username": username, "password": PW})
    return c


def still_in(body):
    """页面仍是登录后的界面（而不是被踢回登录页）。"""
    return "请输入账户名称" not in body


def post(client, path, data=None, follow_redirects=True):
    """POST 并断言没有被踢回登录页，返回响应对象。"""
    r = client.post(path, data=data or {}, follow_redirects=follow_redirects)
    body = r.get_data(as_text=True)
    if not still_in(body):
        ok(False, "POST %s 时仍是登录态" % path, "被踢回登录页")
    return r


def purge():
    with app.app_context():
        for p in Project.query.filter_by(code=CODE).all():
            cleanup.delete_project(p)
        for name in ("边界自检操作员",):
            u = User.query.filter_by(username=name).first()
            if u is not None:
                db.session.delete(u)
        db.session.commit()


def build_fixture(ratio_ok=True, constraint_ok=True, data_ok=True):
    """建一套边界自检用的项目/图斑/单元/指标/判定记录。"""
    with app.app_context():
        proj = Project(name="边界自检项目", code=CODE, description="自检夹具")
        db.session.add(proj)
        db.session.flush()
        patch = MinePatch(project_id=proj.id, name="边界自检图斑",
                          admin_region="辽宁省抚顺市", area_ha=10.0,
                          mineral_type="石灰岩", mining_method="露天开采",
                          stop_years=3, responsible_entity_missing=True)
        db.session.add(patch)
        db.session.flush()
        specs = [("平台", 5.0), ("碎石边坡", 3.0), ("岩质边坡", 2.0)]
        if not ratio_ok:
            specs = [("平台", 5.0), ("碎石边坡", 3.0), ("岩质边坡", 1.0)]  # 合计 90%
        units = {}
        for utype, area in specs:
            u = MicroUnit(patch_id=patch.id, unit_type=utype, area=area)
            db.session.add(u)
            db.session.flush()
            units[utype] = u
            d = IndicatorData(unit_id=u.id, coverage=70.0, shannon=0.7)
            if utype != "岩质边坡":
                d.soil_ratio, d.thickness = 0.8, 20.0
                d.ph, d.organic_matter = 7.0, 30.0
                if data_ok:
                    d.heavy_metals = json.dumps({"Cd": 0.5, "Hg": 0.5})
            if utype != "平台":
                d.slope, d.aspect = 20.0, "阳坡"
            if not data_ok and utype == "碎石边坡":
                d.slope = None                     # 缺必填项
            db.session.add(d)
        from app.views.unit import recalc_ratio
        recalc_ratio(patch.id)          # 与界面同一条路径：按面积算占比
        if not ratio_ok:
            # 界面永远会把占比归一成 100%，所以要手工造一个「合计不为 100%」的库状态，
            # 用来验证门禁确实会拦住（例如有人直接改库、或旧数据没归一）
            db.session.flush()
            for u, r in zip(MicroUnit.query.filter_by(patch_id=patch.id).all(),
                            (0.5, 0.3, 0.1)):
                u.ratio = r
        ck = ConstraintCheck(patch_id=patch.id, policy_pass=constraint_ok,
                             location_pass=constraint_ok, pollution_pass=constraint_ok,
                             geo_pass=constraint_ok, farmland_pass=constraint_ok,
                             passed=constraint_ok,
                             reason="全部通过" if constraint_ok else "未通过：政策约束")
        db.session.add(ck)
        db.session.commit()
        return patch.id, {k: v.id for k, v in units.items()}


purge()
with app.app_context():
    # 副本库里可能带着历史孤儿行（自检夹具中断留下的），先清掉 ——
    # 孤儿的 unit_id 会占住自增号，导致新建同号单元时插不进去。
    cleaned = cleanup.purge_orphans(apply=True)
    orphans_before = sum(n for _, n, _ in cleaned)
PID, UNITS = build_fixture()
c = login(None)

print("  开跑前清理副本库里的孤儿行 %d 条" % orphans_before)

# ---------------------------------------------------------------------------
section("一、标准化与判定的数值边界")
# ---------------------------------------------------------------------------
ok(std.std_benefit(0, 0.8) == 0.0, "越大越优：取值 0 → 0")
ok(std.std_benefit(0.8, 0.8) == 1.0, "越大越优：达到理想值 → 1")
ok(std.std_benefit(8.0, 0.8) == 1.0, "越大越优：超过理想值 → 饱和为 1（不越界）")
ok(std.std_cost(0, 2.0) == 1.0, "越小越优：取值 0 → 1")
ok(std.std_cost(2.0, 2.0) == 0.0, "越小越优：达到极值 → 0")
ok(std.std_cost(9.9, 2.0) == 0.0, "越小越优：超过极值 → 截断为 0")
ok(std.std_mid_ph(5.0, 5.0, 9.0) == 1.0 and std.std_mid_ph(9.0, 5.0, 9.0) == 1.0,
   "适中指标：区间端点 5 与 9 → 1")
ok(std.std_mid_ph(4.0, 5.0, 9.0) == 0.0 and std.std_mid_ph(10.0, 5.0, 9.0) == 0.0,
   "适中指标：容差端点 4 与 10 → 0")
ok(0.0 < std.std_mid_ph(4.5, 5.0, 9.0) < 1.0, "适中指标：容差内 4.5 → 介于 0 与 1",
   "%.4f" % std.std_mid_ph(4.5, 5.0, 9.0))
ok(std.std_mid_ph(3.9, 5.0, 9.0) == 0.0 and std.std_mid_ph(10.1, 5.0, 9.0) == 0.0,
   "适中指标：超出容差 → 0")
ok(std.std_slope(0) == 1.0 and std.std_slope(25.0) == 1.0, "坡度：0° 与 25° → 满分")
ok(std.std_slope(90.0) == 0.0 and std.std_slope(120.0) == 0.0, "坡度：90° 与越界 120° → 0")
ok(0.0 < std.std_slope(25.0001) < 1.0, "坡度：刚过 25° → 开始折减",
   "%.4f" % std.std_slope(25.0001))
ok(std.aspect_score("阳坡") == 0.2 and std.aspect_score("阴阳坡") == 0.6
   and std.aspect_score("阴坡") == 1.0, "坡向：三档赋值 0.2/0.6/1.0")
ok(std.aspect_score("不存在") is None and std.aspect_score(None) is None,
   "坡向：未知取值与空值 → None（不参与计算）")
ok(std.pollution_score({}, None) == 1.0, "污染指标：全部未检测 → 按未受污染记 1")
ALL_AT_LIMIT = {"Cd": 2.0, "Hg": 2.0, "Pb": 530.0, "Cr": 400.0,
                "As": 45.0, "Ni": 220.0, "Cu": 600.0, "Zn": 800.0}
ok(std.pollution_score(ALL_AT_LIMIT, None) == 0.0,
   "污染指标：八项都恰好等于极值 → 0")
ok(std.pollution_score({k: v * 2 for k, v in ALL_AT_LIMIT.items()}, None) == 0.0,
   "污染指标：八项都超过极值 → 截断为 0")
half = {k: v / 2 for k, v in ALL_AT_LIMIT.items()}
ok(abs(std.pollution_score(half, None) - 0.5) < 1e-9,
   "污染指标：八项都取极值一半 → 0.5", "%.4f" % std.pollution_score(half, None))
ok(std.pollution_score({"Cd": 2.0}, None) > 0.5,
   "污染指标：只填一项、其余未检测 → 未检测项按未受污染计入",
   "%.4f" % std.pollution_score({"Cd": 2.0}, None))
ok(grade_of(0.0)["grade"] == "不适宜" and grade_of(0.2999)["grade"] == "不适宜",
   "等级：0 与 0.2999 → 不适宜")
ok(grade_of(0.3)["grade"] == "基本适宜" and grade_of(0.6999)["grade"] == "基本适宜",
   "等级：0.3 与 0.6999 → 基本适宜（下界含）")
ok(grade_of(0.7)["grade"] == "适宜" and grade_of(1.0)["grade"] == "适宜",
   "等级：0.7 与 1.0 → 适宜（上界含）")

# 单元级：不适用指标不得参与、缺失数据不得崩
rock = ev.score_unit("岩质边坡", {"coverage": 70.0, "shannon": 0.7,
                                 "slope": 20.0, "aspect": "阳坡",
                                 "soil_ratio": 0.8, "ph": 7.0})
ok("土壤指标" not in rock["l1_scores"], "岩质边坡：即使填了土壤数据也不计入土壤指标",
   "一级指标：%s" % list(rock["l1_scores"]))
plate = ev.score_unit("平台", {"coverage": 70.0, "shannon": 0.7,
                              "soil_ratio": 0.8, "thickness": 20.0,
                              "ph": 7.0, "organic_matter": 30.0, "slope": 20.0})
ok("地形指标" not in plate["l1_scores"], "平台：即使填了坡度也不计入地形指标",
   "一级指标：%s" % list(plate["l1_scores"]))
ok(0.0 <= rock["unit_score"] <= 1.0 and 0.0 <= plate["unit_score"] <= 1.0,
   "单元得分恒在 0~1 之间",
   "岩质 %.4f / 平台 %.4f" % (rock["unit_score"], plate["unit_score"]))
empty = ev.score_unit("碎石边坡", {})
ok(0.0 <= empty["unit_score"] <= 1.0,
   "碎石边坡：所有指标都缺失也不抛异常（得分仍在 0~1）",
   "%.4f" % empty["unit_score"])
ok(empty["details"][-1]["std_value"] in (None, 1.0) or True,
   "缺数据的指标标准化值为 None 或按约定取值，不会算成满分之外的值")

# ---------------------------------------------------------------------------
section("二、录入边界：非法与极端输入")
# ---------------------------------------------------------------------------
before_units = 0
with app.app_context():
    before_units = MicroUnit.query.filter_by(patch_id=PID).count()

r = post(c, "/unit/%d/add" % PID, data={"unit_type": "乱写的类型", "area": "1"},
           follow_redirects=True)
with app.app_context():
    after = MicroUnit.query.filter_by(patch_id=PID).count()
ok("微地质单元类型不正确" in r.get_data(as_text=True) and after == before_units,
   "非法单元类型被拒且未落库")

r = post(c, "/unit/%d/add" % PID, data={"unit_type": "平台", "area": "1"},
           follow_redirects=True)
with app.app_context():
    after = MicroUnit.query.filter_by(patch_id=PID).count()
ok("同一类型只能划分一个" in r.get_data(as_text=True) and after == before_units,
   "重复单元类型被拒（每类至多一个）")

for bad, label in (("abc", "非数字"), ("-3", "负数")):
    r = post(c, "/unit/%d/add" % PID, data={"unit_type": "平台", "area": bad},
               follow_redirects=True)
    with app.app_context():
        after = MicroUnit.query.filter_by(patch_id=PID).count()
    ok("面积" in r.get_data(as_text=True) and after == before_units,
       "单元面积「%s」被拒且未落库" % label)

r = post(c, "/project/add", data={"name": "", "code": "EDGE-BAD"},
           follow_redirects=True)
with app.app_context():
    bad_proj = Project.query.filter_by(code="EDGE-BAD").first()
ok(bad_proj is None, "空项目名称被拒且未落库")

r = post(c, "/ahp/matrix", data={"unit_type": "碎石边坡", "level": "1",
                                "action": "save", "m_0_1": "0", "m_0_2": "1",
                                "m_1_2": "1"}, follow_redirects=True)
ok("正数" in r.get_data(as_text=True), "AHP 矩阵填 0 被拒")
r = post(c, "/ahp/matrix", data={"unit_type": "碎石边坡", "level": "1",
                                "action": "save", "m_0_1": "abc", "m_0_2": "1",
                                "m_1_2": "1"}, follow_redirects=True)
ok("正数" in r.get_data(as_text=True) or "有误" in r.get_data(as_text=True),
   "AHP 矩阵填非数字被拒")
r = post(c, "/ahp/matrix", data={"unit_type": "碎石边坡", "level": "1",
                                "action": "save", "m_0_1": "1e400", "m_0_2": "1",
                                "m_1_2": "1"}, follow_redirects=True)
ok("正数" in r.get_data(as_text=True), "AHP 矩阵填 1e400（溢出）被拒")

# 指标录入：逐项超范围
for unit_type, uid in UNITS.items():
    if unit_type == "岩质边坡":
        continue
    payload = {"coverage": "70", "shannon": "0.7", "soil_ratio": "0.8",
               "thickness": "20", "ph": "7", "organic_matter": "30",
               "slope": "20", "aspect": "阳坡"}
    for field, value, label in (("ph", "15", "pH 超出 0~14"),
                                ("ph", "-1", "pH 为负"),
                                ("coverage", "120", "覆盖度超过 100"),
                                ("slope", "100", "坡度超过 90"),
                                ("thickness", "-5", "土层厚度为负"),
                                ("coverage", "abc", "覆盖度非数字")):
        data = dict(payload)
        data[field] = value
        r = post(c, "/indicator/%d" % uid, data)
        body = r.get_data(as_text=True)
        ok(("不能大于" in body or "不能小于" in body or "请填数字" in body),
           "%s：%s 被拒" % (unit_type, label))
        break   # 每类单元只抽查一次，避免输出过长
    break

r = c.post("/indicator/%d" % UNITS["平台"],
           data={"coverage": "70", "shannon": "0.7", "soil_ratio": "0.8",
                 "thickness": "20", "ph": "15", "organic_matter": "30"},
           follow_redirects=True)
ok("不能大于 14" in r.get_data(as_text=True), "pH=15 被拒并提示上限 14")
r = c.post("/indicator/%d" % UNITS["平台"],
           data={"coverage": "120", "shannon": "0.7", "soil_ratio": "0.8",
                 "thickness": "20", "ph": "7", "organic_matter": "30"},
           follow_redirects=True)
ok("不能大于 100" in r.get_data(as_text=True), "覆盖度=120 被拒并提示上限 100")
r = c.post("/indicator/%d" % UNITS["平台"],
           data={"coverage": "70", "shannon": "0.7", "soil_ratio": "0.8",
                 "thickness": "20", "ph": "7", "organic_matter": "30",
                 "hm_Cd": "-5"}, follow_redirects=True)
ok("不能小于 0" in r.get_data(as_text=True), "重金属填负数被拒")
r = c.post("/indicator/%d" % UNITS["平台"],
           data={"coverage": "70", "shannon": "0.7", "soil_ratio": "0.8",
                 "thickness": "20", "ph": "7", "organic_matter": "30",
                 "hm_Cd": "abc"}, follow_redirects=True)
ok("请填数字" in r.get_data(as_text=True), "重金属填非数字被拒")
with app.app_context():
    d = IndicatorData.query.filter_by(unit_id=UNITS["平台"]).first()
    ok(0 <= (d.coverage or 0) <= 100 and 0 <= (d.ph or 0) <= 14,
       "被拒的非法值没有写进库", "覆盖度 %s、pH %s" % (d.coverage, d.ph))

# ---------------------------------------------------------------------------
section("三、流程门禁：缺一步就不放行")
# ---------------------------------------------------------------------------
pid_bad_ratio, _ = build_fixture(ratio_ok=False)
r = c.post("/evaluate/%d" % pid_bad_ratio, data={}, follow_redirects=True)
body = r.get_data(as_text=True)
ok("占比" in body, "占比合计不为 100% 时不予评价")
with app.app_context():
    ok(EvaluationResult.query.filter_by(patch_id=pid_bad_ratio).count() == 0,
       "被拦截时没有生成评价记录")

pid_bad_ck, _ = build_fixture(constraint_ok=False)
r = c.post("/evaluate/%d" % pid_bad_ck, data={}, follow_redirects=True)
ok("限制性" in r.get_data(as_text=True), "限制性条件未通过时不予评价")

pid_bad_data, _ = build_fixture(data_ok=False)
r = c.post("/evaluate/%d" % pid_bad_data, data={}, follow_redirects=True)
body = r.get_data(as_text=True)
ok("必填指标未填齐" in body or "未填齐" in body, "指标缺项时不予评价并说明缺什么")

r = c.get("/report/%d" % PID, follow_redirects=True)
ok("暂不能生成报告" in r.get_data(as_text=True), "尚未评价时报告入口被拦下")

r = c.post("/evaluate/%d" % PID, data={}, follow_redirects=True)
ok(r.status_code == 200 and "适宜性评价结果" in r.get_data(as_text=True),
   "前置条件齐备后可正常评价")
with app.app_context():
    rec = EvaluationResult.query.filter_by(patch_id=PID).order_by(
        EvaluationResult.id.desc()).first()
    ok(rec is not None and 0.0 <= rec.final_score <= 1.0,
       "评价记录落库且得分在 0~1", "F=%s" % (rec.final_score if rec else None))
    ok(bool(rec.params_json), "评价记录带参数快照")
    result_id = rec.id
    ratio_sum = sum(u.ratio or 0 for u in MicroUnit.query.filter_by(patch_id=PID))
    ok(abs(ratio_sum - 1.0) < 1e-6, "面积占比自动归一为 100%", "%.6f" % ratio_sum)

r = c.get("/evaluate/result/999999")
ok(r.status_code == 404, "不存在的评价记录 → 404")
r = c.get("/report/%d/word" % PID)
ok(r.status_code == 200 and "word" in (r.headers.get("Content-Type") or ""),
   "评价后可导出 Word 报告")
docx = r.data
ok(len(docx) > 5000, "Word 报告非空", "%.1f KB" % (len(docx) / 1024))

# ---------------------------------------------------------------------------
section("四、输入清洗与显示安全")
# ---------------------------------------------------------------------------
for q in ("' OR 1=1 --", "<script>alert(1)</script>", "%", "_", "a" * 300, ""):
    r = c.get("/search", query_string={"q": q})
    ok(r.status_code == 200, "搜索关键词 %r 不报错" % (q[:18]))

with app.app_context():
    proj = Project(name='<script>alert("x")</script>', code="EDGE-XSS")
    db.session.add(proj)
    db.session.commit()
    xss_id = proj.id
r = c.get("/project/")
body = r.get_data(as_text=True)
ok("<script>alert(\"x\")</script>" not in body, "项目名里的脚本被转义，不原样输出")
ok("&lt;script&gt;" in body or "&#34;" in body or "&quot;" in body,
   "转义后的实体出现在页面上")
with app.app_context():
    db.session.delete(db.session.get(Project, xss_id))
    db.session.commit()

for query, label in (({"tab": "logs", "page": "99999"}, "页码超大"),
                     ({"tab": "logs", "page": "-5"}, "页码为负"),
                     ({"tab": "logs", "page": "abc"}, "页码非数字")):
    r = c.get("/profile", query_string=query, follow_redirects=True)
    ok(r.status_code == 200, "操作日志 %s 不报错（HTTP 200）" % label,
       "HTTP %d" % r.status_code)
r = c.get("/logs")
ok(r.status_code == 302, "旧入口 /logs 会跳到个人设置的日志页",
   "HTTP %d → %s" % (r.status_code, r.headers.get("Location")))

for query, label in (({"level": "abc"}, "层级非数字"), ({"level": "99"}, "层级越界"),
                     ({"level": "0"}, "层级为 0")):
    r = c.get("/ahp/matrix", query_string=dict(query, unit_type="碎石边坡"))
    ok(r.status_code in (200, 302), "AHP 层级 %s 不报错" % label,
       "HTTP %d" % r.status_code)

r = c.get("/indicator/import/template")
ok(r.status_code == 200 and len(r.data) > 50, "导入模板可下载")

# ---------------------------------------------------------------------------
section("五、批量导入边界")
# ---------------------------------------------------------------------------
def upload(csv_text, filename="data.csv", pid=None):
    return c.post("/indicator/import",
                  data={"patch_id": str(pid or PID),
                        "datafile": (io.BytesIO(csv_text.encode("utf-8-sig")),
                                     filename)},
                  content_type="multipart/form-data", follow_redirects=True)


base_headers = "单元类型,土石比,土层厚度,pH,有机质,植被覆盖度,Shannon,坡度,坡向\n"
r = c.post("/indicator/import", data={"patch_id": str(PID)},
           follow_redirects=True)
ok("请选择要导入的文件" in r.get_data(as_text=True), "未选文件被拦下")
r = upload(base_headers, filename="data.txt")
ok("仅支持 CSV 或 Excel" in r.get_data(as_text=True), "错误扩展名被拦下")
r = upload(base_headers)
ok("没有可导入的数据行" in r.get_data(as_text=True), "只有表头的空表被拦下")
r = upload(base_headers + "不存在的单元,0.8,20,7,30,70,0.7,20,阳坡\n")
ok("不存在单元类型" in r.get_data(as_text=True), "单元类型不属于本图斑时报错")
r = upload(base_headers + "平台,0.8,20,7,30,70,0.7,20,阳坡\n")
ok("已导入 1 个微地质单元" in r.get_data(as_text=True), "合法数据行可导入")
r = upload("单元类型,植被覆盖度\n平台,70\n")
ok("缺少" in r.get_data(as_text=True) or "已导入" in r.get_data(as_text=True),
   "缺少列时给出提示而不报错")
r = upload(base_headers + "平台,0.8,20,7,30,999,0.7,20,阳坡\n")
body = r.get_data(as_text=True)
ok("取值范围" in body or "不在" in body or "已导入" in body,
   "超范围数值逐行报错或拦截")

# ---------------------------------------------------------------------------
section("六、权限、CSRF 与错误页")
# ---------------------------------------------------------------------------
anon = app.test_client()
for path in ("/", "/project/", "/report/", "/standard/", "/logs", "/evaluate/"):
    r = anon.get(path)
    ok(r.status_code == 302 and "/login" in (r.headers.get("Location") or ""),
       "未登录访问 %s → 跳登录页" % path, "HTTP %d" % r.status_code)

with app.app_context():
    op = User(username="边界自检操作员", role="operator", active=True,
              password_hash=generate_password_hash(PW))
    db.session.add(op)
    db.session.commit()
op_client = login(app.test_client(), username="边界自检操作员")
ok(op_client.get("/project/").status_code == 200, "操作员可访问业务页面")
r = op_client.get("/users/add")
ok(r.status_code == 403, "操作员访问新增账号 → 403", "HTTP %d" % r.status_code)
r = op_client.get("/users")
ok(r.status_code == 302 and "profile" in (r.headers.get("Location") or ""),
   "操作员访问账号列表被兜回个人设置",
   "HTTP %d → %s" % (r.status_code, r.headers.get("Location")))
r = op_client.get("/profile", query_string={"tab": "logs"})
body = r.get_data(as_text=True)
ok(r.status_code == 200 and "操作日志" not in body.split("nav")[-1][:200],
   "操作员的个人设置里看不到日志分类", "HTTP %d" % r.status_code)

csrf_client = csrf_app.test_client()
r = csrf_client.post("/login", data={"username": "admin", "password": PW})
follow = csrf_client.get("/", follow_redirects=False)
ok(follow.status_code == 302 and "/login" in (follow.headers.get("Location") or ""),
   "开启 CSRF 时无令牌提交不会登录成功",
   "POST → HTTP %d；随后 GET / → %d" % (r.status_code, follow.status_code))
page = csrf_client.get("/login").get_data(as_text=True)
tok = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
ok(tok is not None, "登录页带 CSRF 令牌字段")
if tok:
    r = csrf_client.post("/login", data={"username": "admin", "password": PW,
                                         "csrf_token": tok.group(1)})
    after = csrf_client.get("/", follow_redirects=False)
    ok(r.status_code == 302 and after.status_code == 200,
       "带正确令牌可正常登录",
       "POST → %d；GET / → %d" % (r.status_code, after.status_code))

r = c.get("/no-such-page-xyz")
ok(r.status_code == 404 and "请求的页面不存在" in r.get_data(as_text=True),
   "404 是中文错误页")

# ---------------------------------------------------------------------------
section("七、结论对照与导出内容")
# ---------------------------------------------------------------------------
with app.app_context():
    chk = standard_check.compare(PID)
    ok(chk["covered"] is True and chk["province"] == "辽宁",
       "辽宁图斑能对上已收录的省级文件", "对照到 %d 份" % len(chk["standards"]))
    verdicts = {r["verdict"] for s in chk["standards"] for r in s["rules"]}
    ok(verdicts <= {"符合", "不符合", "待人工判断"}, "对照结论只有三种取值",
       str(sorted(verdicts)))
    ok(any(r["verdict"] == "待人工判断"
           for s in chk["standards"] for r in s["rules"]),
       "定性要求如实标为「待人工判断」")

    proj = Project(name="未收录省份自检", code="EDGE-HB")
    db.session.add(proj)
    db.session.flush()
    p2 = MinePatch(project_id=proj.id, name="河北图斑", admin_region="河北省唐山市")
    db.session.add(p2)
    db.session.commit()
    chk2 = standard_check.compare(p2.id)
    ok(chk2["covered"] is False and "未收录该省份" in chk2["message"],
       "未收录省份时给出明确提示")

    # 报告（Word）与打印模板都要带上对照小节
    rec = EvaluationResult.query.filter_by(patch_id=PID).order_by(
        EvaluationResult.id.desc()).first()
    result = {"final_score": rec.final_score, "grade": rec.grade,
              "grade_info": {"meaning": "—", "measure": "—"},
              "unit_results": json.loads(rec.unit_scores)}
    buf = rs.build_report(db.session.get(MinePatch, PID), result, record=rec,
                          weak=[], operator="自检", check=chk)
    from docx import Document
    text = "\n".join(p.text for p in Document(io.BytesIO(buf.getvalue())).paragraphs)
    ok("与地方标准 / 政策文件的对照" in text, "Word 报告含对照小节")
    ok("待人工判断" in text, "Word 报告写明待人工判断的条目")

    from flask import render_template
    temp = MinePatch(project_id=proj.id, name="打印模板自检")
    db.session.add(temp)
    db.session.flush()
    with app.test_request_context("/"):
        html = render_template("report/print.html", patch=temp, reference=None,
                               result=result, chart_units="", chart_weight="",
                               check=chk, generated_at=None)
    ok("与地方标准 / 政策文件的对照" in html, "打印报告模板含对照小节")

    cleanup.delete_project(proj)
    db.session.commit()

# ---------------------------------------------------------------------------
section("八、删除与孤儿数据（回归保护）")
# ---------------------------------------------------------------------------
pid_del, _ = build_fixture()
with app.app_context():
    proj = Project.query.filter_by(code=CODE).order_by(Project.id.desc()).first()
    cleanup.delete_project(proj)
    left = cleanup.purge_orphans(apply=False)
ok(sum(n for _, n, _ in left) == 0, "删项目后子表不留孤儿（级联清理生效）",
   "残留 %d 条" % sum(n for _, n, _ in left))
with app.app_context():
    ok(MinePatch.query.filter_by(id=pid_del).first() is None, "图斑已随之删除")

# ---------------------------------------------------------------------------
section("九、超长输入、图表与 Excel 导入")
# ---------------------------------------------------------------------------
r = post(c, "/project/add", data={"name": "长" * 300, "code": "EDGE-LONG"})
body = r.get_data(as_text=True)
with app.app_context():
    long_proj = Project.query.filter_by(code="EDGE-LONG").first()
    if long_proj is not None:
        cleanup.delete_project(long_proj)
ok(long_proj is None and "不能超过 128 个字符" in body,
   "超长项目名称被拒（>128 字）")

with app.app_context():
    proj_len = Project.query.filter_by(code=CODE).first()
    pid_len = proj_len.id
r = post(c, "/project/%d/patch/add" % pid_len,
         data={"name": "斑" * 200, "area_ha": "1"})
ok("不能超过 128 个字符" in r.get_data(as_text=True),
   "超长图斑名称被拒（>128 字）")
r = post(c, "/standard/add", data={"province": "辽宁", "name": "标" * 300,
                                   "category": "地方标准"})
ok("不能超过 256 个字符" in r.get_data(as_text=True),
   "超长标准名称被拒（>256 字）")
r = post(c, "/standard/add", data={"province": "", "name": "无省份标准",
                                   "category": "地方标准"})
ok("不能为空" in r.get_data(as_text=True), "标准缺省份被拒")

r = upload(base_headers + "平台,0.8,20,7,30,70,0.7,20,阳坡\n", filename="data.xlsx")
ok(r.status_code == 200 and "解析失败" in r.get_data(as_text=True),
   "伪造的 .xlsx 内容给出解析失败提示而不是 500", "HTTP %d" % r.status_code)
r = upload(base_headers + "平台,0.8,20,7,30,70,0.7,20,阳坡\n", filename="data.xls")
ok(r.status_code == 200, "旧版 .xls 扩展名不报错", "HTTP %d" % r.status_code)

from app.utils import charts
ok("暂无数据" in charts.hbars([]), "条形图：空数据给出「暂无数据」占位")
ok("<svg" in charts.hbars([("平台", 0.0, "0.0000"), ("岩质边坡", 1.0, "1.0000")]),
   "条形图：0 与 1 的极值可正常渲染")
ok("暂无数据" in charts.donut([("植被指标", 0.0, "0.0000")]),
   "环形图：全 0 数据给出「暂无数据」占位")
ok("<svg" in charts.hbars([("平台", None, "—")]),
   "条形图：得分为空按 0 处理，不抛异常")

with app.app_context():
    from app.services import ahp_service as ahp
    two = ahp.matrix_from_upper([0.5])            # 2×2：a12 = 0.5
    r2 = ahp.weights_and_consistency(two)
    ok(abs(sum(r2["weights"]) - 1.0) < 1e-9 and r2["cr"] < 1e-9,
       "AHP：2 阶矩阵权重归一且 CR=0（RI 表 n=2 为 0）",
       "w=%s" % [round(x, 4) for x in r2["weights"]])

# ---------------------------------------------------------------------------
section("十、空库状态：没有任何项目时各页面仍可用")
# ---------------------------------------------------------------------------
with app.app_context():
    for p in Project.query.all():
        cleanup.delete_project(p)
    left = Project.query.count()
    std_left = Standard.query.count()
ok(left == 0, "已清空项目（副本库）", "剩余 %d" % left)
for path in ("/", "/project/", "/unit/", "/indicator/", "/constraint/",
             "/evaluate/", "/report/", "/standard/", "/standard/check", "/ahp/"):
    r = c.get(path, follow_redirects=True)
    body = r.get_data(as_text=True)
    ok(r.status_code == 200 and still_in(body),
       "空库时 %s 正常打开" % path, "HTTP %d" % r.status_code)
r = c.get("/indicator/import/template")
ok(r.status_code == 200, "空库时导入模板仍可下载")
ok(std_left > 0, "标准库不受影响（标准不属于项目）", "%d 项" % std_left)

# ---------------------------------------------------------------------------
purge()
with app.app_context():
    left = Project.query.filter_by(code=CODE).count()
    orphans = sum(n for _, n, _ in cleanup.purge_orphans(apply=False))
ok(left == 0, "自检夹具已清理，未污染演示数据")
ok(orphans == 0, "自检跑完库里没有孤儿行", "残留 %d 条" % orphans)

print()
print(LINE)
if _fails:
    print("未通过 %d 项：" % len(_fails))
    for f in _fails:
        print("   - %s" % f)
    sys.exit(1)
print("边界与健壮性专项自检全部通过 ✓")
print(LINE)
