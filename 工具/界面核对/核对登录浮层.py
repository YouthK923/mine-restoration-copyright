# -*- coding: utf-8 -*-
"""核对「登录成功」中上方浮层：渲染位置、只出现一次、其他提示不受影响。

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

TOAST_RE = re.compile(r'<div class="toast-center[^"]*".*?</div>', re.S)
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


print("一、登录成功后，首页应出现中上方浮层")
c = app.test_client()
r = c.post("/login", data={"username": "admin", "password": "admin123"},
           follow_redirects=True)
body = r.get_data(as_text=True)
ok(r.status_code == 200, "登录并跳转成功", "HTTP %d" % r.status_code)
ok(has_toast(body), "页面渲染出中上方浮层元素")
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
print("四、登录失败的提示（凭据错误走浮层、必填未填就地提示）")
c2 = app.test_client()
# 凭据错误：走中上方浮层，会自动淡出，不再常驻页面
bad = c2.post("/login", data={"username": "admin", "password": "wrong"},
              ).get_data(as_text=True)
m_bad = TOAST_RE.search(bad)
ok(m_bad is not None and "账户名称或密码错误" in m_bad.group(0),
   "凭据错误渲染成浮层（会自动淡出，不常驻）")
ok("toast-center--error" in bad, "失败浮层用错误配色与成功提示区分")
ok(bad.count("账户名称或密码错误") == 1, "该提示全页只出现一次",
   "%d 次" % bad.count("账户名称或密码错误"))

# 用户名不存在：同样有提示
ghost = c2.post("/login", data={"username": "no_such_user",
                                "password": "whatever"}).get_data(as_text=True)
ok("账户名称或密码错误" in ghost, "用户名不存在时同样给出提示")

# 必填未填：错误留在表单里逐项显示（以前点了「登录」什么反应都没有）
empty = c2.post("/login", data={"username": "no_such_user",
                                "password": ""}).get_data(as_text=True)
ok("请输入密码" in empty and 'class="lp-field__error"' in empty,
   "密码留空时给出「请输入密码」")
ok("aria-invalid" in empty, "出错的输入框带 aria-invalid 标记")
ok(not has_toast(empty), "字段校验错误不占用浮层（要对着输入框看）")
blank = c2.post("/login", data={"username": "", "password": ""},
                ).get_data(as_text=True)
ok("请输入账户名称" in blank and "请输入密码" in blank,
   "账户名称与密码都为空时两条都提示")

c2.post("/login", data={"username": "admin", "password": "admin123"},
        follow_redirects=True)
made = c2.post("/project/add", data={"name": "浮层核对", "code": "TOASTCHK"},
               follow_redirects=True).get_data(as_text=True)
m2 = TOAST_RE.search(made)
ok(m2 is not None, "其他操作成功也出现中上方浮层")
ok(m2 is not None and "项目已创建" in m2.group(0), "浮层文字为操作结果")
ok('class="flash ok"' not in made, "成功提示不再同时出现在顶部提示条里")
ok("项目已创建" not in visible_text(made), "顶部没有重复出现该提示")

print()
print("五、浮层样式：中上方、浅绿半透明底、居中堆叠、不挡操作")
base = io.open(os.path.join(BASE, "app", "templates", "base.html"),
               encoding="utf-8").read()
# 浮层规则单独取出来，确认底色是浅绿且半透明
m_rule = re.search(r"\.toast-center\s*\{(.*?)\}", base, re.S)
rule = m_rule.group(1) if m_rule else ""
m_bg = re.search(r"background:\s*rgba\(([^)]*)\)", rule)
ok(bool(m_bg), "浮层带半透明底色",
   m_bg.group(0) if m_bg else "未找到 rgba 底色")
if m_bg:
    parts = [p.strip() for p in m_bg.group(1).split(",")]
    r, g, b = (int(float(p)) for p in parts[:3])
    alpha = float(parts[3])
    ok(alpha < 1, "底色是透明的（alpha < 1）", "alpha=%.2f" % alpha)
    ok(g >= r and g >= b, "底色偏绿（G 通道最大）", "rgb(%d,%d,%d)" % (r, g, b))
    ok(min(r, g, b) > 190, "底色是浅色（不是高饱和色块）",
       "rgb(%d,%d,%d)" % (r, g, b))
for key, label in ((".toast-stack", "外层为固定堆叠容器"),
                   ("position: fixed", "容器用 fixed 定位（悬浮于页面之上）"),
                   ("top: 16px", "位置在页面中上方"),
                   ("translateX(-50%)", "水平居中"),
                   ("flex-direction: column", "多条提示纵向排开不重叠"),
                   ("backdrop-filter: blur", "半透明毛玻璃（透出背后内容）"),
                   ("@keyframes toast-fade", "定义了淡入淡出动画"),
                   ("forwards", "动画结束后保持透明（不会又冒出来）"),
                   ("pointer-events: none", "浮层不遮挡鼠标操作"),
                   ("prefers-reduced-motion", "尊重系统「减少动态效果」设置")):
    ok(key in base, label)

print()
print("六、介绍区排版：两个标题居中、九个模块 3×3 居中")


def rule_of(src, selector):
    """取出某个选择器的声明块（取文件中第一处，即主规则）。"""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", src, re.S)
    return m.group(1) if m else ""


lp = io.open(os.path.join(BASE, "app", "templates", "auth", "login.html"),
             encoding="utf-8").read()
intro = rule_of(lp, ".lp-intro > *")
ok("margin-left: auto" in intro and "margin-right: auto" in intro,
   "介绍区各块整体水平居中")
ok("max-width" in intro, "介绍区有统一最大宽度",
   intro.split(";")[0].strip())
title = rule_of(lp, ".lp-intro__title")
ok("text-align: center" in title, "「一套把评价流程固定下来的工具」居中")
ok("margin: 0 auto" in title, "标题块自身也居中（不是只把文字居中）")
sub = rule_of(lp, ".lp-sub-title")
ok("text-align: center" in sub, "「九个功能模块」居中")
mods = rule_of(lp, ".lp-mods")
ok("repeat(3" in mods, "模块卡排成三列", mods.split(";")[1].strip()
   if ";" in mods else "")
points = rule_of(lp, ".lp-points")
ok("repeat(3" in points, "特点卡排成三列")
from app.services import dashboard as dash
n_mod = len(dash.MODULES)
ok(n_mod == 9, "模块数为 9（三列即 3×3）", "%d 个" % n_mod)
ok("@media (max-width: 900px)" in lp and "@media (max-width: 620px)" in lp,
   "窄屏退为两列、一列")

print()
print("七、清理测试数据")
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
print("浮层自检全部通过 ✓")
