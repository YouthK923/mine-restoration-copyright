# -*- coding: utf-8 -*-
"""端到端自检：录数据 → 执行评价 → 查看结果。"""
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")

# 本脚本位于 测试/ 子目录，先把仓库根目录加入模块搜索路径，
# 使 `from app import ...` 与 app/app.db 的定位不受影响。
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

LINE = "=" * 66

# 与真实配置共用同一个 app.db，但关闭 CSRF 便于测试客户端
class TestConfig:
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        ROOT, "app", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    TESTING = True


app = create_app(TestConfig)
client = app.test_client()

# 登录（案例种子已创建 admin 用户）
client.post("/login", data={"username": "admin", "password": "admin123"})

print(LINE)
print("测试 1  指标数据列表")
print(LINE)
r = client.get("/indicator/")
body = r.get_data(as_text=True)
print("  状态码:", r.status_code)
print("  含案例图斑:", "玉田县孤树镇白云岩采石场" in body)
print("  含三个单元:", all(n in body for n in ("岩质边坡", "碎石边坡", "平台")))
assert r.status_code == 200
assert "岩质边坡" in body and "碎石边坡" in body and "平台" in body

print()
print(LINE)
print("测试 2  指标数据录入页（按单元类型显示字段）")
print(LINE)
from app.models import MicroUnit, MinePatch
with app.app_context():
    unit_rock = MicroUnit.query.filter_by(unit_type="岩质边坡").first()
    unit_gravel = MicroUnit.query.filter_by(unit_type="碎石边坡").first()

r = client.get("/indicator/%d" % unit_rock.id)
b_rock = r.get_data(as_text=True)
print("  岩质边坡页：无「土石比」字段:", "土石比" not in b_rock, "（应 True）")
print("  岩质边坡页：含「植被覆盖度」:", "植被覆盖度" in b_rock)
assert "土石比" not in b_rock and "植被覆盖度" in b_rock

r = client.get("/indicator/%d" % unit_gravel.id)
b_gravel = r.get_data(as_text=True)
print("  碎石边坡页：含「土石比」字段:", "土石比" in b_gravel)
print("  碎石边坡页：含 8 种重金属:", all(m in b_gravel for m in ("Cd", "Hg", "Pb", "Cr", "As", "Ni", "Cu", "Zn")))
assert "土石比" in b_gravel and all(m in b_gravel for m in ("Cd", "Hg", "Pb", "Cr", "As", "Ni", "Cu", "Zn"))

print()
print(LINE)
print("测试 3  执行评价")
print(LINE)
with app.app_context():
    patch = MinePatch.query.first()
r = client.post("/evaluate/%d" % patch.id, data={}, follow_redirects=True)
body = r.get_data(as_text=True)
print("  跳转至结果页:", "适宜性评价结果" in body)
print("  含最终评价因子 F:", "最终评价因子 F" in body)
print("  含等级「适宜」:", "适宜" in body)
print("  含推荐措施「自然恢复」:", "自然恢复" in body)
assert "最终评价因子 F" in body and "自然恢复" in body

print()
print(LINE)
print("测试 4  结果持久化")
print(LINE)
from app.models import EvaluationResult
with app.app_context():
    res = EvaluationResult.query.order_by(EvaluationResult.id.desc()).first()
    print("  最终得分 F =", res.final_score)
    print("  等级 =", res.grade)
    assert res.grade == "适宜"
    assert 0.7 <= res.final_score < 1.0

print()
print(LINE)
print("端到端全部测试通过 ✓")
print(LINE)
