# -*- coding: utf-8 -*-
"""指标体系与 AHP 权重 —— 路由与页面逻辑。"""
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.forms import AHPSelectForm, EmptyForm
from app.models import db, Indicator, ExpertMatrix, WeightScheme
from app.utils.constants import DEFAULT_WEIGHTS, UNIT_TYPES
from app.services import ahp_service as ahp
from app.services import indicator_service as ind_svc
from app.services import weight_service as ws

bp = Blueprint("ahp", __name__, url_prefix="/ahp")

# 一次计算的权重结果对应的指标编码：名称 → 编码
_L1_CODE = {"土壤指标": "soil", "植被指标": "veg", "地形指标": "terrain"}
_L2_CODE = {
    ("土壤指标", "土石比"): "soil_ratio",
    ("土壤指标", "土层厚度"): "thickness",
    ("土壤指标", "pH"): "ph",
    ("土壤指标", "有机质"): "organic_matter",
    ("土壤指标", "污染指标"): "pollution",
    ("植被指标", "植被覆盖度"): "coverage",
    ("植被指标", "生物多样性"): "shannon",
    ("地形指标", "坡度"): "slope",
    ("地形指标", "坡向"): "aspect",
}


def to_code_pairs(unit_type, level, l1, names, weights):
    """把一次 AHP 计算的权重结果转成「指标编码 → 权重」，便于落库。"""
    pairs = []
    for name, w in zip(names, weights):
        if level == 1:
            code = _L1_CODE.get(name)
        else:
            code = _L2_CODE.get((l1, name))
        if code:
            pairs.append((code, w))
    return pairs


def indicator_list(unit_type, level, l1=None):
    """返回 (指标名称列表, 默认权重列表)。

    level=1 时返回一级指标；level=2 时返回指定一级指标下的二级指标。
    """
    weights = DEFAULT_WEIGHTS[unit_type]
    if level == 1:
        names = list(weights["l1"].keys())
        vec = [weights["l1"][n] for n in names]
        return names, vec
    # level == 2
    l2 = weights["l2"][l1]
    names = list(l2.keys())
    vec = [l2[n] for n in names]
    return names, vec


def l1_choices(unit_type):
    """某单元类型的一级指标名称列表（用于二级指标录入时选择父指标）。"""
    return list(DEFAULT_WEIGHTS[unit_type]["l1"].keys())


@bp.route("/", methods=["GET", "POST"])
def index():
    form = AHPSelectForm()
    # 先根据请求中的单元类型填充 l1 选项，再进行表单校验
    unit = request.form.get("unit_type") or form.unit_type.choices[0][0]
    form.l1.choices = [(n, n) for n in l1_choices(unit)]
    if form.validate_on_submit():
        unit_type = form.unit_type.data
        level = int(form.level.data)
        if level == 1:
            return redirect(url_for("ahp.matrix", unit_type=unit_type, level=1))
        if not form.l1.data:
            flash("选择「二级指标」时，请同时选择所属的一级指标", "error")
            return render_template("ahp/index.html", form=form,
                                   weight_rows=ws.summary())
        return redirect(url_for("ahp.matrix", unit_type=unit_type,
                                level=2, l1=form.l1.data))
    return render_template("ahp/index.html", form=form,
                           weight_rows=ws.summary())


@bp.route("/matrix", methods=["GET", "POST"])
def matrix():
    unit_type = request.values.get("unit_type")
    level = int(request.values.get("level", 1))
    l1 = request.values.get("l1")

    if unit_type not in DEFAULT_WEIGHTS:
        flash("无效的微地质单元类型", "error")
        return redirect(url_for("ahp.index"))

    names, vec = indicator_list(unit_type, level, l1)
    n = len(names)
    form = EmptyForm()

    # 预填默认值：论文表 3 权重对应的完全一致矩阵 a_ij = w_i / w_j
    default = [[round(vec[i] / vec[j], 4) for j in range(n)] for i in range(n)]

    def compute(upper):
        A = ahp.matrix_from_upper(upper)
        r = ahp.weights_and_consistency(A)
        bad = ahp.find_most_inconsistent(A)
        return {
            "weights": [round(v, 4) for v in r["weights"]],
            "lambda_max": round(r["lambda_max"], 4),
            "ci": r["ci"],
            "cr": r["cr"],
            "consistent": r["consistent"],
            "matrix": [[round(A[i, j], 4) for j in range(n)] for i in range(n)],
            "most_inconsistent": bad,
        }

    result = None
    if request.method == "POST" and form.validate_on_submit():
        action = request.form.get("action", "calc")
        try:
            upper = [float(request.form.get("m_%d_%d" % (i, j), "1"))
                     for i in range(n) for j in range(i + 1, n)]
            result = compute(upper)
        except (ValueError, ZeroDivisionError):
            flash("矩阵输入有误：请填入正数（对角线自动为 1，下三角自动取倒数）", "error")
            return redirect(url_for("ahp.matrix", unit_type=unit_type,
                                    level=level, l1=l1))

        if action == "save":
            if not result["consistent"]:
                flash("一致性比例 CR=%.4f ≥ 0.1，判断矩阵不满足一致性要求，"
                      "请调整后再保存" % result["cr"], "error")
            else:
                pairs = to_code_pairs(unit_type, level, l1, names,
                                      result["weights"])
                scheme, cnt = ws.save_weights(unit_type, pairs)
                flash("已保存并为「%s」生效 %d 项权重（CR=%.4f）。"
                      "此后该单元类型的评价将以此权重计算。"
                      % (unit_type, cnt, result["cr"]), "ok")
                return redirect(url_for("ahp.matrix", unit_type=unit_type,
                                        level=level, l1=l1))
    elif request.values.get("calc") == "1":
        # 按默认（论文表 3）矩阵直接试算，便于一键查看权重与一致性
        result = compute([default[i][j] for i in range(n) for j in range(i + 1, n)])

    _, source_label, custom_scheme = ws.effective_weights(unit_type)
    return render_template(
        "ahp/matrix.html",
        form=form, unit_type=unit_type, level=level, l1=l1,
        names=names, vec=vec, default=default, result=result,
        source_label=source_label, custom_scheme=custom_scheme,
    )


