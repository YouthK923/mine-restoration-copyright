# -*- coding: utf-8 -*-
"""核对《验证数据/使用说明.md》里让用户找的界面字样确实存在。

文档写了「点某个按钮」「应该看到某行字」，如果界面上其实不叫这个，
用户就会卡住。这里把文档提到的关键词逐个到真实页面上找一遍。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from app import create_app
from app.models import db, Project, MinePatch, MicroUnit

CSV = os.path.join(BASE, "验证数据", "用例01_理想上限_碎石边坡.csv")


class Cfg:
    SECRET_KEY = "doc"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE, "app",
                                                          "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(Cfg)
c = app.test_client()
c.post("/login", data={"username": "admin", "password": "admin123"},
       follow_redirects=True)

# 建一个临时项目，先在「还没有图斑」的状态下核对项目列表
c.post("/project/add", data={"name": "文档核对", "code": "DOCCHK"}, follow_redirects=True)
with app.app_context():
    pid = Project.query.filter_by(code="DOCCHK").first().id

body = c.get("/project/").get_data(as_text=True)
missing = [w for w in ("＋ 新建图斑", "项目与矿山档案") if w not in body]
print("  [%s] %-12s %s" % ("✓" if not missing else "✗", "项目列表(无图斑)", "/project/"))
if missing:
    print("        页面上找不到：%s" % "、".join(missing))
    fails = ["项目列表无图斑"]

c.post("/project/%d/patch/add" % pid,
       data={"name": "文档核对图斑", "area_ha": "10"}, follow_redirects=True)
with app.app_context():
    patch_id = MinePatch.query.filter_by(project_id=pid).first().id
c.post("/unit/%d/add" % patch_id, data={"unit_type": "碎石边坡", "area": "10"},
       follow_redirects=True)
c.post("/constraint/%d" % patch_id,
       data={"policy_pass": "1", "location_pass": "1", "pollution_pass": "1",
             "geo_pass": "1"}, follow_redirects=True)
with io.open(CSV, "rb") as fh:
    raw = fh.read()
c.post("/indicator/import",
       data={"patch_id": str(patch_id),
             "datafile": (io.BytesIO(raw), "c.csv")},
       content_type="multipart/form-data", follow_redirects=True)

CHECKS = [
    ("微地质单元列表", "/unit/", ["划分与维护", "所属项目"]),
    ("微地质单元页", "/unit/%d" % patch_id,
     ["添加微地质单元", "占比合计", "100.00%", "类型"]),
    ("限制性判定页", "/constraint/%d" % patch_id,
     ["保存判定", "通过", "不通过", "判定结论", "通过，可进入定量评价",
      "政策约束", "区位约束", "土壤污染", "地质灾害"]),
    ("批量导入页", "/indicator/import",
     ["目标矿山图斑", "数据文件", "开始导入", "下载导入模板"]),
    ("评价列表", "/evaluate/", ["前置条件", "已具备", "执行评价"]),
    ("评价页", "/evaluate/%d" % patch_id,
     ["开始评价", "当前流程状态", "限制性条件判定", "划分微地质单元",
      "录入指标数据"]),
    # 「恢复默认」按钮只在存在自定义权重方案时才出现，
    # 默认状态下核对的是这张表本身
    ("权重首页", "/ahp/", ["当前生效权重", "论文表 3 默认权重"]),
]

fails = []
for name, url, words in CHECKS:
    body = c.get(url).get_data(as_text=True)
    missing = [w for w in words if w not in body]
    flag = "✓" if not missing else "✗"
    print("  [%s] %-12s %s" % (flag, name, url))
    if missing:
        print("        页面上找不到：%s" % "、".join(missing))
        fails.append("%s(%s)" % (name, "、".join(missing)))

# 导入结果页（POST 后同页渲染）
r = c.post("/indicator/import",
           data={"patch_id": str(patch_id),
                 "datafile": (io.BytesIO(raw), "c.csv")},
           content_type="multipart/form-data")
body = r.get_data(as_text=True)
missing = [w for w in ("成功导入", "问题行", "导入结果") if w not in body]
print("  [%s] %-12s %s" % ("✓" if not missing else "✗", "导入结果页", ""))
if missing:
    print("        页面上找不到：%s" % "、".join(missing))
    fails.append("导入结果页")

# 评价结果页
c.post("/evaluate/%d" % patch_id, data={}, follow_redirects=True)
body = c.get("/evaluate/").get_data(as_text=True)
import re
m = re.search(r"/evaluate/result/(\d+)", body)
if m:
    body = c.get("/evaluate/result/%s" % m.group(1)).get_data(as_text=True)
    missing = [w for w in ("最终评价因子 F", "适宜性等级", "推荐措施",
                           "各微地质单元得分") if w not in body]
    print("  [%s] %-12s" % ("✓" if not missing else "✗", "评价结果页"))
    if missing:
        print("        页面上找不到：%s" % "、".join(missing))
        fails.append("评价结果页")

# 清理
with app.app_context():
    from app.models import (IndicatorData, ConstraintCheck, EvaluationResult,
                            ScoreDetail)
    uids = [u.id for u in MicroUnit.query.filter_by(patch_id=patch_id)]
    if uids:
        IndicatorData.query.filter(IndicatorData.unit_id.in_(uids)).delete(
            synchronize_session=False)
    rids = [r.id for r in EvaluationResult.query.filter_by(patch_id=patch_id)]
    if rids:
        ScoreDetail.query.filter(ScoreDetail.result_id.in_(rids)).delete(
            synchronize_session=False)
    EvaluationResult.query.filter_by(patch_id=patch_id).delete()
    ConstraintCheck.query.filter_by(patch_id=patch_id).delete()
    MicroUnit.query.filter_by(patch_id=patch_id).delete()
    db.session.delete(db.session.get(MinePatch, patch_id))
    db.session.delete(db.session.get(Project, pid))
    db.session.commit()

print()
if fails:
    print("文档与界面不一致：%s" % "、".join(fails))
    sys.exit(1)
print("文档提到的界面字样全部存在 ✓")
