# -*- coding: utf-8 -*-
"""注册与职务自检。

覆盖：登录页的注册入口、自助注册的必填/选填、默认职务为操作员、
职务只能由管理员调整、以及操作员看不到管理员分类。
测完删除临时账号，不改动既有数据。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import db, User
from app.utils.constants import DEFAULT_ROLE, ROLE_LABELS

LINE = "=" * 72
_fails = []
TMP_USERS = ("reg_zhang", "reg_li", "reg_dup")


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


def cleanup():
    with app.app_context():
        for name in TMP_USERS:
            u = User.query.filter_by(username=name).first()
            if u:
                db.session.delete(u)
        db.session.commit()


cleanup()

print(LINE)
print("一、登录页的注册入口")
print(LINE)
anon = app.test_client()
body = anon.get("/login").get_data(as_text=True)
ok("点我注册" in body, "登录浮层里有「点我注册」链接")
ok('href="/register"' in body, "链接指向 /register")
r = anon.get("/register")
ok(r.status_code == 200, "未登录可直接打开注册页", "HTTP %d" % r.status_code)
body = r.get_data(as_text=True)
ok("创建账号" in body and "操作员" in body, "注册页说明新账号为操作员")
ok('name="username"' in body and 'name="password"' in body,
   "注册页含账户名称与密码")
ok('name="display_name"' in body and 'name="gender"' in body
   and 'name="email"' in body and 'name="phone"' in body
   and 'name="avatar"' in body,
   "注册页含昵称/性别/邮箱/手机号/头像")
ok("选填" in body, "选填项有明确标注")

print()
print(LINE)
print("二、必填项校验")
print(LINE)
c = app.test_client()
body = c.post("/register", data={}, follow_redirects=True).get_data(as_text=True)
ok("必填" in body or "不能为空" in body, "全空提交被拦下")

body = c.post("/register", data={"username": "reg_li", "password": "abc123",
                                 "confirm": "xyz789"},
              follow_redirects=True).get_data(as_text=True)
ok("不一致" in body, "两次密码不一致被拦下")
with app.app_context():
    ok(User.query.filter_by(username="reg_li").first() is None,
       "校验失败不写入账号")

body = c.post("/register", data={"username": "reg_li", "password": "123",
                                 "confirm": "123"},
              follow_redirects=True).get_data(as_text=True)
ok("至少" in body, "密码过短被拦下")

body = c.post("/register", data={"username": "reg_li", "password": "abc123",
                                 "confirm": "abc123", "email": "不是邮箱"},
              follow_redirects=True).get_data(as_text=True)
ok("邮箱格式不正确" in body, "邮箱格式错误被拦下")

print()
print(LINE)
print("三、只填必填项即可注册成功")
print(LINE)
body = c.post("/register", data={"username": "reg_zhang", "password": "abc123",
                                 "confirm": "abc123"},
              follow_redirects=True).get_data(as_text=True)
ok("注册成功" in body, "注册成功并给出反馈")
ok("工作台" in body or "评价流程" in body, "注册后自动登录进入系统")
with app.app_context():
    u = User.query.filter_by(username="reg_zhang").first()
    ok(u is not None, "账号已写入数据库")
    ok(u.role == DEFAULT_ROLE == "operator",
       "新账号职务默认为操作员", u.role if u else "")
    ok(u.display_name is None and u.email is None and u.phone is None,
       "未填的选填项存为 NULL")
    ok(u.active is True or u.active == 1, "新账号默认启用")

print()
print(LINE)
print("四、选填项与头像")
print(LINE)
png = open(os.path.join(ROOT, "软著材料", "截图", "01_登录.png"), "rb").read()
c2 = app.test_client()
body = c2.post("/register",
               data={"username": "reg_li", "password": "abc123",
                     "confirm": "abc123", "display_name": "李四",
                     "gender": "男", "email": "lisi@example.com",
                     "phone": "13900000000",
                     "avatar": (io.BytesIO(png), "me.png")},
               content_type="multipart/form-data",
               follow_redirects=True).get_data(as_text=True)
ok("注册成功" in body, "带选填项注册成功")
with app.app_context():
    u = User.query.filter_by(username="reg_li").first()
    ok(u.display_name == "李四" and u.gender == "男"
       and u.email == "lisi@example.com" and u.phone == "13900000000",
       "选填项已写入")
    rel = u.avatar
ok(bool(rel) and rel.startswith("uploads/avatars/"),
   "注册时上传的头像已落库", rel or "")
ok(os.path.isfile(os.path.join(ROOT, "app", "static", rel or "")),
   "头像文件确实落盘")
ok("李四" in body, "侧边栏显示注册时填的昵称")

print()
print(LINE)
print("五、账户名称不可重复")
print(LINE)
c3 = app.test_client()
body = c3.post("/register", data={"username": "reg_zhang",
                                  "password": "abc123",
                                  "confirm": "abc123"},
               follow_redirects=True).get_data(as_text=True)
ok("该账户名称已被使用" in body, "重复账户名称被拒绝")

print()
print(LINE)
print("六、职务只能由管理员调整")
print(LINE)
# 操作员自己进个人设置，看不到「账号」分类
body = c2.get("/profile").get_data(as_text=True)
ok("tab=users" not in body and "tab=logs" not in body,
   "操作员看不到账号与操作日志分类")
forced = c2.get("/profile?tab=users").get_data(as_text=True)
ok("tab=users" not in forced, "操作员越权访问账号分类被退回")
ok(c2.get("/users/add").status_code == 403, "操作员访问新增账号返回 403")
ok(c2.get("/profile?tab=users").status_code == 200,
   "越权访问不报错，只是看不到内容")

# 个人设置里也没有职务下拉框（自己改不了自己的职务）
info = c2.get("/profile?tab=info").get_data(as_text=True)
ok('name="info-role"' not in info and 'name="role"' not in info,
   "个人设置里不能改自己的职务")

# 管理员可以改
admin = app.test_client()
admin.post("/login", data={"username": "admin", "password": "admin123"})
with app.app_context():
    uid = User.query.filter_by(username="reg_li").first().id
r = admin.post("/users/%d/edit" % uid,
               data={"role": "admin", "active": "1", "display_name": "李四"},
               follow_redirects=True)
with app.app_context():
    ok(db.session.get(User, uid).role == "admin", "管理员可把操作员改为管理员")
admin.post("/users/%d/edit" % uid,
           data={"role": "operator", "active": "1", "display_name": "李四"},
           follow_redirects=True)
with app.app_context():
    ok(db.session.get(User, uid).role == "operator", "管理员可改回操作员")

# 停用后无法登录
admin.post("/users/%d/edit" % uid,
           data={"role": "operator", "display_name": "李四"},
           follow_redirects=True)
c4 = app.test_client()
body = c4.post("/login", data={"username": "reg_li", "password": "abc123"},
               follow_redirects=True).get_data(as_text=True)
ok("该账号已停用" in body, "被停用的账号无法登录")

print()
print(LINE)
print("七、清理")
print(LINE)
with app.app_context():
    u = User.query.filter_by(username="reg_li").first()
    avatars = [u.avatar] if u and u.avatar else []
cleanup()
for rel in avatars:
    p = os.path.join(ROOT, "app", "static", rel)
    if os.path.isfile(p):
        os.remove(p)
with app.app_context():
    left = User.query.filter(User.username.in_(TMP_USERS)).count()
ok(left == 0, "临时账号已清理")

print()
print(LINE)
if _fails:
    print("存在未通过项：")
    for f in _fails:
        print("  -", f)
    sys.exit(1)
print("注册与职务自检全部通过 √")
print(LINE)
