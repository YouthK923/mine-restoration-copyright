# -*- coding: utf-8 -*-
"""系统正确性验证用例：8 个带手算期望值的算例。

用法：
    python 工具/数值核对/验证用例.py            建算例 → 跑评价 → 比对期望值
    python 工具/数值核对/验证用例.py --emit-csv 只重新生成 验证数据/*.csv
    python 工具/数值核对/验证用例.py --clean    删除全部算例后退出

设计原则
--------
1. 期望值全部由论文公式**手工推算**并写在注释里，不从系统反算，
   否则「用系统结果验证系统」没有任何意义。
2. 输入值刻意取理想值、极值、分界值，使标准化结果恰为 0 / 0.5 / 1，
   便于逐个指标核对，而不是只看一个总分。
3. 覆盖：理想上限、理论下限、面积加权、污染指标、不适用指标被忽略、
   坡度分界与坡向离散赋值、等级边界、限制性条件一票否决。

计算公式（论文式(8)、式(9) 与表 3、表 4）
-----------------------------------------
标准化（结果限于 [0,1]）
    越大越优  x' = min(x / 理想值, 1)
    越小越优  x' = max(1 - x / 极值, 0)
    pH 适中  [5,9] 记 1；>9 记 max(10-x, 0)；<5 记 max(x-4, 0)
    坡度     ≤25° 记 1；>25° 记 max((90-x)/65, 0)
    坡向     阳坡 0.2、阴阳坡 0.6、阴坡 1.0
    污染     8 种重金属等权，各自 max(1 - 含量/限值, 0)，缺测按 1

单元评价因子
    F' = Σ(一级权重 × 一级得分) / Σ(一级权重)
    一级得分 = Σ(二级权重 × 二级标准化值) / Σ(二级权重)   （不适用项不参与）

整矿评价因子
    F = Σ(单元面积占比 × F')

等级（论文表 4）
    F < 0.3 不适宜 ；0.3 ≤ F < 0.7 基本适宜 ；F ≥ 0.7 适宜
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from app import create_app
from app.models import (db, Project, MinePatch, MicroUnit, IndicatorData,
                        ConstraintCheck, EvaluationResult, ScoreDetail)
from app.services import import_service as imp

CSV_DIR = os.path.join(BASE, "验证数据")
CODE_PREFIX = "VERIFY-"

HEADERS = imp.HEADERS        # 单元类型,土石比,土层厚度,pH,有机质,Cd..Zn,植被覆盖度,Shannon,坡度,坡向


def row(unit_type, soil=None, metals=None, cover=None, shannon=None,
        slope=None, aspect=None):
    """按导入模板的表头顺序拼一行；soil 为 (土石比,厚度,pH,有机质)。"""
    def s(v):
        return "" if v is None else ("%g" % v)
    cells = [unit_type]
    cells += [s(v) for v in (soil or (None, None, None, None))]
    m = metals or {}
    cells += [s(m.get(k)) for k in ("Cd", "Hg", "Pb", "Cr", "As", "Ni",
                                    "Cu", "Zn")]
    cells += [s(cover), s(shannon), s(slope), aspect or ""]
    return cells


# ---------------------------------------------------------------------------
# 理想值与极值（与 app.utils.constants 一致，此处复写以便独立对照）
# ---------------------------------------------------------------------------
IEDEAL = dict(soil=0.8, thick=20.0, org=30.0, cover=75.0, shannon=0.7)
LIMIT = dict(Cd=2.0, Hg=2.0, Pb=530.0, Cr=400.0, As=45.0, Ni=220.0,
             Cu=600.0, Zn=800.0)
AT_LIMIT = dict(LIMIT)          # 全部取限值 → 污染 = 0
NO_METAL = {k: 0 for k in LIMIT}  # 全部为 0 → 污染 = 1


# ---------------------------------------------------------------------------
# 算例定义
# 每项：(文件名, 图斑名, [ (单元类型, 面积ha) ... ], [CSV 行 ... ],
#       期望 F, 期望等级, 手算说明)
# ---------------------------------------------------------------------------
CASES = [
    dict(
        key="01",
        title="理想上限：全部指标取最优",
        file="理想上限_碎石边坡",
        patch="验证1 理想上限",
        units=[("碎石边坡", 10.0)],
        rows=[row("碎石边坡", soil=(0.8, 20, 7, 30), metals=NO_METAL,
                  cover=75, shannon=0.7, slope=25, aspect="阴坡")],
        expect_f=1.0000, expect_grade="适宜",
        expect_units={"碎石边坡": 1.0000},
        calc=[
            "土壤：土石比 0.8/0.8=1，厚度 20/20=1，pH 7∈[5,9]=1，有机质 30/30=1，",
            "      污染 8 种重金属均为 0 → 各自 1-0/限值=1 → 污染=1",
            "      土壤一级 = (0.25+0.25+0.17+0.17+0.17×1)/1.01 = 1.01/1.01 = 1.0000",
            "植被：覆盖度 75/75=1，Shannon 0.7/0.7=1 → 植被一级 = 1.0000",
            "地形：坡度 25≤25 记 1，坡向 阴坡 记 1.0 → 地形一级 = 1.0000",
            "单元 F' = 0.44×1 + 0.31×1 + 0.25×1 = 1.0000",
            "F = 1.0000×100% = 1.0000 → 适宜",
        ],
    ),
    dict(
        key="02",
        title="理论下限：全部指标取最差（平台，无地形指标）",
        file="理论下限_平台",
        patch="验证2 理论下限",
        units=[("平台", 10.0)],
        rows=[row("平台", soil=(0, 0, 0, 0), metals=AT_LIMIT,
                  cover=0, shannon=0, slope=None, aspect=None)],
        expect_f=0.0000, expect_grade="不适宜",
        expect_units={"平台": 0.0000},
        calc=[
            "土壤：土石比 0/0.8=0，厚度 0/20=0，",
            "      pH 0<5 → max(0-4, 0)=0，有机质 0/30=0，",
            "      污染 8 种重金属均取限值 → 各自 1-1=0 → 污染=0",
            "      土壤一级 = 0/1.01 = 0.0000",
            "植被：覆盖度 0，Shannon 0 → 植被一级 = 0.0000",
            "单元 F' = 0.54×0 + 0.46×0 = 0.0000",
            "F = 0.0000 → 不适宜（平台不设地形指标，故不受坡向最低 0.2 影响）",
        ],
    ),
    dict(
        key="03",
        title="面积加权：三类单元混合，验证式(9) 的加权合成",
        file="面积加权_三单元混合",
        patch="验证3 面积加权",
        units=[("岩质边坡", 2.0), ("碎石边坡", 5.0), ("平台", 3.0)],
        rows=[
            row("岩质边坡", cover=0, shannon=0, slope=25, aspect="阳坡"),
            row("碎石边坡", soil=(0, 0, 0, 0), metals=AT_LIMIT,
                cover=75, shannon=0.7, slope=90, aspect="阴坡"),
            row("平台", soil=(0.8, 20, 7, 30), metals=NO_METAL,
                cover=0, shannon=0, slope=None, aspect=None),
        ],
        expect_f=0.4366, expect_grade="基本适宜",
        expect_units={"岩质边坡": 0.3916, "碎石边坡": 0.3925,
                      "平台": 0.5400},
        calc=[
            "面积占比：岩质 2/10=20%，碎石 5/10=50%，平台 3/10=30%",
            "岩质边坡：植被 0 → 0；地形 = 0.64×1(坡度25) + 0.36×0.2(阳坡) = 0.712",
            "          F' = 0.45×0 + 0.55×0.712 = 0.3916",
            "碎石边坡：土壤全 0 → 0；植被 = 0.64×1 + 0.36×1 = 1.0；",
            "          地形 = 0.67×0(坡度90) + 0.33×1(阴坡) = 0.33",
            "          F' = 0.44×0 + 0.31×1 + 0.25×0.33 = 0.3925",
            "平台：土壤 = 1.0（全部取最优）；植被 = 0（覆盖度与多样性均为 0）",
            "      F' = 0.54×1 + 0.46×0 = 0.5400",
            "F = 0.2×0.3916 + 0.5×0.3925 + 0.3×0.5400",
            "  = 0.07832 + 0.19625 + 0.16200 = 0.43657 → 0.4366 → 基本适宜",
        ],
    ),
    dict(
        key="04",
        title="污染指标：8 种重金属全部达到限值",
        file="污染取限值_碎石边坡",
        patch="验证4 污染取限值",
        units=[("碎石边坡", 10.0)],
        rows=[row("碎石边坡", soil=(0.8, 20, 7, 30), metals=AT_LIMIT,
                  cover=75, shannon=0.7, slope=25, aspect="阴坡")],
        expect_f=0.9259, expect_grade="适宜",
        expect_units={"碎石边坡": 0.925941},
        calc=[
            "除污染外全部取最优，故土壤一级只剩污染项被拉低：",
            "  污染 = 0（8 种均取限值，各自 1-1=0）",
            "  土壤一级 = (0.25+0.25+0.17+0.17+0.17×0)/1.01 = 0.84/1.01 = 0.8316832",
            "植被 = 1.0000，地形 = 1.0000",
            "单元 F' = 0.44×0.8316832 + 0.31×1 + 0.25×1 = 0.9259406",
            "F = 0.9259 → 适宜",
            "说明：污染项权重 0.17，占土壤 0.44 中的 0.17×0.44 = 7.48%，",
            "      故重金属全部超标仅使总分下降约 7.4%，这是论文表 3 权重的必然结果。",
        ],
    ),
    dict(
        key="05",
        title="不适用指标必须被忽略：岩质边坡不应启用土壤指标",
        file="岩质边坡忽略土壤指标",
        patch="验证5 岩质边坡含土壤数据",
        units=[("岩质边坡", 10.0)],
        rows=[row("岩质边坡", soil=(0.8, 20, 7, 30), metals=NO_METAL,
                  cover=75, shannon=0.7, slope=90, aspect="阳坡")],
        expect_f=0.4896, expect_grade="基本适宜",
        expect_units={"岩质边坡": 0.4896},
        calc=[
            "岩质边坡按论文表 3 不设土壤指标，故上面填的土石比/厚度/pH/有机质/",
            "重金属全部不参与计算，期望值与「完全不填土壤数据」时相同。",
            "植被 = 0.67×1(覆盖度75) + 0.33×1(Shannon0.7) = 1.0000",
            "地形 = 0.64×0(坡度90) + 0.36×0.2(阳坡) = 0.0720",
            "F' = 0.45×1 + 0.55×0.072 = 0.45 + 0.0396 = 0.4896",
            "F = 0.4896 → 基本适宜",
            "孪生对照：再造一个「不填土壤数据」的同型算例，两者 F 必须完全相同。",
        ],
        twin=dict(patch="验证5b 岩质边坡不含土壤数据",
                  rows=[row("岩质边坡", cover=75, shannon=0.7, slope=90,
                            aspect="阳坡")]),
    ),
    dict(
        key="06",
        title="不适用指标必须被忽略：平台不应启用地形指标",
        file="平台忽略地形指标",
        patch="验证6 平台含地形数据",
        units=[("平台", 10.0)],
        rows=[row("平台", soil=(0.8, 20, 7, 30), metals=NO_METAL,
                  cover=75, shannon=0.7, slope=90, aspect="阳坡")],
        expect_f=1.0000, expect_grade="适宜",
        expect_units={"平台": 1.0000},
        calc=[
            "平台按论文表 3 不设地形指标，故坡度 90 与坡向 阳坡不参与计算。",
            "土壤 = 1.0000（五项全取最优）",
            "植被 = 0.61×1 + 0.39×1 = 1.0000",
            "F' = 0.54×1 + 0.46×1 = 1.0000",
            "F = 1.0000 → 适宜",
            "孪生对照：再造一个「不填坡度坡向」的同型算例，两者 F 必须完全相同。",
        ],
        twin=dict(patch="验证6b 平台不含地形数据",
                  rows=[row("平台", soil=(0.8, 20, 7, 30), metals=NO_METAL,
                            cover=75, shannon=0.7)]),
    ),
    dict(
        key="07",
        title="坡度分界与坡向离散赋值：坡度 57.5°、阴阳坡",
        file="坡度分界_坡向赋值",
        patch="验证7 坡度坡向",
        units=[("岩质边坡", 10.0)],
        rows=[row("岩质边坡", cover=75, shannon=0.7, slope=57.5,
                  aspect="阴阳坡")],
        expect_f=0.7448, expect_grade="适宜",
        expect_units={"岩质边坡": 0.7448},
        calc=[
            "植被 = 1.0000（覆盖度与多样性均取参照值）",
            "坡度 57.5 > 25 → (90-57.5)/(90-25) = 32.5/65 = 0.5000",
            "坡向 阴阳坡 → 0.6000",
            "地形 = 0.64×0.5 + 0.36×0.6 = 0.32 + 0.216 = 0.5360",
            "F' = 0.45×1 + 0.55×0.536 = 0.45 + 0.2948 = 0.7448",
            "F = 0.7448 → 适宜（刚好越过 0.7 分界）",
        ],
    ),
    dict(
        key="08",
        title="限制性条件一票否决：耕地属性不通过",
        file="一票否决_耕地不通过",
        patch="验证8 一票否决",
        units=[("碎石边坡", 10.0)],
        rows=[row("碎石边坡", soil=(0.8, 20, 7, 30), metals=NO_METAL,
                  cover=75, shannon=0.7, slope=25, aspect="阴坡")],
        expect_f=None, expect_grade="不进入定量评价",
        constraint=False,          # 判定不通过
        calc=[
            "数据本身为理想上限（与算例 01 相同），但限制性条件判定不通过。",
            "按论文 4.1 节，此类矿山应直接判定为「人工辅助或生态重建」，",
            "不进入定量评价。期望：执行评价被拦下，且不产生任何评价结果。",
        ],
    ),
]


# ---------------------------------------------------------------------------
# CSV 生成
# ---------------------------------------------------------------------------
def emit_csv():
    os.makedirs(CSV_DIR, exist_ok=True)
    import csv as _csv
    made = []
    for case in CASES:
        if not case["rows"]:
            continue
        fn = "用例%s_%s.csv" % (case["key"], case["file"])
        path = os.path.join(CSV_DIR, fn)
        buf = io.StringIO()
        w = _csv.writer(buf)
        w.writerow(HEADERS)
        for r in case["rows"]:
            w.writerow(r)
        # 带 BOM 写出，便于 Excel 直接双击打开不乱码；导入端按 utf-8-sig 读取
        with io.open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(buf.getvalue())
        made.append(fn)
    return made


# ---------------------------------------------------------------------------
# 在系统中建算例并核对
# ---------------------------------------------------------------------------
class TestConfig:
    SECRET_KEY = "verify"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE, "app",
                                                          "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


def clean(app):
    """删除此前生成的验证算例（仅限编号 VERIFY- 的项目）。"""
    with app.app_context():
        ids = [p.id for p in Project.query.filter(
            Project.code.like(CODE_PREFIX + "%")).all()]
        if not ids:
            return 0
        pids = [m.id for m in MinePatch.query.filter(
            MinePatch.project_id.in_(ids)).all()]
        if pids:
            uids = [u.id for u in MicroUnit.query.filter(
                MicroUnit.patch_id.in_(pids)).all()]
            if uids:
                IndicatorData.query.filter(
                    IndicatorData.unit_id.in_(uids)).delete(
                    synchronize_session=False)
            rids = [r.id for r in EvaluationResult.query.filter(
                EvaluationResult.patch_id.in_(pids)).all()]
            if rids:
                ScoreDetail.query.filter(
                    ScoreDetail.result_id.in_(rids)).delete(
                    synchronize_session=False)
            EvaluationResult.query.filter(
                EvaluationResult.patch_id.in_(pids)).delete(
                synchronize_session=False)
            ConstraintCheck.query.filter(
                ConstraintCheck.patch_id.in_(pids)).delete(
                synchronize_session=False)
            MicroUnit.query.filter(MicroUnit.patch_id.in_(pids)).delete(
                synchronize_session=False)
            MinePatch.query.filter(MinePatch.id.in_(pids)).delete(
                synchronize_session=False)
        Project.query.filter(Project.id.in_(ids)).delete(
            synchronize_session=False)
        db.session.commit()
        return len(ids)


def build_and_check(app, c, case, suffix="", patch_name=None, rows=None):
    """按网页路径建立算例并执行评价，返回实际结果。"""
    import json
    code = CODE_PREFIX + case["key"] + suffix

    # 1) 项目与图斑
    c.post("/project/add",
           data={"name": patch_name or case["patch"], "code": code},
           follow_redirects=True)
    with app.app_context():
        proj = Project.query.filter_by(code=code).first()
        pid = proj.id
    c.post("/project/%d/patch/add" % pid,
           data={"name": patch_name or case["patch"], "area_ha": "0",
                 "admin_region": "验证用数据"}, follow_redirects=True)
    with app.app_context():
        patch = MinePatch.query.filter_by(project_id=pid).first()
        patch_id = patch.id

    # 2) 微地质单元与面积
    for unit_type, area in case["units"]:
        c.post("/unit/%d/add" % patch_id,
               data={"unit_type": unit_type, "area": "%g" % area},
               follow_redirects=True)

    # 3) 限制性条件判定
    passed = "1" if case.get("constraint", True) else "0"
    c.post("/constraint/%d" % patch_id,
           data={"policy_pass": passed, "location_pass": passed,
                 "pollution_pass": passed, "geo_pass": passed,
                 "farmland_pass": passed}, follow_redirects=True)

    # 4) 批量导入指标数据（走真实的导入接口）
    use_rows = case["rows"] if rows is None else rows
    if use_rows:
        import csv as _csv
        buf = io.StringIO()
        w = _csv.writer(buf)
        w.writerow(HEADERS)
        for r in use_rows:
            w.writerow(r)
        c.post("/indicator/import",
               data={"patch_id": str(patch_id),
                     "datafile": (io.BytesIO(buf.getvalue().encode("utf-8")),
                                  "case.csv")},
               content_type="multipart/form-data", follow_redirects=True)

    # 5) 执行评价
    c.post("/evaluate/%d" % patch_id, data={}, follow_redirects=True)
    with app.app_context():
        rec = EvaluationResult.query.filter_by(patch_id=patch_id) \
            .order_by(EvaluationResult.id.desc()).first()
        out = {
            "patch_id": patch_id,
            "final": rec.final_score if rec else None,
            "grade": rec.grade if rec else None,
            "units": json.loads(rec.unit_scores) if rec else [],
        }
    return out


def main():
    if "--emit-csv" in sys.argv:
        made = emit_csv()
        print("已生成 %d 个 CSV 到 验证数据/：" % len(made))
        for m in made:
            print("  ", m)
        return 0

    app = create_app(TestConfig)
    if "--clean" in sys.argv:
        n = clean(app)
        print("已删除 %d 个验证算例" % n)
        return 0

    emit_csv()
    n = clean(app)
    if n:
        print("（已清理上次的 %d 个验证算例）" % n)

    c = app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin123"},
           follow_redirects=True)

    LINE = "=" * 78
    print()
    print(LINE)
    print("  系统正确性验证：8 个算例（期望值由论文公式手工推算）")
    print(LINE)

    fails = []
    for case in CASES:
        r = build_and_check(app, c, case)
        print()
        print("-" * 78)
        print("算例 %s  %s" % (case["key"], case["title"]))
        print("-" * 78)
        for line in case["calc"]:
            print("    推算｜" + line)
        exp_f, exp_g = case["expect_f"], case["expect_grade"]
        if exp_f is None:
            ok = r["final"] is None
            print("    期望｜不产生评价结果")
            print("    实际｜%s" % ("无评价结果（已被拦下）" if ok else
                                    "F=%.4f %s" % (r["final"], r["grade"])))
            if not ok:
                fails.append(case["key"])
        else:
            got_f = r["final"] if r["final"] is not None else float("nan")
            ok = (abs(got_f - exp_f) < 5e-5) and r["grade"] == exp_g
            print("    期望｜F = %.4f，等级 = %s" % (exp_f, exp_g))
            print("    实际｜F = %s，等级 = %s"
                  % ("%.4f" % got_f if r["final"] is not None else "无",
                     r["grade"] or "无"))
            print("    判定｜%s" % ("[一致] ✓" if ok else "[不一致] ✗"))
            if not ok:
                fails.append(case["key"])

            # 单元得分逐个核对（总分对不代表每个单元都对，可能互相抵消）
            want_units = case.get("expect_units") or {}
            got_units = {u["unit_type"]: u["unit_score"] for u in r["units"]}
            for ut, want_u in sorted(want_units.items()):
                got_u = got_units.get(ut)
                ok_u = got_u is not None and abs(got_u - want_u) < 5e-5
                print("    单元｜%-6s 期望 F′ = %.4f   实际 F′ = %s   %s"
                      % (ut, want_u,
                         "%.4f" % got_u if got_u is not None else "无",
                         "[一致] ✓" if ok_u else "[不一致] ✗"))
                if not ok_u:
                    fails.append("%s单元%s" % (case["key"], ut))

        # 孪生对照：去掉多余指标后，结果必须完全相同
        twin = case.get("twin")
        if twin:
            t = build_and_check(app, c, case, suffix="b",
                                patch_name=twin["patch"], rows=twin["rows"])
            same = (r["final"] is not None and t["final"] is not None
                    and abs(r["final"] - t["final"]) < 1e-9)
            print("    孪生｜%s → F = %.4f"
                  % (twin["patch"], t["final"] if t["final"] is not None
                     else float("nan")))
            print("    判定｜去掉多余指标后结果%s"
                  % ("完全相同 ✓" if same else "发生变化 ✗"))
            if not same:
                fails.append(case["key"] + "孪生")

    # ---- 等级边界单独核对（论文表 4 的分界口径）----
    from app.utils.constants import grade_of
    print()
    print("-" * 78)
    print("等级边界（论文表 4：F<0.3 不适宜，0.3≤F<0.7 基本适宜，F≥0.7 适宜）")
    print("-" * 78)
    for v, want in ((0.2999, "不适宜"), (0.3000, "基本适宜"),
                    (0.6999, "基本适宜"), (0.7000, "适宜"),
                    (0.0000, "不适宜"), (1.0000, "适宜")):
        got = grade_of(v)["grade"]
        ok = got == want
        print("    F = %.4f → %-6s 期望 %-6s %s"
              % (v, got, want, "[一致] ✓" if ok else "[不一致] ✗"))
        if not ok:
            fails.append("边界%.4f" % v)

    print()
    print(LINE)
    if fails:
        print("  未通过：%s" % "、".join(fails))
        print(LINE)
        return 1
    print("  全部算例与期望值一致，系统计算正确 ✓")
    print()
    print("  算例已保留在系统中（项目编号 VERIFY-01…08 及孪生 VERIFY-05b/06b），")
    print("  可登录界面逐个查看。删除：")
    print("      python 工具/数值核对/验证用例.py --clean")
    print("  ＊ 生成软著材料（截图 / 说明书）前建议先清理，否则列表页会带上这些算例。")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
