# -*- coding: utf-8 -*-
"""时间显示：库里一律存 UTC，展示时换成服务器本地时间。

为什么不在写库时直接用本地时间：一个系统里时间基准只能有一个。
`app/models.py` 里所有 `created_at` / `checked_at` 都用 `datetime.utcnow`，
存的是 UTC；如果写库改成本地时间，已经存进库的几千条记录会新旧混着差 8 小时。
所以统一在「展示」这一层换算，老数据不用动。

用法（Jinja）：
    {{ row.created_at | localdt }}                    → 2026-09-26 23:33
    {{ row.created_at | localdt("%Y-%m-%d %H:%M:%S") }} → 2026-09-26 23:33:28
"""
from datetime import datetime, timezone

DEFAULT_FORMAT = "%Y-%m-%d %H:%M"


def to_local(value, fmt=DEFAULT_FORMAT, empty="—"):
    """把 UTC 时间换算成服务器本地时间并格式化。

    传进来的值按「无时区即 UTC」处理；带时区的原样换算，便于以后改用
    带时区的时间戳。空值返回占位符，免得页面上出现 None。
    """
    if value is None:
        return empty
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime(fmt)


def now_utc():
    """取当前 UTC 时间（带时区），用于只作展示、不落库的时间戳。"""
    return datetime.now(timezone.utc)


def utcnow():
    """取当前 UTC 时间（无时区），用于数据库默认值。

    `datetime.utcnow()` 在 Python 3.12 已标记弃用，导入时会刷告警；
    这里用带时区的 now() 再摘掉时区，得到的仍是 naive-UTC，行为一致。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
