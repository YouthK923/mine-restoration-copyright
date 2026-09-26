# -*- coding: utf-8 -*-
"""个人设置自检：资料、头像、密码。

与「用户管理」的区别：那里是管理员维护别人，这里是用户维护自己。
注意本脚本会临时改动 admin 的密码，测完必须还原，否则会污染其他测试。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 本脚本位于 测试/ 子目录，先把仓库根目录加入模块搜索路径，
# 使 `from app import ...` 与 app/app.db 的定位不受影响。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import db, User
from werkzeug.security import generate_password_hash, check_password_hash

LINE = "=" * 72
SHOT = os.path.join(ROOT, "软著材料", "截图", "01_登录.png")
_fails = []


def ok(flag, label, extra=""):
    print("  %s %-46s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


class TestConfig(Config):
    """继承正式配置，保证上传目录等设置与真实运行一致。"""
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(ROOT, "app", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(TestConfig)
client = app.test_client()

print(LINE)
print("一、访问控制")
print(LINE)
r = client.get("/profile", follow_redirects=False)
ok(r.status_code == 302 and "/login" in (r.headers.get("Location") or ""),
   "未登录访问个人设置被跳到登录页", "HTTP %d" % r.status_code)

client.post("/login", data={"username": "admin", "password": "admin123"},
            follow_redirects=True)
r = client.get("/profile")
body = r.get_data(as_text=True)
ok(r.status_code == 200, "登录后可访问个人设置", "HTTP %d" % r.status_code)
ok("个人资料" in body and "修改密码" in body and "上传头像" in body,
   "页面含资料、密码、头像三块")

print()
print(LINE)
print("二、保存个人资料")
print(LINE)
r = client.post("/profile", data={
    "action": "info",
    "info-display_name": "赵永凯",
    "info-title": "项目负责人",
    "info-email": "zhao@example.com",
    "info-phone": "13800000000",
}, follow_redirects=True)
body = r.get_data(as_text=True)
ok("个人资料已保存" in body, "保存成功并给出反馈")
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    ok(u.display_name == "赵永凯" and u.title == "项目负责人",
       "显示名称与职务已写入", u.display_name or "")
    ok(u.email == "zhao@example.com" and u.phone == "13800000000",
       "邮箱与手机号已写入")
ok("赵永凯" in body, "侧边栏改为显示名称")

r = client.post("/profile", data={
    "action": "info", "info-display_name": "赵永凯",
    "info-email": "不是邮箱",
}, follow_redirects=True)
ok("邮箱格式不正确" in r.get_data(as_text=True), "邮箱格式错误被拦下")

# 留空应清空，而不是写入空串
client.post("/profile", data={"action": "info", "info-display_name": "",
                              "info-title": "", "info-email": "",
                              "info-phone": ""}, follow_redirects=True)
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    ok(u.display_name is None and u.email is None, "留空字段存为 NULL 而非空串")
    ok(u.shown_name == "admin", "没填显示名称时回退到账号名", u.shown_name)

print()
print(LINE)
print("三、上传头像")
print(LINE)
png = open(SHOT, "rb").read()
r = client.post("/profile/avatar",
                data={"avatar": (io.BytesIO(png), "me.png")},
                content_type="multipart/form-data", follow_redirects=True)
body = r.get_data(as_text=True)
ok("头像已更新" in body, "上传成功并给出反馈")
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    rel = u.avatar
ok(bool(rel) and rel.startswith("uploads/avatars/"),
   "头像路径已写入 uploads/avatars/", rel or "")
ok(os.path.isfile(os.path.join(ROOT, "app", "static", rel or "")),
   "头像文件确实落盘")
ok(rel and (rel in body), "页面用上传的头像渲染 <img>")

r = client.post("/profile/avatar",
                data={"avatar": (io.BytesIO(b"x"), "bad.txt")},
                content_type="multipart/form-data", follow_redirects=True)
ok("不支持的文件类型" in r.get_data(as_text=True), "非图片格式被拦下")

# 换一张，旧文件应被清掉
old_abs = os.path.join(ROOT, "app", "static", rel or "")
r = client.post("/profile/avatar",
                data={"avatar": (io.BytesIO(png), "me2.png")},
                content_type="multipart/form-data", follow_redirects=True)
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    new_rel = u.avatar
ok(new_rel != rel, "换头像后路径更新", new_rel or "")
ok(not os.path.isfile(old_abs), "旧头像文件已删除，未残留")

r = client.post("/profile/avatar/delete", data={}, follow_redirects=True)
ok("头像已移除" in r.get_data(as_text=True), "移除头像成功")
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    ok(u.avatar is None, "数据库中头像字段已清空")
new_abs = os.path.join(ROOT, "app", "static", new_rel or "")
ok(not os.path.isfile(new_abs), "移除后文件也删掉了")

print()
print(LINE)
print("四、修改密码")
print(LINE)
r = client.post("/profile", data={
    "action": "password", "pwd-old_password": "wrong",
    "pwd-new_password": "newpass123", "pwd-confirm": "newpass123",
}, follow_redirects=True)
ok("当前密码不正确" in r.get_data(as_text=True), "旧密码错误被拒绝")
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    ok(check_password_hash(u.password_hash, "admin123"), "密码未被改动")

r = client.post("/profile", data={
    "action": "password", "pwd-old_password": "admin123",
    "pwd-new_password": "newpass123", "pwd-confirm": "different",
}, follow_redirects=True)
ok("两次输入的新密码不一致" in r.get_data(as_text=True), "两次新密码不一致被拒绝")

r = client.post("/profile", data={
    "action": "password", "pwd-old_password": "admin123",
    "pwd-new_password": "123", "pwd-confirm": "123",
}, follow_redirects=True)
ok("新密码至少 6 位" in r.get_data(as_text=True), "新密码过短被拒绝")

r = client.post("/profile", data={
    "action": "password", "pwd-old_password": "admin123",
    "pwd-new_password": "newpass123", "pwd-confirm": "newpass123",
}, follow_redirects=True)
ok("密码已修改" in r.get_data(as_text=True), "旧密码正确时修改成功")
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    ok(check_password_hash(u.password_hash, "newpass123"), "新密码已生效")

c2 = app.test_client()
bad = c2.post("/login", data={"username": "admin", "password": "admin123"},
              follow_redirects=True).get_data(as_text=True)
ok("用户名或密码错误" in bad, "旧密码已无法登录")
good = c2.post("/login", data={"username": "admin", "password": "newpass123"},
               follow_redirects=True)
ok(good.status_code == 200 and "用户名或密码错误" not in
   good.get_data(as_text=True), "新密码可以登录")

print()
print(LINE)
print("五、管理员代改他人资料（用户管理页）")
print(LINE)
with app.app_context():
    other = User.query.filter_by(username="prof_target").first()
    if other is None:
        other = User(username="prof_target",
                     password_hash=generate_password_hash("target123"),
                     role="evaluator")
        db.session.add(other)
        db.session.commit()
    other_id = other.id

r = client.get("/users")
ok("显示名称" in r.get_data(as_text=True), "用户列表含「显示名称」列")

r = client.post("/users/%d/edit" % other_id, data={
    "role": "evaluator", "active": "1",
    "display_name": "李四", "title": "评价员",
    "email": "lisi@example.com", "phone": "13900000000",
}, follow_redirects=True)
ok("用户信息已保存" in r.get_data(as_text=True), "管理员保存他人资料成功")
with app.app_context():
    o = db.session.get(User, other_id)
    ok(o.display_name == "李四" and o.title == "评价员",
       "显示名称与职务已写入", o.display_name or "")
    ok(o.email == "lisi@example.com" and o.phone == "13900000000",
       "邮箱与手机号已写入")

r = client.post("/users/%d/edit" % other_id, data={
    "role": "evaluator", "active": "1", "display_name": "李四",
    "email": "坏邮箱",
}, follow_redirects=True)
ok("邮箱格式不正确" in r.get_data(as_text=True), "管理员改错邮箱同样被拦下")
with app.app_context():
    o = db.session.get(User, other_id)
    ok(o.email == "lisi@example.com", "非法邮箱未写入", o.email or "")

# 被改的人登录后，界面上应显示新的显示名称
c3 = app.test_client()
body = c3.post("/login", data={"username": "prof_target",
                               "password": "target123"},
               follow_redirects=True).get_data(as_text=True)
ok("李四" in body, "被改用户登录后侧边栏显示其显示名称")

with app.app_context():
    o = User.query.filter_by(username="prof_target").first()
    if o:
        db.session.delete(o)
        db.session.commit()
    ok(User.query.filter_by(username="prof_target").first() is None,
       "临时用户已清理")

print()
print(LINE)
print("六、还原环境")
print(LINE)
with app.app_context():
    u = User.query.filter_by(username="admin").first()
    u.password_hash = generate_password_hash("admin123")
    u.display_name = None
    u.title = None
    u.email = None
    u.phone = None
    u.avatar = None
    db.session.commit()
    ok(check_password_hash(u.password_hash, "admin123"), "admin 密码已还原")
    ok(u.display_name is None, "个人资料已清空")

print()
print(LINE)
if _fails:
    print("存在未通过项：")
    for f in _fails:
        print("  -", f)
    sys.exit(1)
print("个人设置自检全部通过 √")
print(LINE)