@bp.route("/weights/reset", methods=["POST"])
def weights_reset():
    """删除自定义权重方案，恢复为该单元类型的论文表 3 默认权重。"""
    unit_type = request.form.get("unit_type")
    form = EmptyForm()
    if form.validate_on_submit():
        if unit_type not in DEFAULT_WEIGHTS:
            flash("无效的微地质单元类型", "error")
        else:
            n = ws.reset_weights(unit_type)
            if n:
                flash("已恢复「%s」为论文表 3 默认权重" % unit_type, "ok")
            else:
                flash("「%s」本就是论文表 3 默认权重，无需恢复" % unit_type, "ok")
    return redirect(url_for("ahp.index"))


# ---------------------------- 指标维护 ----------------------------

@bp.route("/indicators")
def indicators():
    """指标定义维护：查看指标树、单位、理想值与取值依据。"""
    if Indicator.query.count() == 0:
        ind_svc.seed_indicators()
    all_ind = Indicator.query.order_by(Indicator.level, Indicator.id).all()
    by_parent = {}
    for i in all_ind:
        by_parent.setdefault(i.parent_code, []).append(i)
    return render_template("ahp/indicators.html", by_parent=by_parent,
                           all_ind=all_ind, unit_types=UNIT_TYPES,
                           type_label=ind_svc.ideal_type_label,
                           form=EmptyForm())


@bp.route("/indicators/<code>/edit", methods=["GET", "POST"])
def indicator_edit(code):
    ind = Indicator.query.filter_by(code=code).first_or_404()
    form = EmptyForm()
    if request.method == "POST" and form.validate_on_submit():
        name = request.form.get("name", "").strip()
        if not name:
            flash("指标名称不能为空", "error")
            return redirect(url_for("ahp.indicator_edit", code=code))
        ind.name = name
        ind.unit = request.form.get("unit", "").strip() or None
        ind.ideal_value = request.form.get("ideal_value", "").strip() or None
        ind.ideal_type = request.form.get("ideal_type") or ind.ideal_type
        units = request.form.getlist("enabled_units")
        ind.enabled_units = ",".join(units) if units else None
        ind.is_constraint = request.form.get("is_constraint") == "1"
        ind.description = request.form.get("description", "").strip() or None
        db.session.commit()
        flash("指标「%s」已保存" % ind.name, "ok")
        return redirect(url_for("ahp.indicators"))
    return render_template("ahp/indicator_edit.html", ind=ind,
                           unit_types=UNIT_TYPES,
                           type_label=ind_svc.ideal_type_label, form=form)


@bp.route("/indicators/reset", methods=["POST"])
def indicators_reset():
    """按论文取值重置指标定义。"""
    form = EmptyForm()
    if form.validate_on_submit():
        n = ind_svc.seed_indicators()
        flash("已按论文取值重置 %d 项指标定义" % n, "ok")
    return redirect(url_for("ahp.indicators"))


# ---------------------------- 多专家矩阵 ----------------------------

def expert_scope():
    unit_type = request.values.get("unit_type") or UNIT_TYPES[0]
    level = int(request.values.get("level", 1))
    l1 = request.values.get("l1") or None
    return unit_type, level, l1


def expert_query(unit_type, level, l1):
    q = ExpertMatrix.query.filter_by(unit_type=unit_type, level=level)
    if level == 2:
        q = q.filter_by(l1_name=l1)
    else:
        q = q.filter(ExpertMatrix.l1_name.is_(None))
    return q.order_by(ExpertMatrix.id)


def default_scheme(unit_type, level, l1=None):
    """取（或建）该范围的权重方案，专家矩阵统一挂到它下面。"""
    name = "%s · %s%s" % (unit_type,
                          "一级指标" if level == 1 else "二级指标",
                          "（%s）" % l1 if l1 else "")
    scheme = WeightScheme.query.filter_by(unit_type=unit_type,
                                          level=level, name=name).first()
    if scheme is None:
        scheme = WeightScheme(unit_type=unit_type, level=level, name=name,
                              is_default=False)
        db.session.add(scheme)
        db.session.flush()
    return scheme


