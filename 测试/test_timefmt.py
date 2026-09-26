# -*- coding: utf-8 -*-
"""时间显示自检：库里存 UTC，页面上必须是本地时间（北京时间）。

背景：模型里的 created_at / checked_at 全部用 datetime.utcnow 落库，
但页面上直接 .strftime 显示，于是操作日志、评价时间比本地时间慢 8 小时；
而报告里的「生成时间」用的是 datetime.now（本地）。同一份报告里两个时间
差 8 小时，评审看到就会当成缺陷。现在统一在展示层换算：
模板用 `| localdt` 过滤器，不再直接对 UTC 值 strftime。
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import db, OperationLog, User
from app.utils.timefmt import to_local, now_utc

LINE = "=" * 72
_fails = []


def ok(flag, label, extra=""):
    print("  %s %-46s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


class TestConfig(Config):
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(ROOT, "app", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(TestConfig)
OFFSET = datetime.now().astimezone().utcoffset() or timedelta(0)

print(LINE)
print("一、换算本身")
print(LINE)
ok(to_local(None) == "—", "空值给占位符，页面上不出现 None")

# 固定一个 UTC 时刻，换算结果应等于它加上本机偏移
utc_moment = datetime(2026, 9, 26, 15, 33, 28)
want = (utc_moment + OFFSET).strftime("%Y-%m-%d %H:%M:%S")
got = to_local(utc_moment, "%Y-%m-%d %H:%M:%S")
ok(got == want, "UTC 按本机偏移换算", "UTC %s → %s（本机偏移 %s）"
   % (utc_moment.strftime("%H:%M:%S"), got, OFFSET))

aware = utc_moment.replace(tzinfo=timezone.utc)
ok(to_local(aware, "%H:%M:%S") == to_local(utc_moment, "%H:%M:%S"),
   "已带时区的值不会被二次换算")

ok(now_utc().tzinfo is not None, "now_utc 返回带时区的时间")
ok(abs((datetime.now(timezone.utc) - now_utc()).total_seconds()) < 5,
   "now_utc 与系统 UTC 时间一致")

print()
print(LINE)
print("二、操作日志页显示的是本地时间")
print(LINE)
MARK = "TIMECHK"
with app.app_context():
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        raise SystemExit("库里没有 admin 账号，无法自检")
    row = OperationLog(user_id=admin.id, action="时间自检",
                       target_type="system", target_id=0,
                       detail="time check",
                       created_at=datetime.utcnow())
    db.session.add(row)
    db.session.commit()
    row_id = row.id

client = app.test_client()
client.post("/login", data={"username": "admin", "password": "admin123"},
            follow_redirects=True)
r = client.get("/profile?tab=logs")
body = r.get_data(as_text=True)
ok(r.status_code == 200, "操作日志页可访问", "HTTP %d" % r.status_code)

local_str = to_local(row.created_at, "%Y-%m-%d %H:%M:%S")
utc_str = row.created_at.strftime("%Y-%m-%d %H:%M:%S")
ok(local_str in body, "日志时间按本地时间显示", local_str)
if OFFSET != timedelta(0):
    ok(utc_str not in body or utc_str == local_str,
       "页面上不再出现未换算的 UTC 时间", "UTC 原值 %s" % utc_str)
else:
    print("  [跳过] 本机时区就是 UTC，无法区分两者")

print()
print(LINE)
print("三、模板层不再直接对 UTC 字段 strftime")
print(LINE)
TEMPLATES = ["auth/_logs.html", "ahp/experts.html", "auth/profile.html",
             "project/patch_edit.html", "report/detail.html",
             "report/print.html"]
for name in TEMPLATES:
    path = os.path.join(ROOT, "app", "templates", name)
    src = open(path, encoding="utf-8").read()
    has_filter = "localdt" in src
    dirty = "created_at.strftime" in src or "image_uploaded_at.strftime" in src
    ok(has_filter and not dirty, "%s 走 localdt 过滤器" % name,
       "直接 strftime" if dirty else "")

print()
print(LINE)
print("四、清理自检数据")
print(LINE)
with app.app_context():
    row = db.session.get(OperationLog, row_id)
    if row:
        db.session.delete(row)
        db.session.commit()
print("  已删除自检日志 1 条")

print()
if _fails:
    print("未通过：%s" % "、".join(_fails))
    sys.exit(1)
print("时间显示自检全部通过 √")
