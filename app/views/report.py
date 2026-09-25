# -*- coding: utf-8 -*-
"""M9 报告与结果输出 —— 路由（占位，由甲实现）。"""
from flask import Blueprint

bp = Blueprint("report", __name__, url_prefix="/report")


@bp.route("/")
def index():
    return "报告与结果输出模块（待实现）"
