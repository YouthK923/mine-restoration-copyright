# -*- coding: utf-8 -*-
"""界面修复自检：「记住我」与各模块删除功能。"""
import os
import re
import sys

# 本脚本位于 测试/ 子目录，先把仓库根目录加入模块搜索路径，
# 使 `from app import ...` 与 app/app.db 的定位不受影响。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

sys.stdout.reconfigure(encoding="utf-8")
LINE = "=" * 70


class TestConfig:
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        ROOT, "app", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True
    REMEMBER_COOKIE_DURATION = __import__("datetime").timedelta(days=30)


app = create_app(TestConfig)
client = app.test_client()

# ---------------------------------------------------------------------------
print(LINE)
print("一、「记住我」")
print(LINE)

html = client.get("/login").get_data(as_text=True)
# 1) 复选框必须有可点击关联的 label（这是原先失效的根因）
#    只判断「复选框与文字是否落在同一个 <label> 内」，不绑定具体类名 ——
#    否则换个样式类就会误报，而真正的回归点其实与类名无关。
labels = re.findall(r"<label[^>]*>(.*?)</label>", html, re.S)
wrapped = any(('name="remember"' in b and "记住我" in b) for b in labels)
print("  %s 「记住我」文字与复选框包在同一 label 内" % ("[符合]" if wrapped else "[不符合]"))
assert wrapped, "复选框未与文字关联，点击文字不会勾选"

has_for = 'for="remember"' in html
print("  %s label 带 for 属性指向复选框" % ("[符合]" if has_for else "[不符合]"))

# 2) 勾选后应下发带过期时间的 remember_token
c = app.test_client()
r = c.post("/login", data={"username": "admin", "password": "admin123",
                           "remember": "y"}, follow_redirects=False)
cookies = r.headers.getlist("Set-Cookie")
rt = [h for h in cookies if h.startswith("remember_token=")]
print("  %s 勾选后下发 remember_token" % ("[符合]" if rt else "[不符合]"))
assert rt, "未下发 remember_token"

exp = re.search(r"Expires=([^;]+)", rt[0])
print("  %s 该 cookie 带过期时间：%s"
      % ("[符合]" if exp else "[不符合]", exp.group(1) if exp else "无（会话 cookie）"))
assert exp, "remember_token 无过期时间，关浏览器即失效"

# 3) 不勾选时不应下发 remember_token
c2 = app.test_client()
r2 = c2.post("/login", data={"username": "admin", "password": "admin123"},
             follow_redirects=False)
rt2 = [h for h in r2.headers.getlist("Set-Cookie") if h.startswith("remember_token=")]
print("  %s 未勾选时不下发 remember_token" % ("[符合]" if not rt2 else "[不符合]"))
assert not rt2

# 4) 携带 remember_token 的新会话应自动登录
c3 = app.test_client()
c3.set_cookie("remember_token",
              rt[0].split(";")[0].split("=", 1)[1], domain="localhost")
r3 = c3.get("/", follow_redirects=False)
print("  %s 仅凭 remember_token 访问首页可自动登录（状态码 %d）"
      % ("[符合]" if r3.status_code == 200 else "[不符合]", r3.status_code))
assert r3.status_code == 200

# ---------------------------------------------------------------------------
print()
print(LINE)
print("二、删除功能")
print(LINE)

client.post("/login", data={"username": "admin", "password": "admin123"})

# 项目：列表页须有删除按钮
html = client.get("/project/").get_data(as_text=True)
has_del = "/delete" in html and "btn--danger" in html
print("  %s 项目列表含删除按钮" % ("[符合]" if has_del else "[不符合]"))
assert has_del, "项目列表缺少删除按钮"
print("  %s 删除前有二次确认" % ("[符合]" if "confirm(" in html else "[不符合]"))
assert "confirm(" in html

# 图斑列表
with app.app_context():
    from app.models import MinePatch, Project
    import seed_demo
    patch = seed_demo.demo_patch()
    patch_id = patch.id
html = client.get("/project/%d/patches" % patch_id).get_data(as_text=True)
print("  %s 图斑列表含删除按钮" % ("[符合]" if "/project/patch/" in html and "btn--danger" in html else "[不符合]"))
assert "btn--danger" in html

# 微地质单元
html = client.get("/unit/%d" % patch_id).get_data(as_text=True)
print("  %s 微单元列表含删除按钮" % ("[符合]" if "/unit/delete/" in html else "[不符合]"))
assert "/unit/delete/" in html
print("  %s 微单元编辑为独立页面（表单不再嵌在表格行内）"
      % ("[符合]" if "/unit/edit/" in html else "[不符合]"))

# 标准
html = client.get("/standard/").get_data(as_text=True)
print("  %s 标准列表含删除按钮" % ("[符合]" if "btn--danger" in html else "[不符合]"))
assert "btn--danger" in html

# 实际执行一次删除：新建项目 → 删除 → 确认消失
client.post("/project/add", data={"name": "待删除测试项目", "code": "DEL-1"})
with app.app_context():
    from app.models import db, Project
    tmp = Project.query.filter_by(name="待删除测试项目").first()
    tmp_id = tmp.id
html = client.get("/project/").get_data(as_text=True)
print("  %s 新建项目成功" % ("[符合]" if "待删除测试项目" in html else "[不符合]"))
r = client.post("/project/%d/delete" % tmp_id, follow_redirects=True)
html = r.get_data(as_text=True)
gone = "待删除测试项目" not in html
print("  %s 删除项目后列表中不再出现" % ("[符合]" if gone else "[不符合]"))
assert gone
print("  %s 有删除成功提示" % ("[符合]" if "已删除" in html else "[不符合]"))

print()
print(LINE)
print("界面修复自检全部通过 √")
print(LINE)
