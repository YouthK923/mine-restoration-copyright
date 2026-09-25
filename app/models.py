# -*- coding: utf-8 -*-
"""数据模型：系统全部数据表。

本文件由甲在阶段 0 一次性写完，作为两人独立开发的地基。
约定：两人只读此文件；确需改表时，由乙提需求、甲统一修改。
"""
import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """用户（M1 用户与权限管理）。"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    # 角色：管理员 admin / 评价员 evaluator / 查看者 viewer
    role = db.Column(db.String(20), nullable=False, default="viewer")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "username": self.username,
                "role": self.role, "active": self.active}


class OperationLog(db.Model):
    """操作日志（M1）。"""
    __tablename__ = "operation_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(128), nullable=False)      # 操作类型
    target_type = db.Column(db.String(64), nullable=True)   # 对象类型
    target_id = db.Column(db.Integer, nullable=True)        # 对象主键
    detail = db.Column(db.Text, nullable=True)              # 操作详情
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Project(db.Model):
    """评价项目（M2 项目与矿山档案）。"""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(64), nullable=True)           # 项目编号
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="进行中")       # 进行中 / 已完成 / 已归档
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patches = db.relationship("MinePatch", backref="project", lazy="dynamic",
                              cascade="all, delete-orphan")


class MinePatch(db.Model):
    """矿山图斑（M2）。"""
    __tablename__ = "mine_patches"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    admin_region = db.Column(db.String(128), nullable=True)   # 所在行政区
    center_x = db.Column(db.Float, nullable=True)             # 中心经度/横坐标
    center_y = db.Column(db.Float, nullable=True)             # 中心纬度/纵坐标
    area_ha = db.Column(db.Float, nullable=True)              # 图斑面积（公顷）
    mineral_type = db.Column(db.String(64), nullable=True)    # 开采矿种
    mining_method = db.Column(db.String(64), nullable=True)   # 开采方式
    stop_years = db.Column(db.Float, nullable=True)           # 停产年限
    responsible_entity_missing = db.Column(db.Boolean, default=True)  # 责任主体是否缺失
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    units = db.relationship("MicroUnit", backref="patch", lazy="dynamic",
                            cascade="all, delete-orphan")


class ReferenceEcosystem(db.Model):
    """参照生态系统（M2）：标准化基准值，与图斑绑定。"""
    __tablename__ = "reference_ecosystems"

    id = db.Column(db.Integer, primary_key=True)
    patch_id = db.Column(db.Integer, db.ForeignKey("mine_patches.id"), nullable=False)
    coverage_benchmark = db.Column(db.Float, default=75.0)     # 植被覆盖度基准 %
    shannon_benchmark = db.Column(db.Float, default=0.7)       # Shannon-Wiener 基准
    dominant_species = db.Column(db.String(256), nullable=True)  # 建群种
    soil_benchmark = db.Column(db.String(256), nullable=True)    # 土壤基准


class Standard(db.Model):
    """地方标准/政策文件（M3 政策与标准知识库）。"""
    __tablename__ = "standards"

    id = db.Column(db.Integer, primary_key=True)
    province = db.Column(db.String(32), nullable=False)         # 省份
    name = db.Column(db.String(256), nullable=False)            # 名称
    doc_number = db.Column(db.String(128), nullable=True)       # 标准编号/文号
    publish_date = db.Column(db.String(32), nullable=True)
    implement_date = db.Column(db.String(32), nullable=True)
    # 类别：地方标准 / 政策文件
    category = db.Column(db.String(32), nullable=False, default="地方标准")
    summary = db.Column(db.Text, nullable=True)                 # 特点概述


class StandardRule(db.Model):
    """结构化规则（M3）：将标准条文拆解为可执行规则。"""
    __tablename__ = "standard_rules"

    id = db.Column(db.Integer, primary_key=True)
    standard_id = db.Column(db.Integer, db.ForeignKey("standards.id"), nullable=False)
    item = db.Column(db.String(128), nullable=False)            # 判定项
    operator = db.Column(db.String(8), nullable=False)          # 比较符：> >= < <= ==
    threshold = db.Column(db.String(64), nullable=True)         # 阈值
    condition_type = db.Column(db.String(32), default="必要条件")  # 必要条件/充分条件
    region = db.Column(db.String(64), nullable=True)            # 适用分区（宁夏分区差异化）
    note = db.Column(db.Text, nullable=True)


class ConstraintCheck(db.Model):
    """限制性判定记录（M4）。"""
    __tablename__ = "constraint_checks"

    id = db.Column(db.Integer, primary_key=True)
    patch_id = db.Column(db.Integer, db.ForeignKey("mine_patches.id"), nullable=False)
    policy_pass = db.Column(db.Boolean, nullable=True)         # 政策约束
    location_pass = db.Column(db.Boolean, nullable=True)       # 区位约束
    pollution_pass = db.Column(db.Boolean, nullable=True)      # 土壤污染
    geo_pass = db.Column(db.Boolean, nullable=True)            # 地质灾害
    farmland_pass = db.Column(db.Boolean, nullable=True)       # 耕地属性
    passed = db.Column(db.Boolean, nullable=True)              # 总体是否通过
    reason = db.Column(db.Text, nullable=True)                 # 不通过原因
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)


class MicroUnit(db.Model):
    """微地质单元（M5）：岩质边坡 / 碎石边坡 / 平台。"""
    __tablename__ = "micro_units"

    id = db.Column(db.Integer, primary_key=True)
    patch_id = db.Column(db.Integer, db.ForeignKey("mine_patches.id"), nullable=False)
    unit_type = db.Column(db.String(32), nullable=False)        # 单元类型
    area = db.Column(db.Float, nullable=True)                   # 面积
    ratio = db.Column(db.Float, nullable=True)                  # 面积占比（自动计算）
    description = db.Column(db.Text, nullable=True)             # 现场描述


class Indicator(db.Model):
    """指标定义（M6）：指标树，含角色与启用单元类型。"""
    __tablename__ = "indicators"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)  # 指标编码
    name = db.Column(db.String(64), nullable=False)               # 指标名称
    level = db.Column(db.Integer, nullable=False)                 # 1/2/3 级
    parent_code = db.Column(db.String(32), nullable=True)         # 父指标编码
    # 角色：土壤污染指标同时作为限制性指标与评价指标
    is_constraint = db.Column(db.Boolean, default=False)
    is_evaluative = db.Column(db.Boolean, default=True)
    unit = db.Column(db.String(32), nullable=True)                # 单位
    ideal_value = db.Column(db.String(64), nullable=True)         # 理想值（可配置）
    ideal_type = db.Column(db.String(32), nullable=True)          # 标准化类型：benefit/cost/mid/discrete


class WeightScheme(db.Model):
    """权重方案（M6）：按微地质单元类型分别保存。"""
    __tablename__ = "weight_schemes"

    id = db.Column(db.Integer, primary_key=True)
    unit_type = db.Column(db.String(32), nullable=False)          # 所属单元类型
    name = db.Column(db.String(64), nullable=True)                # 方案名称
    level = db.Column(db.Integer, nullable=False, default=1)      # 1=一级指标 2=二级指标
    is_default = db.Column(db.Boolean, default=False)             # 是否默认（论文表 3）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WeightItem(db.Model):
    """权重明细（M6）：方案内的各项权重。"""
    __tablename__ = "weight_items"

    id = db.Column(db.Integer, primary_key=True)
    scheme_id = db.Column(db.Integer, db.ForeignKey("weight_schemes.id"), nullable=False)
    indicator_code = db.Column(db.String(32), nullable=False)     # 指标编码
    weight = db.Column(db.Float, nullable=False)                  # 权重值


class ExpertMatrix(db.Model):
    """专家判断矩阵（M6）：多专家打分的原始矩阵。"""
    __tablename__ = "expert_matrices"

    id = db.Column(db.Integer, primary_key=True)
    scheme_id = db.Column(db.Integer, db.ForeignKey("weight_schemes.id"), nullable=False)
    expert_name = db.Column(db.String(64), nullable=True)         # 专家姓名
    level = db.Column(db.Integer, nullable=False, default=1)      # 矩阵对应指标层级
    matrix_json = db.Column(db.Text, nullable=False)              # 判断矩阵（JSON 二维数组）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class IndicatorData(db.Model):
    """指标实测数据（M7）：按微地质单元组织。"""
    __tablename__ = "indicator_data"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("micro_units.id"), nullable=False, unique=True)
    soil_ratio = db.Column(db.Float, nullable=True)               # 土石比
    thickness = db.Column(db.Float, nullable=True)                # 土层厚度 cm
    ph = db.Column(db.Float, nullable=True)
    organic_matter = db.Column(db.Float, nullable=True)           # 有机质 g/kg
    # 重金属含量，JSON 字符串：{"Hg": 0.05, ...}，未检测项缺失或为 null
    heavy_metals = db.Column(db.Text, nullable=True)
    coverage = db.Column(db.Float, nullable=True)                 # 植被覆盖度 %
    shannon = db.Column(db.Float, nullable=True)                  # Shannon-Wiener 多样性指数
    slope = db.Column(db.Float, nullable=True)                    # 坡度 °
    aspect = db.Column(db.String(16), nullable=True)              # 坡向：阳坡/阴阳坡/阴坡

    def heavy_metals_dict(self):
        return json.loads(self.heavy_metals) if self.heavy_metals else {}


class EvaluationResult(db.Model):
    """评价结果（M8）。"""
    __tablename__ = "evaluation_results"

    id = db.Column(db.Integer, primary_key=True)
    patch_id = db.Column(db.Integer, db.ForeignKey("mine_patches.id"), nullable=False)
    final_score = db.Column(db.Float, nullable=True)              # 最终评价因子 F
    grade = db.Column(db.String(32), nullable=True)               # 适宜性等级
    measures = db.Column(db.Text, nullable=True)                  # 推荐措施
    unit_scores = db.Column(db.Text, nullable=True)               # 各单元得分 JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ScoreDetail(db.Model):
    """得分明细（M8）：每一层指标的权重、标准化值、加权贡献，供追溯与复核。"""
    __tablename__ = "score_details"

    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey("evaluation_results.id"), nullable=False)
    unit_id = db.Column(db.Integer, nullable=True)
    l1_name = db.Column(db.String(64), nullable=True)             # 一级指标
    l2_name = db.Column(db.String(64), nullable=True)             # 二级指标
    raw_value = db.Column(db.String(64), nullable=True)           # 实测值
    std_value = db.Column(db.Float, nullable=True)                # 标准化值
    weight = db.Column(db.Float, nullable=True)                   # 权重
    contribution = db.Column(db.Float, nullable=True)             # 加权贡献
