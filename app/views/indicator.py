# -*- coding: utf-8 -*-
"""M7 指标数据采集与管理 —— 路由与页面逻辑。

按微地质单元组织录入；系统按单元类型自动决定应录入哪些指标
（岩质边坡无土壤指标、平台无地形指标）。
"""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.forms import EmptyForm
from app.models import db, MinePatch, MicroUnit, IndicatorData
from app.utils.constants import HEAVY_METALS, ASPECT_TYPES, UNIT_ENABLED_INDICATORS

bp = Blueprint("indicator", __name__, url_prefix="/indicator")

# 指标字段定义：字段名 -> (中文名, 单位, 是否可选)
SOIL_FIELDS = [
    ("soil_ratio", "土石比", ""),
    ("thickness", "土层厚度", "cm"),
    ("ph", "pH", ""),
    ("organic_matter", "有机质", "g/kg"),
]
VEG_FIELDS = [
    ("coverage", "植被覆盖度", "%"),
    ("shannon", "Shannon-Wiener 多样性指数", ""),
]
TERRAIN_FIELDS = [
    ("slope", "坡度", "°"),
    ("aspect", "坡向", ""),
]


def unit_field_config(unit_type):
    """根据单元类型返回需录入的字段分组。"""
    enabled = UNIT_ENABLED_INDICATORS.get(unit_type, ())
    groups = []
    if "土壤指标" in enabled:
        groups.append(("土壤指标", SOIL_FIELDS, True))   # True = 含重金属
    if "植被指标" in enabled:
        groups.append(("植被指标", VEG_FIELDS, False))
    if "地形指标" in enabled:
        groups.append(("地形指标", TERRAIN_FIELDS, False))
    return groups


@bp.route("/")
def index():
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    return render_template("indicator/index.html", patches=patches)


@bp.route("/<int:unit_id>", methods=["GET", "POST"])
def edit(unit_id):
    unit = MicroUnit.query.get_or_404(unit_id)
    ind = IndicatorData.query.filter_by(unit_id=unit.id).first()
    form = EmptyForm()
    groups = unit_field_config(unit.unit_type)

    if request.method == "POST" and form.validate_on_submit():
        def f(name, cast=float):
            v = request.form.get(name, "").strip()
            return cast(v) if v != "" else None

        heavy = {}
        for m in HEAVY_METALS:
            v = f("hm_" + m)
            if v is not None:
                heavy[m] = v

        if ind is None:
            ind = IndicatorData(unit_id=unit.id)
            db.session.add(ind)

        ind.soil_ratio = f("soil_ratio")
        ind.thickness = f("thickness")
        ind.ph = f("ph")
        ind.organic_matter = f("organic_matter")
        ind.heavy_metals = json.dumps(heavy, ensure_ascii=False) if heavy else None
        ind.coverage = f("coverage")
        ind.shannon = f("shannon")
        ind.slope = f("slope")
        ind.aspect = request.form.get("aspect", "").strip() or None

        db.session.commit()
        flash("指标数据已保存", "ok")
        return redirect(url_for("indicator.index"))

    # 组装当前值供模板回显
    current = {}
    if ind:
        current = {
            "soil_ratio": ind.soil_ratio, "thickness": ind.thickness,
            "ph": ind.ph, "organic_matter": ind.organic_matter,
            "coverage": ind.coverage, "shannon": ind.shannon,
            "slope": ind.slope, "aspect": ind.aspect,
        }
        current["heavy"] = ind.heavy_metals_dict()

    return render_template("indicator/edit.html",
                           unit=unit, form=form, groups=groups,
                           heavy_metals=HEAVY_METALS,
                           aspect_types=ASPECT_TYPES, current=current)
