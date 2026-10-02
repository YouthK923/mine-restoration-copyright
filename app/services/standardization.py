# -*- coding: utf-8 -*-
"""指标标准化（的一部分）。

按标准化公式实现：
    x' = (x - x_min) / (x_max - x_min)
按指标性质分为四类：越大越优 / 越小越优 / 适中 / 离散赋值。
所有理想极值取自 app.utils.constants，可配置。
"""
from app.utils.constants import (
    IDEAL_SOIL_RATIO, IDEAL_THICKNESS, IDEAL_PH_RANGE, IDEAL_ORGANIC,
    IDEAL_COVERAGE, IDEAL_SHANNON, HEAVY_METAL_LIMIT,
    HEAVY_METAL_EQUAL_WEIGHT, SLOPE_BREAK, ASPECT_SCORES,
    PH_TOL_LOW, PH_TOL_HIGH,
)


def std_benefit(value, ideal):
    """越大越优指标标准化：以理想值为上限，按比例给分，饱和于 [0,1]。"""
    if value is None:
        return None
    return max(0.0, min(1.0, value / ideal))


def std_cost(value, extreme):
    """越小越优指标标准化：以极值为参考，线性折减至 [0,1]。"""
    if value is None:
        return None
    return max(0.0, min(1.0, 1.0 - value / extreme))


def std_mid_ph(value, lo, hi, tol_lo=PH_TOL_LOW, tol_hi=PH_TOL_HIGH):
    """适中型指标标准化（pH）：理想区间内取 1，区间外线性衰减。"""
    if value is None:
        return None
    if lo <= value <= hi:
        return 1.0
    if value > hi:
        return max(0.0, (tol_hi - value) / (tol_hi - hi))
    return max(0.0, (value - tol_lo) / (lo - tol_lo))


def std_slope(value, break_point=SLOPE_BREAK, upper=90.0):
    """坡度标准化。

    取值规定：以 25° 为陡坡重要分界。25° 及以下记满分 1，
    超过 25° 线性折减，90° 记 0。
    """
    if value is None:
        return None
    if value <= break_point:
        return 1.0
    return max(0.0, (upper - value) / (upper - break_point))


def aspect_score(aspect):
    """坡向离散赋值：阳坡 0.2 / 阴阳坡 0.6 / 阴坡 1.0（取值规定）。"""
    if aspect is None:
        return None
    return ASPECT_SCORES.get(aspect)


def pollution_score(heavy_metals, limits=None):
    """污染指标：8 种重金属等权（各 0.125）合成。

    方法约定：未检测 Cr、Zn 的，从矿山类型看未受污染，按无污染(=1)处理。
    heavy_metals : dict，键为金属名，值为含量 mg/kg；缺失键视为未检测。
    limits : 可选，金属 → 极值；不传则用代码常量（界面改过就传库里的值）。
    """
    table = limits or HEAVY_METAL_LIMIT
    total = 0.0
    for metal, extreme in table.items():
        value = heavy_metals.get(metal)
        total += std_cost(value, extreme) if value is not None else 1.0
    return total / len(table)


def standardize_unit(unit_type, data, weights=None, settings=None):
    """对单个微地质单元的全部指标做标准化。

    参数
    ----
    unit_type : str，岩质边坡 / 碎石边坡 / 平台
    data : dict，实测数据，字段见接口契约：
        soil_ratio, thickness, ph, organic_matter, heavy_metals(dict),
        coverage, shannon, slope, aspect
    weights : dict，该单元类型的权重（app.utils.constants.DEFAULT_WEIGHTS 结构），
              未提供时用默认值。
    settings : app.services.unit_config.UnitSettings，图斑级的基准值与理想取值。
              不传则全部按代码常量 —— 历史数据与验证算例走这条路径，结果不变。

    返回
    ----
    dict：{ 一级指标: { 二级指标: (实测值, 标准化值, 权重, 贡献) } }
    标准化值可能为 None，表示该指标不适用或方法待定。
    """
    from app.utils.constants import DEFAULT_WEIGHTS
    from app.services import unit_config as uc
    if weights is None:
        weights = DEFAULT_WEIGHTS[unit_type]
    if settings is None:
        settings = uc.UnitSettings()

    # 理想取值：库里有数字就用库里的，否则用常量
    def ideal(code, fallback):
        return settings.ideal(code, fallback)

    l1_enabled = weights["l1"].keys()
    l2w = weights["l2"]
    result = {}

    # 一级指标是否启用：库里配过就按库里的（界面上的「启用单元」），没配按常量
    def group_on(l1_name, l1_code):
        return settings.group_enabled(unit_type, l1_name, l1_code) is not False

    # ---- 土壤指标 ----
    if "土壤指标" in l1_enabled and group_on("土壤指标", "soil"):
        result["土壤指标"] = {
            "土石比": (data.get("soil_ratio"),
                       std_benefit(data.get("soil_ratio"),
                                   ideal("soil_ratio", IDEAL_SOIL_RATIO)),
                       l2w["土壤指标"]["土石比"]),
            "土层厚度": (data.get("thickness"),
                        std_benefit(data.get("thickness"),
                                    ideal("thickness", IDEAL_THICKNESS)),
                        l2w["土壤指标"]["土层厚度"]),
            "pH": (data.get("ph"),
                   std_mid_ph(data.get("ph"), *IDEAL_PH_RANGE),
                   l2w["土壤指标"]["pH"]),
            "有机质": (data.get("organic_matter"),
                      std_benefit(data.get("organic_matter"),
                                  ideal("organic_matter", IDEAL_ORGANIC)),
                      l2w["土壤指标"]["有机质"]),
            "污染指标": (data.get("heavy_metals") or {},
                        pollution_score(data.get("heavy_metals") or {},
                                        uc.metal_limits(settings)),
                        l2w["土壤指标"]["污染指标"]),
        }

    # ---- 植被指标 ----
    if "植被指标" in l1_enabled and group_on("植被指标", "veg"):
        result["植被指标"] = {
            "植被覆盖度": (data.get("coverage"),
                          std_benefit(data.get("coverage"),
                                      ideal("coverage", IDEAL_COVERAGE)),
                          l2w["植被指标"]["植被覆盖度"]),
            "生物多样性": (data.get("shannon"),
                          std_benefit(data.get("shannon"),
                                      ideal("shannon", IDEAL_SHANNON)),
                          l2w["植被指标"]["生物多样性"]),
        }

    # ---- 地形指标 ----
    if "地形指标" in l1_enabled and group_on("地形指标", "terrain"):
        result["地形指标"] = {
            "坡度": (data.get("slope"),
                     std_slope(data.get("slope")),
                     l2w["地形指标"]["坡度"]),
            "坡向": (data.get("aspect"),
                     aspect_score(data.get("aspect")),
                     l2w["地形指标"]["坡向"]),
        }

    return result
