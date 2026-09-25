# -*- coding: utf-8 -*-
"""操作审计（M1）。

在应用工厂中以 after_request 钩子统一埋点：凡是成功的写操作（POST/PUT/DELETE）
且已登录，即写入 operation_logs 表，无需在每个视图里手工调用。

动作名称由「端点 → 中文动作」映射表给出，未收录的端点回退为方法 + 路径。
"""
from flask import request
from flask_login import current_user

from app.models import db, OperationLog

# 端点 → 可读动作名
ACTION_NAMES = {
    "auth.login": "登录系统",
    "auth.logout": "退出登录",
    "auth.add_user": "新增用户",
    "auth.edit_user": "编辑用户",
    "auth.delete_user": "删除用户",
    "auth.reset_password": "重置用户密码",

    "project.add": "新建项目",
    "project.edit": "编辑项目",
    "project.delete": "删除项目",
    "project.patch_add": "新建矿山图斑",
    "project.patch_edit": "编辑矿山图斑",
    "project.patch_delete": "删除矿山图斑",
    "project.upload_image": "上传遥感影像",

    "unit.add": "添加微地质单元",
    "unit.edit": "编辑微地质单元",
    "unit.delete": "删除微地质单元",

    "standard.add": "添加标准/政策文件",
    "standard.edit": "编辑标准/政策文件",
    "standard.delete": "删除标准/政策文件",
    "standard.rules": "维护标准规则",
    "standard.rule_delete": "删除标准规则",

    "constraint.check": "执行限制性条件判定",

    "ahp.save_expert": "录入专家判断矩阵",
    "ahp.delete_expert": "删除专家判断矩阵",
    "ahp.aggregate": "汇总多专家矩阵",

    "indicator.edit": "保存指标数据",
    "indicator.import_data": "批量导入指标数据",
    "indicator.update_meta": "维护指标定义",

    "evaluate.run": "执行适宜性评价",
}

# 无需记录的操作（查看类或纯导航）
SKIP_ENDPOINTS = {"static", "auth.index"}


def action_name(endpoint):
    if endpoint in ACTION_NAMES:
        return ACTION_NAMES[endpoint]
    return "写操作 %s %s" % (request.method, request.path)


def extract_target_id():
    """从视图参数中取出被操作对象的主键，取不到则返回 None。"""
    args = request.view_args or {}
    for key in ("pid", "patch_id", "unit_id", "sid", "rid", "result_id", "user_id"):
        if key in args:
            try:
                return int(args[key])
            except (TypeError, ValueError):
                return None
    return None


def record(endpoint, status_code):
    """记录一次写操作。失败（4xx/5xx）也记录，便于追溯。"""
    if endpoint in SKIP_ENDPOINTS:
        return
    try:
        detail = "路径 %s" % request.path
        if status_code >= 400:
            detail += "；结果 HTTP %d" % status_code
        db.session.add(OperationLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action_name(endpoint),
            target_type=(endpoint or "").split(".")[0] or None,
            target_id=extract_target_id(),
            detail=detail,
        ))
        db.session.commit()
    except Exception:
        # 审计失败不应影响业务响应
        db.session.rollback()
