# -*- coding: utf-8 -*-
"""地基自检：验证 AHP 引擎与应用可启动。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

from app.services import ahp_service as ahp

LINE = "=" * 66

# ---------------------------------------------------------------------------
# 1) 完全一致矩阵 → 权重应精确还原，CR=0
# ---------------------------------------------------------------------------
print(LINE)
print("测试 1  完全一致判断矩阵的权重还原与一致性")
print(LINE)

# 由权重构造完全一致矩阵：a_ij = w_i / w_j
w_true = np.array([0.44, 0.31, 0.25])
A = np.outer(w_true, 1.0 / w_true)
r = ahp.weights_and_consistency(A)

print("  判断矩阵 A：")
for row in A:
    print("    " + "  ".join(f"{v:8.4f}" for v in row))
print()
print("  计算权重 :", "  ".join(f"{v:.4f}" for v in r["weights"]))
print("  真实权重 :", "  ".join(f"{v:.4f}" for v in w_true))
print("  λmax = %.6f   CI = %.3e   CR = %.3e   一致: %s"
      % (r["lambda_max"], r["ci"], r["cr"], r["consistent"]))
assert np.allclose(r["weights"], w_true, atol=1e-6), "权重未精确还原"
assert r["consistent"], "完全一致矩阵应通过检验"

# ---------------------------------------------------------------------------
# 2) 上三角输入 → 完整矩阵 → 一致性定位
# ---------------------------------------------------------------------------
print()
print(LINE)
print("测试 2  上三角录入与最不一致项定位")
print(LINE)

# 一个不太一致的 3 阶矩阵：上三角 [2, 5, 3]（a12=2, a13=5, a23=3）
M = ahp.matrix_from_upper([2, 5, 3])
r2 = ahp.weights_and_consistency(M)
bad = ahp.find_most_inconsistent(M)
print("  由 [a12=2, a13=5, a23=3] 构造矩阵：")
for row in M:
    print("    " + "  ".join(f"{v:8.4f}" for v in row))
print("  权重:", "  ".join(f"{v:.4f}" for v in r2["weights"]),
      "  CR = %.3f  一致: %s" % (r2["cr"], r2["consistent"]))
print("  最不一致比较项: 第(%d,%d) 项，当前 %.3f，理想 %.3f"
      % (bad["i"] + 1, bad["j"] + 1, bad["value"], bad["expected"]))

# ---------------------------------------------------------------------------
# 3) 多专家聚合（几何平均）
# ---------------------------------------------------------------------------
print()
print(LINE)
print("测试 3  多专家判断矩阵聚合（几何平均）")
print(LINE)

m1 = ahp.matrix_from_upper([2, 4, 3])
m2 = ahp.matrix_from_upper([3, 5, 2])
agg = ahp.aggregate_matrices([m1, m2])
print("  专家1 上三角 [2,4,3]，专家2 上三角 [3,5,2]")
print("  聚合后上三角: a12=%.4f a13=%.4f a23=%.4f"
      % (agg[0, 1], agg[0, 2], agg[1, 2]))
assert abs(agg[0, 1] - np.sqrt(2 * 3)) < 1e-9, "几何平均错误"

# ---------------------------------------------------------------------------
# 4) 论文表 3 权重可还原性
# ---------------------------------------------------------------------------
print()
print(LINE)
print("测试 4  论文表 3 碎石边坡一级权重 (0.44, 0.31, 0.25)")
print(LINE)
j = ahp.judge_from_weights([0.44, 0.31, 0.25])
print("  λmax = %.6f   CR = %.3e   一致: %s" % (j["lambda_max"], j["cr"], j["consistent"]))
assert j["consistent"], "论文权重应能作为完全一致矩阵主特征向量"

# ---------------------------------------------------------------------------
# 5) 应用可启动 + 建表
# ---------------------------------------------------------------------------
print()
print(LINE)
print("测试 5  Flask 应用启动与建表")
print(LINE)
from app import create_app
from app.models import db

app = create_app()
with app.app_context():
    db.create_all()
    tables = sorted(db.metadata.tables.keys())
print("  已创建 %d 张表：" % len(tables))
for t in tables:
    print("    -", t)

print()
print(LINE)
print("全部测试通过 ✓")
print(LINE)
