# -*- coding: utf-8 -*-
"""M6 指标体系与 AHP 权重 —— 路由与页面逻辑。"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.forms import AHPSelectForm, EmptyForm
from app.utils.constants import DEFAULT_WEIGHTS
from app.services import ahp_service as ahp

bp = Blueprint("ahp", __name__, url_prefix="/ahp")


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
            return render_template("ahp/index.html", form=form)
        return redirect(url_for("ahp.matrix", unit_type=unit_type,
                                level=2, l1=form.l1.data))
    return render_template("ahp/index.html", form=form)


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

    result = None
    if request.method == "POST" and form.validate_on_submit():
        # 读取上三角输入
        upper = []
        try:
            for i in range(n):
                for j in range(i + 1, n):
                    upper.append(float(request.form.get("m_%d_%d" % (i, j), "1")))
            A = ahp.matrix_from_upper(upper)
            r = ahp.weights_and_consistency(A)
            bad = ahp.find_most_inconsistent(A)
            result = {
                "weights": [round(v, 4) for v in r["weights"]],
                "lambda_max": round(r["lambda_max"], 4),
                "ci": r["ci"],
                "cr": r["cr"],
                "consistent": r["consistent"],
                "matrix": [[round(A[i, j], 4) for j in range(n)] for i in range(n)],
                "most_inconsistent": bad,
            }
        except (ValueError, ZeroDivisionError):
            flash("矩阵输入有误：请填入正数（对角线自动为 1，下三角自动取倒数）", "error")

    # 预填默认值：论文表 3 权重对应的完全一致矩阵 a_ij = w_i / w_j
    default = [[round(vec[i] / vec[j], 4) for j in range(n)] for i in range(n)]
    return render_template(
        "ahp/matrix.html",
        form=form, unit_type=unit_type, level=level, l1=l1,
        names=names, vec=vec, default=default, result=result,
    )
