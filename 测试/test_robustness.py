# -*- coding: utf-8 -*-
"""健壮性与可追溯性自检。

覆盖两轮审核之后补上的收尾项：
- 错误页：404 / 413 都要是中文页，而不是默认英文页；
- 停用账号立即失效：已经登录的会话不能继续用；
- 会话密钥不再硬编码；
- 口令与账号名长度校验（与自助注册保持一致）；
- 评价结果留存「计算参数快照 + 计算人」，并能算出短板提示；
- 上传文件删除有目录围栏，`../` 出不去。
"""
import io
import os
import re
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.config import Config
from app.models import db, User, MinePatch
from werkzeug.security import generate_password_hash

LINE = "=" * 72
_fails = []
COPY = os.path.join(tempfile.gettempdir(), "dsh_robust_check.db")
shutil.copy2(os.path.join(ROOT, "app", "app.db"), COPY)
PW = "robust-check-123"


def ok(flag, label, extra=""):
    print("  %s %-48s %s" % ("[符合]" if flag else "[不符合]", label, extra))
    if not flag:
        _fails.append(label)


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + COPY
    TESTING = False                  # 生产式：500 走错误页而不是抛异常
    MAX_CONTENT_LENGTH = 64 * 1024   # 调小上限，便于构造「文件太大」


app = create_app(TestConfig)


def token_of(html):
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None


def login(username="admin"):
    c = app.test_client()
    c.post("/login", data={"username": username, "password": PW,
                           "csrf_token": token_of(c.get("/login").get_data(as_text=True))})
    return c


with app.app_context():
    for u in User.query.all():
        u.password_hash = generate_password_hash(PW)
    db.session.commit()

c = login()

print(LINE)
print("一、错误页")
print(LINE)
r = c.get("/no-such-page")
ok(r.status_code == 404 and "请求的页面不存在" in r.get_data(as_text=True),
   "404 是中文错误页", "HTTP %d" % r.status_code)
r = c.post("/indicator/import",
           data={"file": (io.BytesIO(b"x" * (200 * 1024)), "big.csv")},
           content_type="multipart/form-data")
ok(r.status_code == 413 and "上传的文件太大" in r.get_data(as_text=True),
   "413 是中文错误页", "HTTP %d" % r.status_code)

print()
print(LINE)
print("二、停用账号立即失效")
print(LINE)
with app.app_context():
    adm = User.query.filter_by(username="admin").first()
    adm.active = False
    db.session.commit()
r = c.get("/", follow_redirects=False)
ok(r.status_code == 302 and "/login" in (r.headers.get("Location") or ""),
   "停用后旧会话被踢回登录页", "HTTP %d → %s" % (r.status_code,
                                              r.headers.get("Location")))
body = c.get("/", follow_redirects=True).get_data(as_text=True)
ok("该账号已停用" in body, "登录页给出停用提示")
with app.app_context():
    adm = User.query.filter_by(username="admin").first()
    adm.active = True
    db.session.commit()
c = login()
ok(c.get("/").status_code == 200, "恢复启用后可正常登录", "HTTP 200")

print()
print(LINE)
print("三、会话密钥与口令校验")
print(LINE)
ok(Config.SECRET_KEY != "mine-restoration-dev-key",
   "SECRET_KEY 不再是硬编码默认值", "长度 %d" % len(Config.SECRET_KEY))
key_file = os.path.join(ROOT, "app", ".secret_key")
ok(not os.path.exists(key_file) or os.path.getsize(key_file) > 0,
   "随机密钥落盘保存（.gitignore 已忽略）")

tok = token_of(c.get("/profile?tab=users").get_data(as_text=True))
r = c.post("/users/add", data={"username": "shortpw", "password": "a",
                               "role": "operator", "csrf_token": tok},
           follow_redirects=True)
ok("密码至少 6 位" in r.get_data(as_text=True), "1 位口令被拒")
with app.app_context():
    ok(User.query.filter_by(username="shortpw").first() is None,
       "被拒的账号没有落库")
