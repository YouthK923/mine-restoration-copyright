# -*- coding: utf-8 -*-
"""内置玉田县案例：把论文第 5 节案例数据写入数据库。

用于功能验证与操作演示。数据逐字取自论文表 5 与第 5 节。
运行：python seed_demo.py（幂等：已存在则先清空重建）
"""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

from app import create_app
from app.models import (db, User, Project, MinePatch, ReferenceEcosystem,
                        MicroUnit, IndicatorData, Standard, StandardRule)

app = create_app()

# 论文表 1：11 项地方标准与政策文件
STANDARDS = [
    dict(category="地方标准", province="辽宁", name="矿山废弃地植被自然恢复技术规程",
         doc_number="DB21/T 3702—2023", publish_date="2023-03-30",
         implement_date="2023-04-30",
         summary="首个正式发布的矿山自然恢复地方标准；提出必要条件和充分条件",
         rules=[("植被覆盖度", ">=", "50", "必要条件", None),
                ("无地质灾害", "==", "是", "必要条件", None),
                ("无水土污染", "==", "是", "必要条件", None),
                ("与参照系差距", "<", "20", "充分条件", "%")]),
    dict(category="地方标准", province="湖北", name="废弃露天矿山生态环境自然恢复标准",
         doc_number="DB42/T 2421—2025", publish_date="2025-08-20",
         implement_date="2025-10-20",
         summary="结合矿山生态需求进行自然恢复适宜性分级判断",
         rules=[("自然恢复适宜性分级", "==", "是", "必要条件", None)]),
    dict(category="地方标准", province="内蒙古", name="历史遗留废弃矿山自然恢复判定规范",
         doc_number="DB15/T 4280—2026", publish_date="2026-01-30",
         implement_date="2026-03-01",
         summary="调查内容包含参照生态系统调查",
         rules=[("地质灾害发育程度", "<=", "弱发育", "必要条件", None),
                ("地形地貌与周边协调", "==", "是", "必要条件", None),
                ("有利于植被恢复的表层土壤", "==", "是", "必要条件", None),
                ("已形成稳定植被覆盖", "==", "是", "必要条件", None)]),
    dict(category="地方标准", province="江西", name="废弃矿山自然恢复技术规范",
         doc_number="DB36/T 2221—2026", publish_date="2026-02-02",
         implement_date="2026-08-01",
         summary="对参照生态系统进行了要求；提出自然恢复适宜性指数",
         rules=[("参照生态系统调查", "==", "是", "必要条件", None),
                ("自然恢复适宜性指数", ">=", "阈值", "充分条件", None)]),
    dict(category="地方标准", province="宁夏", name="矿山自然恢复认定规程",
         doc_number=None, publish_date="2026-06-18", implement_date=None,
         summary="分区差异化：三个一级生态修复分区及 22 个二级分区",
         rules=[("无地质灾害风险", "==", "是", "必要条件", None),
                ("植被覆盖度趋势", "==", "稳定或正增长", "必要条件", None),
                ("与参照系差距", "<", "20", "充分条件", "%")]),
    dict(category="政策文件", province="安徽",
         name="安徽省自然资源厅关于规范废弃露天矿山采取自然恢复方式进行治理的通知",
         doc_number="皖自然资修函[2020]34号", publish_date="2020-03-03", implement_date=None,
         summary="自然恢复条件：责任主体为政府、无地质灾害、无水土污染、不在三线三边、水土条件良好",
         rules=[("责任主体", "==", "政府", "必要条件", None),
                ("无地质灾害", "==", "是", "必要条件", None),
                ("无水土污染", "==", "是", "必要条件", None)]),
    dict(category="政策文件", province="山东",
         name="山东省自然资源厅关于进一步规范历史遗留废弃露天开采矿山采取自然恢复方式进行治理的通知",
         doc_number="鲁自然资字[2022]104号", publish_date="2022-08-02", implement_date=None,
         summary="条件与安徽省相同，另增加自然恢复认定标准",
         rules=[("无地质灾害", "==", "是", "必要条件", None),
                ("无水土污染", "==", "是", "必要条件", None)]),
    dict(category="政策文件", province="湖南",
         name="关于印发《湖南省历史遗留矿山自然恢复指导意见（试行）》的通知",
         doc_number="湘自资办发[2023]58号", publish_date="2023-07-20", implement_date=None,
         summary="自然恢复认定标准：无地质灾害或无威胁对象、无水土污染、设备拆除、符合规划、植被覆盖度>75%、连续3年正向增长",
         rules=[("植被覆盖度", ">", "75", "必要条件", "%"),
                ("植被覆盖率趋势", "==", "连续3年正向增长", "必要条件", None),
                ("无地质灾害", "==", "是", "必要条件", None),
                ("符合国土空间规划", "==", "是", "必要条件", None)]),
    dict(category="政策文件", province="新疆",
         name="自治区历史遗留废弃矿山自然恢复方式销号图斑工作指南(试行)",
         doc_number="新自然资源办函〔2024〕219号", publish_date="2024-12-20", implement_date=None,
         summary="荒漠区沙地/裸土地/裸岩石砾地满足无地质灾害、地形协调、无水土污染即可判定",
         rules=[("植被覆盖度", ">=", "周边30%", "必要条件", None),
                ("无地质灾害", "==", "是", "必要条件", None),
                ("地形平缓地貌稳定", "==", "是", "必要条件", None)]),
    dict(category="政策文件", province="广西",
         name="广西壮族自治区历史遗留矿山自然恢复技术指南",
         doc_number="桂自然资办〔2024〕250号", publish_date="2024-12-30", implement_date=None,
         summary="除高陡边坡和裸露岩体外，水土水热条件良好、植被自然恢复趋势明显",
         rules=[("无地质灾害", "==", "是", "必要条件", None),
                ("植被自然恢复趋势", "==", "明显", "必要条件", None),
                ("生产设备拆除完毕", "==", "是", "必要条件", None)]),
    dict(category="政策文件", province="西藏",
         name="西藏自治区历史遗留废弃矿山生态自然恢复认定指导意见（试行）",
         doc_number="藏自然资发〔2025〕19号", publish_date="2025-09-24", implement_date=None,
         summary="含修复成本高、生态修复效益不显著等适用条件",
         rules=[("责任主体", "==", "政府", "必要条件", None),
                ("地形地貌完整与周边协调", "==", "是", "必要条件", None),
                ("无地质灾害", "==", "是", "必要条件", None)]),
]


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


