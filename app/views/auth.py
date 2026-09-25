# -*- coding: utf-8 -*-
"""M1 用户与权限管理 —— 路由（占位，由乙实现）。"""
from flask import Blueprint

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    return "历史遗留废弃矿山自然恢复适宜性评价系统 V1.0（登录功能待乙实现）"
