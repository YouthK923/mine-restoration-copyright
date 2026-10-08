# -*- coding: utf-8 -*-
"""表单数值的安全解析。

背景：页面上的数字输入框原来写成 `float(request.form.get("area"))`，
用户填「约 3.5」或全角数字就会撞上 ValueError —— 页面上是默认英文 500 页。
真人演示时这是最容易踩到的一类。统一走这里：
没填返回 None，填了但不是数字抛 FieldError，让视图 flash 一句中文再回退。
"""
import math


class FieldError(ValueError):
    """表单里某个字段填得不对，携带给用户看的中文提示。"""


def parse_float(raw, field, *, minimum=None, maximum=None):
    """把表单值解析成 float。

    raw     表单原始值（可能是 None / "" / "abc" / "1e400"）
    field   字段名，用于拼提示
    minimum / maximum  可选的取值范围，越界同样抛 FieldError
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    try:
        value = float(text)
    except (TypeError, ValueError):
        raise FieldError("「%s」请填数字" % field)
    # nan / inf 能通过 float()，但存进库里会把标准化算成满分，必须挡住
    if not math.isfinite(value):
        raise FieldError("「%s」请填正常的数字" % field)
    if minimum is not None and value < minimum:
        raise FieldError("「%s」不能小于 %g" % (field, minimum))
    if maximum is not None and value > maximum:
        raise FieldError("「%s」不能大于 %g" % (field, maximum))
    return value


def parse_int(raw, field, *, default=None, minimum=None, maximum=None):
    """解析整数，用于查询参数与计数类字段。"""
    if raw is None:
        return default
    text = str(raw).strip()
    if text == "":
        return default
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise FieldError("「%s」请填整数" % field)
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def parse_text(raw, field, *, max_len=None, required=False, default=None):
    """文本字段的统一处理：去空白、查必填、查长度。

    SQLite 不强制 String(128) 的长度，超长名称会原样写进库（自检实测：
    300 字的项目名照样落库），换到 MySQL/PostgreSQL 会直接报错；
    界面版式也会被撑坏。所以在入口处挡一次。
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        if required:
            raise FieldError("「%s」不能为空" % field)
        return default
    if max_len is not None and len(text) > max_len:
        raise FieldError("「%s」不能超过 %d 个字符（当前 %d 个）"
                         % (field, max_len, len(text)))
    return text