def clean_case():
    """清空案例相关数据（幂等重跑用）。

    indicator_data / score_details 等表未设级联删除，需显式清理。
    """
    from app.models import EvaluationResult, ScoreDetail, ConstraintCheck
    ScoreDetail.query.delete()
    EvaluationResult.query.delete()
    ConstraintCheck.query.delete()
    IndicatorData.query.delete()
    MicroUnit.query.delete()
    ReferenceEcosystem.query.delete()
    MinePatch.query.delete()
    Project.query.delete()
    db.session.commit()


def seed():
    with app.app_context():
        clean_case()

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

        seed_standards()


def seed_standards():
    """写入论文表 1 的 11 项标准与政策文件及其结构化规则。"""
    StandardRule.query.delete()
    Standard.query.delete()
    db.session.commit()

    for s in STANDARDS:
        std = Standard(category=s["category"], province=s["province"],
                       name=s["name"], doc_number=s["doc_number"],
                       publish_date=s["publish_date"],
                       implement_date=s["implement_date"],
                       summary=s["summary"])
        db.session.add(std)
        db.session.flush()
        for item, op, thr, ctype, note in s["rules"]:
            db.session.add(StandardRule(standard_id=std.id, item=item,
                                        operator=op, threshold=thr,
                                        condition_type=ctype, note=note))
    db.session.commit()
    print("已写入标准/政策文件：%d 项，规则 %d 条"
          % (len(STANDARDS), sum(len(s["rules"]) for s in STANDARDS)))


if __name__ == "__main__":
    seed()
