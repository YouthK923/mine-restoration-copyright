# -*- coding: utf-8 -*-
"""指标定义维护（M6）。

把论文表 2/表 3 的指标体系写入 indicators 表，使指标名称、单位、
理想值与取值依据可在界面上查看维护，而不再只存在于代码常量中。

代码常量（app.utils.constants）仍是计算时的**权威取值来源**；
本表用于展示、核对与记录取值依据。二者由 seed_indicators() 保持同步。
"""
from app.models import db, Indicator
from app.utils.constants import (
    UNIT_TYPES, UNIT_ENABLED_INDICATORS, IDEAL_SOIL_RATIO, IDEAL_THICKNESS,
    IDEAL_PH_RANGE, IDEAL_ORGANIC, IDEAL_COVERAGE, IDEAL_SHANNON,
    HEAVY_METAL_LIMIT, SLOPE_BREAK, ASPECT_SCORES,
)

ALL_UNITS = ",".join(UNIT_TYPES)

# (code, name, level, parent, unit, ideal_value, ideal_type, enabled_units, desc, is_constraint)
TREE = [
    # ---- 一级指标 ----
    ("soil", "土壤指标", 1, None, None, None, None, "碎石边坡,平台", "论文表 2 评价指标之一级指标", False),
    ("veg", "植被指标", 1, None, None, None, None, ALL_UNITS, "论文表 2 评价指标之一级指标", False),
    ("terrain", "地形指标", 1, None, None, None, None, "岩质边坡,碎石边坡", "论文表 2 评价指标之一级指标", False),

    # ---- 二级指标：土壤 ----
    ("soil_ratio", "土石比", 2, "soil", "—", str(IDEAL_SOIL_RATIO), "benefit", "碎石边坡,平台",
     "论文 4.2.2 节：理想值 0.8，根据矿山修复实际情况确定", False),
    ("thickness", "土层厚度", 2, "soil", "cm", str(IDEAL_THICKNESS), "benefit", "碎石边坡,平台",
     "论文 4.2.2 节：理想值 20 cm", False),
    ("ph", "pH", 2, "soil", "—", "%g~%g" % IDEAL_PH_RANGE, "mid", "碎石边坡,平台",
     "论文 4.2.2 节：pH 用适中指标的标准化方法，理想区间 %g~%g" % IDEAL_PH_RANGE, False),
    ("organic_matter", "有机质", 2, "soil", "g/kg", str(IDEAL_ORGANIC), "benefit", "碎石边坡,平台",
     "《全国第二次土壤普查养分等级划分标准》二等（较丰富）最低值 30 g/kg", False),
    ("pollution", "污染指标", 2, "soil", "mg/kg", "见三级指标", "cost", "碎石边坡,平台",
     "同时作为限制性指标与评价指标；8 种重金属等权合成（各 0.125）", True),

    # ---- 二级指标：植被 ----
    ("coverage", "植被覆盖度", 2, "veg", "%", str(IDEAL_COVERAGE), "benefit", ALL_UNITS,
     "论文 4.2.2 节：参照生态系统取值 75%", False),
    ("shannon", "生物多样性", 2, "veg", "—", str(IDEAL_SHANNON), "benefit", ALL_UNITS,
     "Shannon-Wiener 多样性指数，参照生态系统取值 0.7", False),

    # ---- 二级指标：地形 ----
    ("slope", "坡度", 2, "terrain", "°", "%g° 分界" % SLOPE_BREAK, "cost", "岩质边坡,碎石边坡",
     "论文 4.2.2 节引《新一轮退耕还林还草总体方案》发改西部〔2014〕1772 号：25° 为陡坡重要分界", False),
    ("aspect", "坡向", 2, "terrain", "—", "阳坡0.2/阴阳坡0.6/阴坡1.0", "discrete", "岩质边坡,碎石边坡",
     "论文 4.2.2 节：阴坡及半阴坡水分条件更优，故赋值高于阳坡", False),
]

# 污染指标下的三级指标（8 种重金属）
for _m, _limit in HEAVY_METAL_LIMIT.items():
    TREE.append((
        "hm_" + _m, _m, 3, "pollution", "mg/kg", str(_limit), "cost",
        "碎石边坡,平台",
        "《绿化种植土壤》CJ/T 340—2016 土壤重金属含量 IV 级最高值 %g mg/kg" % _limit,
        False,
    ))


def seed_indicators():
    """写入/更新指标定义（幂等）。返回写入条数。"""
    code_map = {
        "benefit": "越大越优", "cost": "越小越优",
        "mid": "适中型", "discrete": "离散赋值",
    }
    n = 0
    for (code, name, level, parent, unit, ideal, itype, units, desc, is_con) in TREE:
        ind = Indicator.query.filter_by(code=code).first()
        if ind is None:
            ind = Indicator(code=code)
            db.session.add(ind)
        ind.name = name
        ind.level = level
        ind.parent_code = parent
        ind.unit = unit
        ind.ideal_value = ideal
        ind.ideal_type = itype
        ind.enabled_units = units
        ind.description = desc
        ind.is_constraint = is_con
        ind.is_evaluative = (level in (2, 3))
        n += 1
    db.session.commit()
    return n


def ideal_type_label(code):
    return {"benefit": "越大越优", "cost": "越小越优",
            "mid": "适中型", "discrete": "离散赋值"}.get(code, code or "—")
