# -*- coding: utf-8 -*-
"""指标数据采集与管理 —— 路由与页面逻辑。

按微地质单元组织录入；系统按单元类型自动决定应录入哪些指标
（岩质边坡无土壤指标、平台无地形指标）。
"""
import io
import json

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, send_file)

from app.forms import EmptyForm
from app.models import db, MinePatch, MicroUnit, IndicatorData
from app.utils.constants import HEAVY_METALS, ASPECT_TYPES, UNIT_ENABLED_INDICATORS
from app.services import import_service as imp

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
    unit = db.get_or_404(MicroUnit, unit_id)
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


# ---------------------------- 批量导入 ----------------------------

@bp.route("/import", methods=["GET", "POST"])
def import_data():
    """批量导入指标数据（CSV / Excel）。"""
    patches = MinePatch.query.order_by(MinePatch.id.desc()).all()
    form = EmptyForm()
    report = None

    if request.method == "POST" and form.validate_on_submit():
        patch_id = request.form.get("patch_id", type=int)
        patch = db.session.get(MinePatch, patch_id) if patch_id else None
        if patch is None:
            flash("请选择矿山图斑", "error")
            return redirect(url_for("indicator.import_data"))

        file = request.files.get("datafile")
        if file is None or not file.filename:
            flash("请选择要导入的文件", "error")
            return redirect(url_for("indicator.import_data"))
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("csv", "xlsx", "xls"):
            flash("仅支持 CSV 或 Excel（.xlsx/.xls）文件", "error")
            return redirect(url_for("indicator.import_data"))

        units = MicroUnit.query.filter_by(patch_id=patch.id).all()
        unit_map = {}
        for u in units:
            unit_map.setdefault(u.unit_type, u)
        if not unit_map:
            flash("该图斑尚未划分微地质单元，请先划分后再导入", "error")
            return redirect(url_for("indicator.import_data"))

        try:
            parsed, errors = imp.parse_upload(file.filename, file.stream, unit_map)
        except Exception as e:
            flash("文件解析失败：%s" % e, "error")
            return redirect(url_for("indicator.import_data"))

        saved = 0
        for rec in parsed:
            unit = unit_map[rec["unit_type"]]
            ind = IndicatorData.query.filter_by(unit_id=unit.id).first()
            if ind is None:
                ind = IndicatorData(unit_id=unit.id)
                db.session.add(ind)
            f = rec["fields"]
            for key in ("soil_ratio", "thickness", "ph", "organic_matter",
                        "coverage", "shannon", "slope", "aspect"):
                if key in f:
                    setattr(ind, key, f[key])
            if rec["heavy_metals"]:
                ind.heavy_metals = json.dumps(rec["heavy_metals"],
                                              ensure_ascii=False)
            saved += 1
        db.session.commit()
        report = {"patch": patch.name, "saved": saved, "errors": errors,
                  "total": len(parsed) + len(
                      [e for e in errors if e.startswith("第 ")])}
        if saved:
            flash("已导入 %d 个微地质单元的指标数据" % saved, "ok")
        else:
            flash("没有可导入的数据行，请检查文件内容", "error")

    return render_template("indicator/import.html", patches=patches,
                           form=form, report=report, headers=imp.HEADERS)


@bp.route("/import/template")
def import_template():
    """下载导入模板（CSV，含一行示例）。"""
    csv_text = imp.build_template_csv()
    data = csv_text.encode("utf-8-sig")     # 带 BOM，便于 Excel 正确识别中文
    return send_file(io.BytesIO(data), as_attachment=True,
                     download_name="指标数据导入模板.csv",
                     mimetype="text/csv")