@bp.route("/experts", methods=["GET", "POST"])
def experts():
    """多专家判断矩阵录入与汇总。"""
    unit_type, level, l1 = expert_scope()
    if unit_type not in DEFAULT_WEIGHTS:
        flash("无效的微地质单元类型", "error")
        return redirect(url_for("ahp.index"))

    names, vec = indicator_list(unit_type, level, l1)
    n = len(names)
    form = EmptyForm()

    if request.method == "POST" and form.validate_on_submit():
        action = request.form.get("action")
        if action == "add":
            expert_name = request.form.get("expert_name", "").strip() or "未具名专家"
            try:
                upper = [float(request.form.get("m_%d_%d" % (i, j), "1"))
                         for i in range(n) for j in range(i + 1, n)]
            except ValueError:
                flash("矩阵输入有误，请填入正数", "error")
                return redirect(url_for("ahp.experts", unit_type=unit_type,
                                        level=level, l1=l1))
            A = ahp.matrix_from_upper(upper)
            r = ahp.weights_and_consistency(A)
            scheme = default_scheme(unit_type, level, l1)
            db.session.add(ExpertMatrix(
                scheme_id=scheme.id,
                unit_type=unit_type, l1_name=(l1 if level == 2 else None),
                expert_name=expert_name, level=level,
                matrix_json=json.dumps([list(map(float, row)) for row in A]),
                cr=round(r["cr"], 6)))
            db.session.commit()
            flash("已录入专家「%s」的判断矩阵（CR=%.4f）" % (expert_name, r["cr"]), "ok")
        elif action == "save_agg":
            # 把汇总权重落库并生效，使多专家结果真正参与评价计算
            weights = _aggregate(unit_type, level, l1)
            if weights is None:
                flash("暂无可汇总的专家矩阵", "error")
            elif not weights["consistent"]:
                flash("汇总矩阵一致性比例 CR=%.4f ≥ 0.1，不满足要求，"
                      "请先检查或调整专家矩阵" % weights["cr"], "error")
            else:
                names_, _ = indicator_list(unit_type, level, l1)
                pairs = to_code_pairs(unit_type, level, l1, names_,
                                      weights["weights"])
                _, cnt = ws.save_weights(unit_type, pairs)
                flash("已保存并为「%s」生效 %d 项汇总权重（CR=%.4f）"
                      % (unit_type, cnt, weights["cr"]), "ok")
        return redirect(url_for("ahp.experts", unit_type=unit_type,
                                level=level, l1=l1))

    rows = expert_query(unit_type, level, l1).all()
    default = [[round(vec[i] / vec[j], 4) for j in range(n)] for i in range(n)]
    return render_template("ahp/experts.html", unit_type=unit_type, level=level,
                           l1=l1, names=names, rows=rows, default=default,
                           n=n, form=form)


@bp.route("/experts/<int:mid>/delete", methods=["POST"])
def expert_delete(mid):
    row = db.get_or_404(ExpertMatrix, mid)
    unit_type, level, l1 = row.unit_type, row.level, row.l1_name
    form = EmptyForm()
    if form.validate_on_submit():
        db.session.delete(row)
        db.session.commit()
        flash("已删除专家矩阵", "ok")
    return redirect(url_for("ahp.experts", unit_type=unit_type,
                            level=level, l1=l1))


def _aggregate(unit_type, level, l1):
    """按几何平均汇总多专家矩阵并做一致性检验。无矩阵时返回 None。"""
    rows = expert_query(unit_type, level, l1).all()
    mats = []
    for r in rows:
        try:
            mats.append([list(map(float, line))
                         for line in json.loads(r.matrix_json)])
        except Exception:
            continue
    if not mats:
        return None
    agg = ahp.aggregate_matrices(mats)
    res = ahp.weights_and_consistency(agg)
    return {
        "count": len(mats),
        "weights": res["weights"],
        "lambda_max": res["lambda_max"],
        "ci": res["ci"], "cr": res["cr"],
        "consistent": res["consistent"],
        "most_inconsistent": ahp.find_most_inconsistent(agg),
        "expert_crs": [r.cr for r in rows if r.cr is not None],
    }


@bp.route("/experts/aggregate")
def experts_aggregate():
    """按几何平均汇总多专家矩阵，并做一致性检验。"""
    unit_type, level, l1 = expert_scope()
    if unit_type not in DEFAULT_WEIGHTS:
        flash("无效的微地质单元类型", "error")
        return redirect(url_for("ahp.index"))
    names, vec = indicator_list(unit_type, level, l1)
    rows = expert_query(unit_type, level, l1).all()

    result = _aggregate(unit_type, level, l1)
    if result is not None:
        result["weights"] = [round(v, 4) for v in result["weights"]]
        result["lambda_max"] = round(result["lambda_max"], 4)
    return render_template("ahp/experts_aggregate.html", unit_type=unit_type,
                           level=level, l1=l1, names=names, rows=rows,
                           result=result, form=EmptyForm())
