# -*- coding: utf-8 -*-
"""M6 指标体系与 AHP 权重 —— 路由（占位，由甲实现）。"""
from flask import Blueprint

bp = Blueprint("ahp", __name__, url_prefix="/ahp")


@bp.route("/")
def index():
    return "AHP 权重模块（待实现）"
