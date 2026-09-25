# -*- coding: utf-8 -*-
"""M8 适宜性定量评价引擎 —— 路由（占位，由甲实现）。"""
from flask import Blueprint

bp = Blueprint("evaluate", __name__, url_prefix="/evaluate")


@bp.route("/")
def index():
    return "适宜性评价引擎模块（待实现）"
