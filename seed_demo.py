# -*- coding: utf-8 -*-
"""内置玉田县案例：把论文第 5 节案例数据写入数据库。

用于功能验证与操作演示。数据逐字取自论文表 5 与第 5 节。
运行：python seed_demo.py（幂等：已存在则先清空重建）
"""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

from app import create_app
from app.models import db, User, Project, MinePatch, ReferenceEcosystem, MicroUnit, IndicatorData

app = create_app()

CASE = {
    "name": "玉田县典型历史遗留废弃矿山案例",
    "patch_name": "玉田县孤树镇白云岩采石场",
    "area_ha": 5.6,
    "mineral_type": "白云岩",
    "units": [
        {
            "unit_type": "岩质边坡", "ratio": 0.1386,
            "data": {"coverage": 68.88, "shannon": 0.00,
                     "slope": 63.33, "aspect": "阴阳坡"},
        },
        {
            "unit_type": "碎石边坡", "ratio": 0.6295,
            "data": {"soil_ratio": 0.34, "thickness": 10, "ph": 9.24,
                     "organic_matter": 4.89,
                     "heavy_metals": {"Hg": 0.05, "As": 5.17, "Ni": 12.60,
                                      "Cu": 11.70, "Cd": 0.04, "Pb": 6.50},
                     "coverage": 87.92, "shannon": 0.60,
                     "slope": 28.75, "aspect": "阳坡"},
        },
        {
            "unit_type": "平台", "ratio": 0.2319,
            "data": {"soil_ratio": 0.56, "thickness": 30, "ph": 8.72,
                     "organic_matter": 10.92,
                     "heavy_metals": {"Hg": 0.02, "As": 3.13, "Ni": 12.33,
                                      "Cu": 11.14, "Cd": 0.09, "Pb": 9.98},
                     "coverage": 58.42, "shannon": 0.72},
        },
    ],
}


def seed():
    with app.app_context():
        # 清空旧案例（幂等）
        old = Project.query.filter_by(name=CASE["name"]).first()
        if old:
            db.session.delete(old)
            db.session.commit()

        admin = User.query.filter_by(username="admin").first()
        if not admin:
            from werkzeug.security import generate_password_hash
            admin = User(username="admin",
                         password_hash=generate_password_hash("admin123"),
                         role="admin")
            db.session.add(admin)
            db.session.commit()

        project = Project(name=CASE["name"], code="DEMO-001",
                          description="论文第 5 节典型案例", created_by=admin.id)
        db.session.add(project)
        db.session.flush()

        patch = MinePatch(project_id=project.id, name=CASE["patch_name"],
                          admin_region="河北省唐山市玉田县",
                          area_ha=CASE["area_ha"],
                          mineral_type=CASE["mineral_type"],
                          mining_method="露天开采", stop_years=None,
                          responsible_entity_missing=True)
        db.session.add(patch)
        db.session.flush()

        ref = ReferenceEcosystem(patch_id=patch.id,
                                 coverage_benchmark=75.0, shannon_benchmark=0.7)
        db.session.add(ref)

        for u in CASE["units"]:
            unit = MicroUnit(patch_id=patch.id, unit_type=u["unit_type"],
                             ratio=u["ratio"], area=None)
            db.session.add(unit)
            db.session.flush()
            d = u["data"]
            ind = IndicatorData(
                unit_id=unit.id,
                soil_ratio=d.get("soil_ratio"),
                thickness=d.get("thickness"),
                ph=d.get("ph"),
                organic_matter=d.get("organic_matter"),
                heavy_metals=json.dumps(d["heavy_metals"], ensure_ascii=False)
                              if d.get("heavy_metals") else None,
                coverage=d.get("coverage"),
                shannon=d.get("shannon"),
                slope=d.get("slope"),
                aspect=d.get("aspect"),
            )
            db.session.add(ind)

        db.session.commit()
        print("已写入案例：", CASE["name"])
        print("  图斑：", CASE["patch_name"])
        print("  微地质单元：岩质边坡 13.86% / 碎石边坡 62.95% / 平台 23.19%")
        print("  管理员账号：admin / admin123")


if __name__ == "__main__":
    seed()
