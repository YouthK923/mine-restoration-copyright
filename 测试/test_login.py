# -*- coding: utf-8 -*-
"""登录自检：七种输入组合都必须给出提示。

背景：登录框带 novalidate，浏览器不会代填提示。早先的实现只用
`if form.validate_on_submit()` 包住提示，密码留空时校验直接失败，
既没有浮层也没有字段错误 —— 用户点了「登录」会觉得没反应。
本脚本把各种组合固定下来，防止再退回那种「什么都不说」的状态。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import db, User
from werkzeug.security import generate_password_hash

LINE = "=" * 72
TOAST_RE = re.compile(r'<div class="toast-center[^"]*"[^>]*>(.*?)</div>', re.S)
FIELD_RE = re.compile(r'<p class="lp-field__error">(.*?)</p>', re.S)
_fails = []
TMP = "login_off"


def ok(flag, label, extra=""):
    print("  %s %-44s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


class TestConfig(Config):
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(ROOT, "app", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(TestConfig)

# 一个被停用的账号，用来验证停用提示
with app.app_context():
    old = User.query.filter_by(username=TMP).first()
    if old:
        db.session.delete(old)
        db.session.commit()
    off = User(username=TMP, role="operator", active=False,
               password_hash=generate_password_hash("offpass123"))
    db.session.add(off)
    db.session.commit()


def attempt(data):
    """提交一次登录，返回页面上出现的所有提示。"""
    c = app.test_client()
    r = c.post("/login", data=data)
    html = r.get_data(as_text=True)
    toasts = [t.strip() for t in TOAST_RE.findall(html)]
    fields = [t.strip() for t in FIELD_RE.findall(html)]
    return r.status_code, html, toasts, fields


print(LINE)
print("一、每种输入组合都要有提示（不能「点了没反应」）")
print(LINE)
CASES = [
    ("用户名不存在 + 密码留空",
     {"username": "no_such_user", "password": ""},
     ["请输入密码"], []),
    ("用户名不存在 + 填了密码",
     {"username": "no_such_user", "password": "whatever"},
     [], ["账户名称或密码错误"]),
    ("用户名存在 + 密码留空",
     {"username": "admin", "password": ""},
     ["请输入密码"], []),
    ("用户名存在 + 密码错误",
     {"username": "admin", "password": "wrong"},
     [], ["账户名称或密码错误"]),
    ("用户名为空 + 填了密码",
     {"username": "", "password": "whatever"},
     ["请输入账户名称"], []),
    ("两项都为空",
     {"username": "", "password": ""},
     ["请输入账户名称", "请输入密码"], []),
    ("账号已被停用 + 密码正确",
     {"username": TMP, "password": "offpass123"},
     [], ["该账号已停用，请联系管理员"]),
]
for label, data, want_fields, want_toasts in CASES:
    status, html, toasts, fields = attempt(data)
    good = status == 200 and fields == want_fields and toasts == want_toasts
    ok(good, label,
       "字段=%s 浮层=%s" % (fields or "-", toasts or "-"))

print()
print(LINE)
print("二、提示的呈现方式")
print(LINE)
status, html, toasts, fields = attempt({"username": "admin",
                                        "password": "wrong"})
ok("toast-center--error" in html, "凭据错误用错误配色的浮层")
ok(html.count("账户名称或密码错误") == 1, "同一条提示不会重复出现",
   "%d 次" % html.count("账户名称或密码错误"))
ok('class="flash' not in html, "不再同时出现顶部提示条")
ok(not FIELD_RE.search(html), "凭据错误不写成字段错误")

status, html, toasts, fields = attempt({"username": "admin", "password": ""})
ok('aria-invalid="true"' in html, "出错的输入框带 aria-invalid")
ok("lp-field__error" in html, "字段错误贴着输入框显示")
ok('class="toast-center' not in html, "字段校验错误不占用浮层")

print()
print(LINE)
print("三、登录页应有自动展开登录框的钩子")
print(LINE)
base_html = attempt({"username": "", "password": ""})[1]
ok("lp-field__error" in base_html and "lp-auth" in base_html,
   "页面同时含登录框与字段错误元素")
login_tpl = open(os.path.join(ROOT, "app", "templates", "auth", "login.html"),
                 encoding="utf-8").read()
ok("document.querySelector('.lp-field__error')" in login_tpl
   and "document.querySelector('.toast-center')" in login_tpl,
   "脚本在有任一提示时自动展开登录框")

print()
print(LINE)
print("四、正常登录仍然可用")
print(LINE)
c = app.test_client()
body = c.post("/login", data={"username": "admin", "password": "admin123"},
              follow_redirects=True).get_data(as_text=True)
ok("登录成功" in body, "正确的账户名称与密码可以登录")
ok("工作台" in body or "评价流程" in body, "登录后进入工作台")
blank_toasts = attempt({"username": "", "password": ""})[2]
ok("登录成功" not in blank_toasts, "留空提交不会被误判为登录成功")

print()
print(LINE)
print("五、清理")
print(LINE)
with app.app_context():
    t = User.query.filter_by(username=TMP).first()
    if t:
        db.session.delete(t)
        db.session.commit()
    ok(User.query.filter_by(username=TMP).first() is None, "临时停用账号已清理")

print()
print(LINE)
if _fails:
    print("存在未通过项：")
    for f in _fails:
        print("  -", f)
    sys.exit(1)
print("登录自检全部通过 √")
print(LINE)
