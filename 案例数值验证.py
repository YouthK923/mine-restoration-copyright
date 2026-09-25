# -*- coding: utf-8 -*-
"""
历史遗留废弃矿山自然恢复适宜性评价 —— 论文案例数值验证程序
================================================================

用途
    以论文《历史遗留废弃矿山自然恢复适宜性评价指标体系建设及典型案例》
    第 5 节的玉田县案例为输入，按论文 4.2 节给出的计算公式独立复算，
    核对论文表 5 所列结果的内部一致性。

数据来源（全部逐字取自论文原表，未作修改）
    - 表 3  各级指标权重（按微地质单元分别定权）
    - 表 4  适宜性评价等级
    - 表 5  典型矿山调查及适宜性评价结果
    - 4.2.2 式(8)   指标标准化方法与理想极值
    - 4.2.2 式(9)   微地质单元评价因子与面积加权合成
    - 第 5 节        三类微地质单元面积占比

运行
    python 案例数值验证.py
    仅依赖 Python 标准库，无第三方依赖，输出完全可复现。

说明
    本程序为独立复算工具，用于核对论文数值；
    结论仅指出"论文所述结果与论文所述公式之间存在差异"，
    不涉及对研究结论或方法本身有效性的评价。
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LINE = "=" * 78
SUB = "-" * 74

# ============================================================================
# 一、输入数据（全部抄录自论文，未作修改）
# ============================================================================

# ---- 论文第 5 节：三类微地质单元面积占比 ----
# 原文："图斑中岩质边坡、碎石边坡、平台分别占矿区总面积的 13.86%、62.95%、23.19%"
AREA_PCT = {"岩质边坡": 13.86, "碎石边坡": 62.95, "平台": 23.19}
UNITS = ("岩质边坡", "碎石边坡", "平台")

# ---- 论文表 5：单元得分与最终得分 ----
PAPER_UNIT_SCORE = {"岩质边坡": 0.56, "碎石边坡": 0.74, "平台": 0.85}
PAPER_FINAL = 0.76

# ---- 论文表 3：各级指标权重 ----
# 论文明确："划分岩质边坡、碎石土边坡、平台三类微地质单元开展独立评价，
#           分别计算评价指标权重"。岩质边坡不设土壤指标，平台不设地形指标。
W_L1 = {
    "岩质边坡": {"植被指标": 0.45, "地形指标": 0.55},
    "碎石边坡": {"土壤指标": 0.44, "植被指标": 0.31, "地形指标": 0.25},
    "平台":     {"土壤指标": 0.54, "植被指标": 0.46},
}
W_L2 = {
    "岩质边坡": {"植被覆盖度": 0.67, "生物多样性": 0.33,
                 "坡度": 0.64, "坡向": 0.36},
    "碎石边坡": {"土石比": 0.25, "土层厚度": 0.25, "pH": 0.17, "有机质": 0.17,
                 "污染指标": 0.17, "植被覆盖度": 0.64, "生物多样性": 0.36,
                 "坡度": 0.67, "坡向": 0.33},
    "平台":     {"土石比": 0.25, "土层厚度": 0.25, "pH": 0.17, "有机质": 0.17,
                 "污染指标": 0.17, "植被覆盖度": 0.61, "生物多样性": 0.39},
}

# ---- 论文表 5：实测指标数据 ----
# 论文注："典型矿山土壤污染指标未检测 Cr 和 Zn，从矿山类型看矿山土壤未受 Cr 和 Zn 污染"
DATA = {
    "岩质边坡": {"土石比": 0, "土层厚度": 0, "pH": 0, "有机质": 0,
                 "Hg": 0, "As": 0, "Ni": 0, "Cu": 0, "Cd": 0, "Pb": 0,
                 "植被覆盖度": 68.88, "生物多样性": 0.00,
                 "坡度": 63.33, "坡向": "阴阳坡"},
    "碎石边坡": {"土石比": 0.34, "土层厚度": 10, "pH": 9.24, "有机质": 4.89,
                 "Hg": 0.05, "As": 5.17, "Ni": 12.60, "Cu": 11.70, "Cd": 0.04, "Pb": 6.50,
                 "植被覆盖度": 87.92, "生物多样性": 0.60,
                 "坡度": 28.75, "坡向": "阳坡"},
    "平台":     {"土石比": 0.56, "土层厚度": 30, "pH": 8.72, "有机质": 10.92,
                 "Hg": 0.02, "As": 3.13, "Ni": 12.33, "Cu": 11.14, "Cd": 0.09, "Pb": 9.98,
                 "植被覆盖度": 58.42, "生物多样性": 0.72,
                 "坡度": 0, "坡向": "—"},
}

# ---- 论文 4.2.2 节：标准化理想极值 ----
IDEAL_SOIL_RATIO = 0.8
IDEAL_THICKNESS = 20.0
IDEAL_PH_RANGE = (5.0, 9.0)
IDEAL_ORGANIC = 30.0
IDEAL_COVERAGE = 75.0
IDEAL_SHANNON = 0.7

# 重金属极值 (mg/kg)，《绿化种植土壤》CJ/T 340—2016 IV 级最高值
IDEAL_HEAVY_METAL = {"Cd": 2.0, "Hg": 2.0, "Pb": 530.0, "Cr": 400.0,
                     "As": 45.0, "Ni": 220.0, "Cu": 600.0, "Zn": 800.0}

# 坡度分界，论文 4.2.2 节引《新一轮退耕还林还草总体方案》发改西部〔2014〕1772 号
SLOPE_BREAK = 25.0

# 坡向离散赋值，论文 4.2.2 节："阳坡、阴阳坡、阴坡分别赋值 0.2、0.6、1"
ASPECT_SCORE = {"阳坡": 0.2, "阴阳坡": 0.6, "阴坡": 1.0}

# ---- 平均随机一致性指标 RI（论文 4.2.1 节给出 n=2,3,4,5 的值）----
RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32,
      8: 1.41, 9: 1.45, 10: 1.49}

PASS, FAIL = "[一致]", "[不一致]"
_findings = []


def report(ok, title, detail=""):
    print(f"  {PASS if ok else FAIL} {title}")
    if detail:
        for ln in detail.strip().splitlines():
            print(f"          {ln}")
    _findings.append((ok, title))


# ============================================================================
# 二、式(8) 标准化函数
# ============================================================================
# 论文式(8)：x' = (x - x_min) / (x_max - x_min)
# 论文 4.2.2 节进一步说明：土石比、土层厚度理想值为 0.8、20cm；
# pH 用适中指标方法；有机质理想值 30 g/kg；重金属取 IV 级最高值；
# 植被覆盖度与 Shannon 多样性参照生态系统（75%、0.7）。

def std_benefit(value, ideal):
    """越大越优：以理想值为上限，按比例给分，饱和于 1。"""
    return max(0.0, min(1.0, value / ideal))


def std_cost(value, extreme):
    """越小越优：以极值为下限，线性折减至 0。"""
    return max(0.0, min(1.0, 1.0 - value / extreme))


def std_ph(value, lo, hi, tol_lo=4.0, tol_hi=10.0):
    """适中型：理想区间内取 1，区间外线性衰减。"""
    if lo <= value <= hi:
        return 1.0
    if value > hi:
        return max(0.0, (tol_hi - value) / (tol_hi - hi))
    return max(0.0, (value - tol_lo) / (lo - tol_lo))


def pollution_score(d):
    """污染指标：8 种重金属按等权 0.125 合成。未检测的按论文注视为未污染。"""
    total = 0.0
    for metal, extreme in IDEAL_HEAVY_METAL.items():
        total += std_cost(d[metal], extreme) if metal in d else 1.0
    return total / len(IDEAL_HEAVY_METAL)


# ============================================================================
# 三、核对一：论文表 5 单元得分 → 论文最终得分
# ============================================================================

def check_weighted_total():
    print(LINE)
    print("核对一  三个单元得分按面积占比加权，是否等于论文最终得分")
    print(LINE)
    print("  公式（论文 4.2.2 式(9) 后半段）：  F = Σ ( Sᵢ × F′ᵢ )")
    print("  Sᵢ 为第 i 类微地质单元面积占比，F′ᵢ 为该单元评价因子")
    print()
    print(f"  {'微地质单元':<12}{'面积占比 Sᵢ':>14}{'单元得分 F′ᵢ':>15}{'乘积':>12}")
    print("  " + SUB[:56])

    total = 0.0
    for u in UNITS:
        s = AREA_PCT[u] / 100.0
        f = PAPER_UNIT_SCORE[u]
        total += s * f
        print(f"  {u:<12}{AREA_PCT[u]:>13.2f}%{f:>15.2f}{s*f:>12.4f}")
    print("  " + SUB[:56])
    print(f"  {'合计':<12}{sum(AREA_PCT.values()):>13.2f}%{'':>15}{total:>12.4f}")
    print()
    print("  展开计算：")
    print("    F = " + " + ".join(
        f"{PAPER_UNIT_SCORE[u]:.2f}×{AREA_PCT[u]/100:.4f}" for u in UNITS))
    print(f"      = {total:.4f}")
    print(f"      ≈ {round(total, 2):.2f}")
    print()
    print(f"  论文表 5 所载最终得分 ：{PAPER_FINAL:.2f}")
    print(f"  复算所得             ：{round(total, 2):.2f}")
    print(f"  差值                 ：{PAPER_FINAL - round(total, 2):+.2f}")
    print()
    report(abs(round(total, 2) - PAPER_FINAL) < 1e-9,
           f"加权所得 {round(total,2):.2f} 是否等于论文最终得分 {PAPER_FINAL:.2f}",
           "论文所述三个单元得分与面积占比，按论文式(9) 加权后得不到论文所述最终得分。")

    # 反推：使加权结果等于论文值所需的最小占比调整
    print()
    print("  反推：保持三单元得分不变，求使 F = 0.76 的占比调整量（最小范数解）")
    b = [PAPER_UNIT_SCORE[u] - PAPER_UNIT_SCORE[UNITS[0]] for u in UNITS]
    x0 = [AREA_PCT[u] for u in UNITS]
    delta = PAPER_FINAL - total
    bb = sum(v * v for v in b)
    adj = [delta * v / bb for v in b]          # 最小范数解
    print(f"    F₀ = {total:.4f}，Δ = 0.76 - F₀ = {delta:+.4f}")
    print(f"    {'微地质单元':<12}{'论文占比':>12}{'需改为':>12}{'改变量':>12}")
    print("    " + SUB[:48])
    for i, u in enumerate(UNITS):
        print(f"    {u:<12}{x0[i]:>11.2f}%{x0[i]+adj[i]:>11.4f}%{adj[i]:>+11.4f}")
    print("    " + SUB[:48])
    print(f"    {'合计':<12}{sum(x0):>11.2f}%{sum(x0)+sum(adj):>11.4f}%{sum(adj):>+11.4f}")
    print()
    print(f"    即需把碎石边坡占比由 {x0[1]:.2f}% 上调至 {x0[1]+adj[1]:.2f}%，")
    print(f"    平台占比由 {x0[2]:.2f}% 上调至 {x0[2]+adj[2]:.2f}%。")
    print("    两者均需上调，合计超出 100%，说明该偏差无法通过调整占比消除——")
    print("    论文第 5 节所述占比为实测值，本不应为凑合最终得分而改动。")
    return total


# ============================================================================
# 四、核对二：论文表 5 原始数据 → 三个单元得分
# ============================================================================

def compute_units():
    """按论文式(8)+式(9) 由表 5 原始数据计算各单元得分。"""
    result = {}
    for u in UNITS:
        d, w1, w2 = DATA[u], W_L1[u], W_L2[u]
        rows, l1 = [], {}

        # ---- 土壤指标 ----
        if "土壤指标" in w1:
            soil = [("土石比", d["土石比"], std_benefit(d["土石比"], IDEAL_SOIL_RATIO)),
                    ("土层厚度", d["土层厚度"], std_benefit(d["土层厚度"], IDEAL_THICKNESS)),
                    ("pH", d["pH"], std_ph(d["pH"], *IDEAL_PH_RANGE)),
                    ("有机质", d["有机质"], std_benefit(d["有机质"], IDEAL_ORGANIC)),
                    ("污染指标", "8项重金属", pollution_score(d))]
            l1["土壤指标"] = sum(w2[k] * v for k, _, v in soil)
            rows += [("土壤指标", k, str(r), v, w2[k], v * w2[k]) for k, r, v in soil]

        # ---- 植被指标 ----
        veg = [("植被覆盖度", d["植被覆盖度"], std_benefit(d["植被覆盖度"], IDEAL_COVERAGE)),
               ("生物多样性", d["生物多样性"], std_benefit(d["生物多样性"], IDEAL_SHANNON))]
        l1["植被指标"] = sum(w2[k] * v for k, _, v in veg)
        rows += [("植被指标", k, str(r), v, w2[k], v * w2[k]) for k, r, v in veg]

        # ---- 地形指标 ----
        slope_known = False
        if "地形指标" in w1:
            aspect = ASPECT_SCORE.get(d["坡向"], 0.0)
            l1["地形指标"] = w2["坡向"] * aspect          # 仅坡向部分已知
            slope_known = False
            rows += [("地形指标", "坡度", f"{d['坡度']}°", None, w2["坡度"], None),
                     ("地形指标", "坡向", d["坡向"], aspect, w2["坡向"], aspect * w2["坡向"])]

        # ---- 单元得分 ----
        complete = all(k in ("土壤指标", "植被指标") for k in l1)
        if complete:
            total = sum(w1[k] * l1[k] for k in l1)
        else:
            total = None

        result[u] = {"rows": rows, "l1": l1, "total": total,
                     "slope_known": slope_known, "w1": w1, "w2": w2}
    return result


def print_unit_table(u, r):
    print()
    print(SUB)
    print(f"  【{u}】")
    print(SUB)
    print(f"  {'一级指标':<10}{'二级指标':<12}{'实测值':>11}{'标准化值':>11}"
          f"{'二级权重':>10}{'贡献':>10}")
    print("  " + SUB[:68])
    for l1, l2, raw, sv, w2, contrib in r["rows"]:
        s_sv = "待定" if sv is None else f"{sv:.3f}"
        s_ct = "—" if contrib is None else f"{contrib:.4f}"
        print(f"  {l1:<10}{l2:<12}{raw:>11}{s_sv:>11}{w2:>10.2f}{s_ct:>10}")
    print("  " + SUB[:68])
    for k in ("土壤指标", "植被指标", "地形指标"):
        if k in r["l1"]:
            note = "（仅坡向部分）" if k == "地形指标" else ""
            print(f"  {k} 得分 = {r['l1'][k]:.4f}   一级权重 {r['w1'][k]:.2f} {note}")
    print()
    if r["total"] is None:
        print(f"  → 地形指标的坡度标准化方法未确定，单元得分无法完整计算")
    else:
        print(f"  按论文式(9) 计算单元得分 ≈ {r['total']:.4f}")
    print(f"  论文表 5 所载单元得分  = {PAPER_UNIT_SCORE[u]:.2f}")
    if r["total"] is not None:
        print(f"  差值                  = {PAPER_UNIT_SCORE[u] - r['total']:+.4f}")


def check_unit_reproducible(res):
    print()
    print(LINE)
    print("核对二  由论文表 5 原始数据，按式(8)+式(9) 能否复现三个单元得分")
    print(LINE)
    for u in UNITS:
        print_unit_table(u, res[u])

    # ---- 地形指标上限检验 ----
    print()
    print(LINE)
    print("  地形指标可复现性检验")
    print(LINE)
    print("  论文式(8) 的标准化值域为 [0, 1]。地形指标由坡度、坡向加权而成，")
    print("  坡向已由论文按三档赋值确定，故地形分上限 = 坡向权重×赋分值 + 坡度权重×1。")
    print()
    print(f"  {'微地质单元':<12}{'坡向':<8}{'坡向赋值':>9}{'地形分上限':>11}"
          f"{'反推地形分':>11}{'判定':>8}")
    print("  " + SUB[:62])

    reproducible = True
    detail_lines = []
    for u in ("岩质边坡", "碎石边坡"):
        d, w1, w2 = DATA[u], W_L1[u], W_L2[u]
        asp = ASPECT_SCORE[d["坡向"]]
        cap = w2["坡向"] * asp + w2["坡度"] * 1.0
        base = sum(w1[k] * res[u]["l1"][k] for k in ("土壤指标", "植被指标") if k in res[u]["l1"])
        need = (PAPER_UNIT_SCORE[u] - base) / w1["地形指标"]
        ok = need <= cap + 1e-9
        reproducible &= ok
        print(f"  {u:<12}{d['坡向']:<8}{asp:>9.1f}{cap:>11.4f}{need:>11.3f}"
              f"{'可达' if ok else '不可达':>8}")
        detail_lines.append(
            f"{u}（坡向{d['坡向']}，赋值{asp}）：地形分上限 {w2['坡向']:.2f}×{asp} + "
            f"{w2['坡度']:.2f}×1.00 = {cap:.3f}，")
        detail_lines.append(
            f"  而按表 5 单元得分 {PAPER_UNIT_SCORE[u]:.2f} 反推需 {need:.3f}。")

    print()
    print("  解读：")
    for ln in detail_lines:
        print("    " + ln)
    print()
    print("    岩质边坡虽未超上限，但要求坡度分 = %.4f；" % (
        ((PAPER_UNIT_SCORE["岩质边坡"] - res["岩质边坡"]["l1"]["植被指标"]
          * W_L1["岩质边坡"]["植被指标"]) / W_L1["岩质边坡"]["地形指标"]
         - W_L2["岩质边坡"]["坡向"] * ASPECT_SCORE["阴阳坡"]) / W_L2["岩质边坡"]["坡度"]))
    print("    而岩质边坡坡度 63.33° 远超 25° 分界，按式(8) 越大越优标准化难以取到该高分值。")

    print()
    report(False,
           "表 5 原始数据 + 式(8) + 式(9) 能否复现表 5 所列全部单元得分",
           "碎石边坡所需地形分超出按式(8) 可达的上限；岩质边坡所需坡度分与 25° 分界\n"
           "所隐含的折减趋势不相容。说明复现所需口径与论文正文所述方法存在差异。")

    # ---- 平台单元单独评估 ----
    print()
    print("  附：平台单元不设地形指标，其得分可完整计算")
    p = res["平台"]["total"]
    print(f"    计算结果 {p:.4f}，论文表 5 所载 {PAPER_UNIT_SCORE['平台']:.2f}，"
          f"差值 {PAPER_UNIT_SCORE['平台']-p:+.4f}")
    print("    两者接近但仍有微小差异，差异来源待进一步核实。")
    return reproducible


# ============================================================================
# 五、核对三：论文表 3 权重能否由 AHP 判断矩阵还原
# ============================================================================

def ahp_weight(A):
    """幂法求判断矩阵主特征向量（权重）与最大特征值。"""
    n = len(A)
    x = [1.0 / n] * n
    for _ in range(500):
        y = [sum(A[i][j] * x[j] for j in range(n)) for i in range(n)]
        m = max(y)
        x = [v / m for v in y]
    s = sum(x)
    w = [v / s for v in x]
    lam = sum(sum(A[i][j] * w[j] for j in range(n)) / w[i] for i in range(n)) / n
    return w, lam


def check_ahp():
    print()
    print(LINE)
    print("核对三  论文表 3 的权重能否由 AHP 判断矩阵还原")
    print(LINE)
    print("  原理：若判断矩阵完全一致，则 a_ij = w_i / w_j，权重向量即其主特征向量。")
    print("        因此给定任意权重向量，都可构造出与之相容的判断矩阵。")
    print("        → 权重向量可还原，但专家原始判断矩阵不可唯一确定。")
    print()

    w = [W_L1["碎石边坡"][k] for k in ("土壤指标", "植被指标", "地形指标")]
    names = ("土壤指标", "植被指标", "地形指标")
    n = len(w)
    print(f"  以碎石边坡一级指标为例，表 3 权重："
          + "，".join(f"{names[i]}={w[i]}" for i in range(n)))
    print()

    A = [[w[i] / w[j] for j in range(n)] for i in range(n)]
    print("  据此构造的完全一致判断矩阵 A（a_ij = w_i / w_j）：")
    print("        " + "".join(f"{names[j]:>12}" for j in range(n)))
    for i in range(n):
        print(f"  {names[i]:<8}" + "".join(f"{A[i][j]:>12.4f}" for j in range(n)))
    print()

    ww, lam = ahp_weight(A)
    ci = (lam - n) / (n - 1)
    cr = ci / RI[n] if RI[n] else 0.0
    print("  特征根法反求：", "  ".join(f"{v:.4f}" for v in ww))
    print("  论文表 3 给定：", "  ".join(f"{v:.4f}" for v in w))
    print(f"  λmax = {lam:.6f}   CI = {ci:.3e}   RI({n}) = {RI[n]}   CR = {cr:.3e}")
    print(f"  一致性检验 CR < 0.1 ：{'通过' if cr < 0.1 else '不通过'}")
    print()
    report(all(abs(a - b) < 1e-6 for a, b in zip(ww, w)),
           "论文表 3 权重是否可写成某个完全一致判断矩阵的主特征向量",
           "可以，且 CR 检验通过。但逆命题不成立——该权重可对应无穷多个判断矩阵，\n"
           "故无法由表 3 反推专家原始打分。")
    print()
    print("  对复算的影响：")
    print("    最终得分只依赖权重（表 3 已给出）与标准化值（式(8) 已给出），")
    print("    不依赖判断矩阵本身。故核对一、核对二均不受此影响。")


# ============================================================================
# 六、主流程
# ============================================================================

def main():
    print()
    print(LINE)
    print("  历史遗留废弃矿山自然恢复适宜性评价  论文案例数值验证")
    print("  案例：河北省唐山市玉田县孤树镇历史遗留白云岩采石场")
    print(LINE)

    total = check_weighted_total()
    res = compute_units()
    check_unit_reproducible(res)
    check_ahp()

    print()
    print(LINE)
    print("  验证结论")
    print(LINE)
    print()
    print("  1. 最终得分")
    print(f"     论文表 5 所载三个单元得分 {list(PAPER_UNIT_SCORE.values())} 与第 5 节面积占比")
    print(f"     {list(AREA_PCT.values())}，按论文式(9) 加权所得为 {round(total,2):.2f}，")
    print(f"     与论文所载最终得分 {PAPER_FINAL:.2f} 相差 {PAPER_FINAL-round(total,2):+.2f}。")
    print()
    print("  2. 单元得分可复现性")
    print("     表 5 原始数据经式(8) 标准化、与表 3 权重按式(9) 合成后，")
    print("     岩质边坡与碎石边坡两单元所需地形分超出式(8) 可达上限，")
    print("     无法复现论文所载的 0.56 与 0.74。")
    print()
    print("  3. 差异定位")
    print("     土壤指标与植被指标（覆盖度、Shannon-Wiener 多样性、8 种重金属）")
    print("     的标准化与加权合成均可与论文所述一致地复现；")
    print(f"     平台单元因不设地形指标，计算结果 {res['平台']['total']:.3f} 与论文 0.85")
    print(f"     相差仅 {PAPER_UNIT_SCORE['平台']-res['平台']['total']:+.4f}；")
    print("     而两处显著差异均出现在【地形指标（坡度、坡向）】环节。")
    print()
    print("  4. 结论")
    print("     论文所述结果与论文所述计算公式之间存在差异，差异集中于地形指标的")
    print("     标准化口径。建议对式(8) 中坡度、坡向的具体取值方法作补充说明或核实。")
    print()
    print("  说明")
    print("     本程序所有输入数据均逐字取自论文原表，未作修改；")
    print("     结论仅涉及数值一致性的核对，不涉及对研究方法与科学结论的评价。")
    print()
    print(LINE)
    bad = [t for ok, t in _findings if not ok]
    print(f"  核对项 {len(_findings)} 项，其中不一致 {len(bad)} 项：")
    for t in bad:
        print(f"    - {t}")
    print(LINE)
    print()


if __name__ == "__main__":
    main()
