# -*- coding: utf-8 -*-
"""标准化参数与必填项：让界面上能改的东西真正参与计算。

以前有个说不通的地方：图斑的「参照生态系统基准」、指标定义里的「理想取值」
和「启用单元」在界面上都能改、也能落库，**但计算链只读代码常量**
（`app/utils/constants.py`），从不查这两张表。于是报告里写着「基准 60%」，
实际按常量 75% 算，同一份报告两个口径。

现在统一从这里取：
- 基准值（植被覆盖度、Shannon）来自图斑的 `reference_ecosystems`；
- 各指标的理想取值来自 `indicators.ideal_value`（能解析成数字的才覆盖，
  像「5~9」「25° 分界」这种区间/规则型仍按代码里的算法处理）；
- 启用单元来自 `indicators.enabled_units`（岩质边坡无土壤、平台无地形）。

库里没有行、或值不是数字时一律回落到代码常量 —— 所以历史数据与
`验证数据/` 里的 8 个算例结果不会因为这次改动而变化。
"""
from app.models import Indicator, ReferenceEcosystem
from app.utils.constants import (
    UNIT_TYPES, IDEAL_SOIL_RATIO, IDEAL_THICKNESS, IDEAL_ORGANIC,
    IDEAL_COVERAGE, IDEAL_SHANNON, HEAVY_METAL_LIMIT, HEAVY_METALS,
)

# 二级指标编码 → 标准化参数名（同时也是 IndicatorData 的字段名）
NUMERIC_IDEALS = {
    "soil_ratio": ("soil_ratio", IDEAL_SOIL_RATIO),
    "thickness": ("thickness", IDEAL_THICKNESS),
    "organic_matter": ("organic_matter", IDEAL_ORGANIC),
    "coverage": ("coverage", IDEAL_COVERAGE),
    "shannon": ("shannon", IDEAL_SHANNON),
}
# 重金属编码 → 金属名
METAL_CODES = {"hm_" + m: m for m in HEAVY_METALS}

# 必填的实测字段（污染指标按论文注记允许「未检测」，故不在必填之列）
REQUIRED_CODES = ["soil_ratio", "thickness", "ph", "organic_matter",
                  "coverage", "shannon", "slope", "aspect"]

# 字段 → 界面上的中文名，用于提示「缺什么」
FIELD_LABELS = {
    "soil_ratio": "土石比", "thickness": "土层厚度", "ph": "pH",
    "organic_matter": "有机质", "coverage": "植被覆盖度",
    "shannon": "生物多样性（Shannon）", "slope": "坡度", "aspect": "坡向",
}


def _numeric(text):
    """把理想取值的文本解析成数字；区间、规则型返回 None。"""
    if text is None:
        return None
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


class UnitSettings:
    """一个图斑上下文的标准化参数。空对象表示「全部按代码常量」。"""

    def __init__(self, params=None, enabled=None):
        self.params = params or {}          # 覆盖用的标准值
        self.enabled = enabled or {}        # 单元类型 → 启用的二级指标编码集合

    def ideal(self, code, fallback):
        """取某指标的理想取值：库里有数字就用库里的，否则用常量。"""
        value = self.params.get(code)
        return fallback if value is None else value

    def group_enabled(self, unit_type, l1_name, l1_code):
        """该单元类型下某个一级指标是否启用（库里没配就按代码常量）。"""
        codes = self.enabled.get(unit_type)
        if codes is None:
            return None                     # 交给调用方按常量判断
        return l1_code in codes

    def enabled_codes(self, unit_type):
        """该单元类型启用的全部二级指标编码；库里没配返回 None。"""
        return self.enabled.get(unit_type)

    def required_codes(self, unit_type):
        """该单元类型必填的实测字段。

        按「启用的二级指标」推导：岩质边坡不启用土壤，平台不启用地形。
        库里没配该项时用代码常量里的结构性规则。
        """
        from app.utils.constants import UNIT_ENABLED_INDICATORS
        codes = self.enabled.get(unit_type)
        if codes is None:
            groups = UNIT_ENABLED_INDICATORS.get(unit_type, ())
            l2_by_group = {
                "土壤指标": ["soil_ratio", "thickness", "ph", "organic_matter"],
                "植被指标": ["coverage", "shannon"],
                "地形指标": ["slope", "aspect"],
            }
            codes = {c for g in groups for c in l2_by_group.get(g, [])}
        return [c for c in REQUIRED_CODES if c in codes]

    def missing_fields(self, unit_type, data):
        """返回该单元缺哪些必填项（中文名列表）。"""
        missing = []
        for code in self.required_codes(unit_type):
            value = data.get(code)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing.append(FIELD_LABELS.get(code, code))
        return missing

    def undetected_metals(self, data):
        """按论文注记，未检测的重金属按「未受污染」计入；这里列出是哪些。"""
        measured = data.get("heavy_metals") or {}
        return [m for m in HEAVY_METALS if measured.get(m) is None]


def for_patch(patch_id):
    """读某个图斑的标准化参数；库里有什么就用什么，没有就用常量。

    优先级：图斑自己的参照生态系统基准 **高于** 指标定义里的全局理想取值 ——
    前者说的是「这个图斑的参照生态系统是什么样」，后者是「一般情况下的理想值」，
    越具体的越应该说了算。两者都优先于代码常量。
    """
    params = {}
    enabled = {}
    for ind in Indicator.query.all():
        code = ind.code
        if code in NUMERIC_IDEALS:
            value = _numeric(ind.ideal_value)
            if value is not None:
                params[code] = value
        elif code in METAL_CODES:
            # 重金属的「理想值」存的是限值，作为越小越优的极值使用
            value = _numeric(ind.ideal_value)
            if value is not None:
                params[code] = value
        units = (ind.enabled_units or "").strip()
        if units:
            for unit in UNIT_TYPES:
                if unit in units:
                    enabled.setdefault(unit, set()).add(code)

    # 再用该图斑的参照生态系统基准覆盖：它是「这个图斑的参照生态系统」，
    # 比指标定义里的全局理想取值更具体，应该它说了算。
    ref = ReferenceEcosystem.query.filter_by(patch_id=patch_id).first()
    if ref is not None:
        if ref.coverage_benchmark is not None:
            params["coverage"] = float(ref.coverage_benchmark)
        if ref.shannon_benchmark is not None:
            params["shannon"] = float(ref.shannon_benchmark)

    return UnitSettings(params=params, enabled=enabled)


def metal_limits(settings):
    """重金属的极值表：库里有配置的用库里的，其余用常量。"""
    limits = dict(HEAVY_METAL_LIMIT)
    for code, metal in METAL_CODES.items():
        value = settings.params.get(code) if settings else None
        if value is not None:
            limits[metal] = value
    return limits