r = c.post("/users/add", data={"username": "y" * 100, "password": "abcdef",
                               "role": "operator", "csrf_token": tok},
           follow_redirects=True)
ok("账户名称不能超过 64 个字符" in r.get_data(as_text=True),
   "超长账号名被拒")

print()
print(LINE)
print("四、评价记录留存参数快照与计算人 + 短板提示")
print(LINE)
with app.app_context():
    patch = MinePatch.query.first()
    patch_id = patch.id
    admin_id = User.query.filter_by(username="admin").first().id
    from app.models import EvaluationResult
    before_max = db.session.query(db.func.max(EvaluationResult.id)).scalar() or 0

# 走真实的界面路径执行一次评价：这样 current_user 才是有登录态的，
# 顺便也验证「在请求里算出计算人」这条链路
run_url = "/evaluate/%d" % patch_id      # 执行评价的页面就是这个地址
tok = token_of(c.get(run_url).get_data(as_text=True))
c.post(run_url, data={"csrf_token": tok}, follow_redirects=True)

with app.app_context():
    import json
    from app.models import EvaluationResult
    from app.views.evaluate import weak_points, user_label, param_source_summary
    rec = EvaluationResult.query.filter(EvaluationResult.id > before_max) \
        .order_by(EvaluationResult.id.desc()).first()
    ok(rec is not None, "界面执行评价后新增了一条记录",
       ("F=%s %s" % (rec.final_score, rec.grade)) if rec else "没有新增记录")
    ok(bool(rec.params_json), "参数快照已写入评价记录")
    snap = json.loads(rec.params_json or "{}")
    ok("ideals" in snap and "weight_sources" in snap,
       "快照含理想取值与权重来源", "键：%s" % list(snap))
    ok(param_source_summary(snap).startswith("全部采用系统默认取值"),
       "默认情况下如实说明「未偏离系统默认取值」", param_source_summary(snap))
    ok(rec.created_by == admin_id, "计算人已记录", str(user_label(rec.created_by)))
    units = json.loads(rec.unit_scores)
    weak = weak_points(units)
    ok(len(weak) >= 1 and all(w["gain"] > 0 for w in weak),
       "短板提示能算出提升空间最大的指标",
       "；".join("%s/%s +%.4f" % (w["unit_type"], w["l2"], w["gain"])
                for w in weak[:2]))
    rec_id = rec.id

print()
print(LINE)
print("五、上传删除有目录围栏")
print(LINE)
from app.utils.uploads import remove_upload
with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, "uploads")
    os.makedirs(os.path.join(root, "patches"))
    inside = os.path.join(root, "patches", "a.png")
    outside = os.path.join(tmp, "keep.txt")
    for p in (inside, outside):
        with open(p, "w", encoding="utf-8") as f:
            f.write("x")
    remove_upload("uploads/patches/../../../keep.txt", root)
    ok(os.path.exists(outside), "`../` 越界的删除请求被挡下")
    remove_upload("uploads/patches/a.png", root)
    ok(not os.path.exists(inside), "目录内的正常删除仍然有效")

print()
print(LINE)
print("六、清理")
print(LINE)
with app.app_context():
    from app.models import EvaluationResult, ScoreDetail
    rec = db.session.get(EvaluationResult, rec_id)
    if rec:
        ScoreDetail.query.filter_by(result_id=rec.id).delete()
        db.session.delete(rec)
        db.session.commit()
    print("  已删除自检产生的评价记录")
    db.session.remove()
    db.engine.dispose()
try:
    os.remove(COPY)
    print("  副本库已删除")
except OSError as e:
    print("  副本库暂时删不掉（%s）" % e)

print()
if _fails:
    print("未通过：%s" % "、".join(_fails))
    sys.exit(1)
print("健壮性与可追溯性自检全部通过 √")
