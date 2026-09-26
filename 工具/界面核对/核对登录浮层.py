# -*- coding: utf-8 -*-
"""核对「登录成功」居中浮层：渲染位置、只出现一次、其他提示不受影响。

注意：base.html 的内联 <style> 里本来就写着 .toast-center 和
「登录成功」字样的注释，所以不能直接在整页 HTML 里搜这些字符串，
否则全是假阳性。检查前先把 <style> 块和浮层本身剔掉。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from app import create_app

TOAST_RE = re.compile(r'<div class="toast-center".*?</div>', re.S)
STYLE_RE = re.compile(r"<style>.*?</style>", re.S)


class Cfg:
    SECRET_KEY = "toast"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE, "app",
                                                          "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(Cfg)
fails = []


def ok(flag, label, extra=""):
    print("  %s %-44s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        fails.append(label)


def has_toast(html):
    """页面上真正渲染出了浮层元素（而不是命中 CSS 里的类名）。"""
    return bool(TOAST_RE.search(html))


def visible_text(html):
    """去掉 <style> 与浮层后的可见文本，用于查重。"""
    return STYLE_RE.sub("", TOAST_RE.sub("", html))


print("一、登录成功后，首页应出现居中浮层")
c = app.test_client()
r = c.post("/login", data={"username": "admin", "password": "admin123"},
           follow_redirects=True)
body = r.get_data(as_text=True)
ok(r.status_code == 200, "登录并跳转成功", "HTTP %d" % r.status_code)
ok(has_toast(body), "页面渲染出居中浮层元素")
m = TOAST_RE.search(body)
ok(m is not None and "登录成功" in m.group(0), "浮层文字为「登录成功」")
ok(len(TOAST_RE.findall(body)) == 1, "浮层恰好出现一次",
   "%d 次" % len(TOAST_RE.findall(body)))
ok("登录成功" not in visible_text(body),
   "浮层之外不再重复出现该文字（不会同时冒出提示条）")
ok('role="status"' in body and 'aria-live="polite"' in body,
   "带无障碍朗读属性")

print()
print("二、浮层应出现在 body 顶部、正文容器之外")
pos_toast = body.find('<div class="toast-center"')
pos_container = body.find('class="container"')
ok(0 < pos_toast < pos_container, "浮层在正文容器之前（不受其布局影响）",
   "toast@%d container@%d" % (pos_toast, pos_container))

print()
print("三、再次访问不应重复出现（flash 只消费一次）")
body2 = c.get("/").get_data(as_text=True)
ok(not has_toast(body2), "第二次访问已无浮层")
ok("登录成功" not in visible_text(body2), "文字也一并消失")

print()
print("四、其他提示不受影响，仍是顶部提示条")
c2 = app.test_client()
bad = c2.post("/login", data={"username": "admin", "password": "wrong"},
              follow_redirects=True).get_data(as_text=True)
ok('class="flash error"' in bad and "用户名或密码错误" in bad,
   "登录失败仍是顶部错误提示条")
ok(not has_toast(bad), "登录失败不出现浮层")

c2.post("/login", data={"username": "admin", "password": "admin123"},
        follow_redirects=True)
made = c2.post("/project/add", data={"name": "浮层核对", "code": "TOASTCHK"},
               follow_redirects=True).get_data(as_text=True)
ok('class="flash ok"' in made and "项目已创建" in made,
   "其他成功提示仍是顶部提示条")
ok(not has_toast(made), "其他操作不出现浮层")

print()
print("五、CSS 动画与减弱动效分支都在")
base = io.open(os.path.join(BASE, "app", "templates", "base.html"),
               encoding="utf-8").read()
for key, label in (("position: fixed", "浮层用 fixed 定位（悬浮于页面之上）"),
                   ("top: 50%", "水平垂直居中：top 50%"),
                   ("translate(-50%, -50%)", "水平垂直居中：反向平移"),
                   ("@keyframes toast-fade", "定义了淡入淡出动画"),
                   ("forwards", "动画结束后保持透明（不会又冒出来）"),
                   ("pointer-events: none", "浮层不遮挡鼠标操作"),
                   ("prefers-reduced-motion", "尊重系统「减少动态效果」设置")):
    ok(key in base, label)

print()
print("六、清理测试数据")
with app.app_context():
    from app.models import db, Project
    p = Project.query.filter_by(code="TOASTCHK").first()
    if p:
        db.session.delete(p)
        db.session.commit()
print("  已清理")

print()
if fails:
    print("未通过：%s" % "、".join(fails))
    sys.exit(1)
print("居中浮层自检全部通过 ✓")
