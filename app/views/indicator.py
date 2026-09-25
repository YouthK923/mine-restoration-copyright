# -*- coding: utf-8 -*-
"""M7 指标数据采集与管理 —— 路由（占位，由甲实现）。"""
from flask import Blueprint

bp = Blueprint("indicator", __name__, url_prefix="/indicator")


@bp.route("/")
def index():
    return "指标数据采集模块（待实现）"
