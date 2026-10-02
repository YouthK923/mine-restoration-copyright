# -*- coding: utf-8 -*-
"""数据模型：系统全部数据表。

本文件由甲在阶段 0 一次性写完，作为两人独立开发的地基。
约定：两人只读此文件；确需改表时，由乙提需求、甲统一修改。
"""
import json

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

from app.utils.timefmt import utcnow   # 替代已弃用的 datetime.utcnow()

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """用户（账户与权限）。"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    # 职务只有两种：管理员 admin（可管理账号与他人的职务）/ 操作员 operator
    role = db.Column(db.String(20), nullable=False, default="operator")
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    # ---- 个人资料（用户可在「个人设置」里自行维护）----
    display_name = db.Column(db.String(64), nullable=True)    # 昵称
    email = db.Column(db.String(128), nullable=True)
    phone = db.Column(db.String(32), nullable=True)
    gender = db.Column(db.String(8), nullable=True)           # 男 / 女 / 保密
    avatar = db.Column(db.String(256), nullable=True)         # 头像，相对 static 的路径

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def shown_name(self):
        """界面上显示的名字：优先用昵称，没填就用账号名。"""
        return self.display_name or self.username

    @property
    def initial(self):
        """没有头像时用首字占位。"""
        return (self.shown_name or "?")[0].upper()

    def to_dict(self):
        return {"id": self.id, "username": self.username,
                "display_name": self.display_name, "gender": self.gender,
                "role": self.role, "active": self.active}


class OperationLog(db.Model):
    """操作日志。"""
    __tablename__ = "operation_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(128), nullable=False)      # 操作类型
    target_type = db.Column(db.String(64), nullable=True)   # 对象类型
    target_id = db.Column(db.Integer, nullable=True)        # 对象主键
    detail = db.Column(db.Text, nullable=True)              # 操作详情
    created_at = db.Column(db.DateTime, default=utcnow, index=True)


class Project(db.Model):
    """评价项目（项目与矿山档案）。"""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(64), nullable=True)           # 项目编号
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="进行中")       # 进行中 / 已完成 / 已归档
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    patches = db.relationship("MinePatch", backref="project", lazy="dynamic",
                              cascade="all, delete-orphan")


class MinePatch(db.Model):
    """矿山图斑。"""
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
    # 遥感底图 / 无人机正射影像挂接
    image_path = db.Column(db.String(256), nullable=True)     # 相对 static 的路径
    image_note = db.Column(db.String(256), nullable=True)     # 影像说明（如来源、时相）
    image_uploaded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    units = db.relationship("MicroUnit", backref="patch", lazy="dynamic",
                            cascade="all, delete-orphan")


class ReferenceEcosystem(db.Model):
    """参照生态系统：标准化基准值，与图斑绑定。"""
    __tablename__ = "reference_ecosystems"

    id = db.Column(db.Integer, primary_key=True)
    patch_id = db.Column(db.Integer, db.ForeignKey("mine_patches.id"), nullable=False)
    coverage_benchmark = db.Column(db.Float, default=75.0)     # 植被覆盖度基准 %
    shannon_benchmark = db.Column(db.Float, default=0.7)       # Shannon-Wiener 基准
    dominant_species = db.Column(db.String(256), nullable=True)  # 建群种
    soil_benchmark = db.Column(db.String(256), nullable=True)    # 土壤基准


class Standard(db.Model):
    """地方标准/政策文件（政策与标准知识库）。"""
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

    rules = db.relationship("StandardRule", backref="standard",
                            cascade="all, delete-orphan")


class StandardRule(db.Model):
    """结构化规则：将标准条文拆解为可执行规则。"""
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
    """限制性判定记录。"""
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
    checked_at = db.Column(db.DateTime, default=utcnow)


class MicroUnit(db.Model):
    """微地质单元：岩质边坡 / 碎石边坡 / 平台。"""
    __tablename__ = "micro_units"

    id = db.Column(db.Integer, primary_key=True)
    patch_id = db.Column(db.Integer, db.ForeignKey("mine_patches.id"), nullable=False)
    unit_type = db.Column(db.String(32), nullable=False)        # 单元类型
    area = db.Column(db.Float, nullable=True)                   # 面积
    ratio = db.Column(db.Float, nullable=True)                  # 面积占比（自动计算）
    description = db.Column(db.Text, nullable=True)             # 现场描述


class Indicator(db.Model):
    """指标定义：指标树，含角色与启用单元类型。"""
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
    ideal_type = db.Column(db.String(32), nullable=True)          # benefit/cost/mid/discrete
    # 启用该指标的微地质单元（逗号分隔）。岩质边坡不启用土壤指标、平台不启用地形指标
    enabled_units = db.Column(db.String(128), nullable=True)
    description = db.Column(db.Text, nullable=True)               # 取值依据说明

    def units_list(self):
        return [s for s in (self.enabled_units or "").split(",") if s]


class WeightScheme(db.Model):
    """权重方案：按微地质单元类型分别保存。"""
    __tablename__ = "weight_schemes"

    id = db.Column(db.Integer, primary_key=True)
    unit_type = db.Column(db.String(32), nullable=False)          # 所属单元类型
    name = db.Column(db.String(64), nullable=True)                # 方案名称
    level = db.Column(db.Integer, nullable=False, default=1)      # 1=一级指标 2=二级指标
    is_default = db.Column(db.Boolean, default=False)             # 是否默认（系统默认）
    created_at = db.Column(db.DateTime, default=utcnow)


class WeightItem(db.Model):
    """权重明细：方案内的各项权重。"""
    __tablename__ = "weight_items"

    id = db.Column(db.Integer, primary_key=True)
    scheme_id = db.Column(db.Integer, db.ForeignKey("weight_schemes.id"), nullable=False)
    indicator_code = db.Column(db.String(32), nullable=False)     # 指标编码
    weight = db.Column(db.Float, nullable=False)                  # 权重值


class ExpertMatrix(db.Model):
    """专家判断矩阵：多专家打分的原始矩阵。"""
    __tablename__ = "expert_matrices"

    id = db.Column(db.Integer, primary_key=True)
    scheme_id = db.Column(db.Integer, db.ForeignKey("weight_schemes.id"), nullable=True)
    # 直接标注适用对象，便于无需先建权重方案即可录入专家矩阵
    unit_type = db.Column(db.String(32), nullable=True)           # 微地质单元类型
    l1_name = db.Column(db.String(64), nullable=True)             # 所属一级指标（二级矩阵用）
    expert_name = db.Column(db.String(64), nullable=True)         # 专家姓名
    specialty = db.Column(db.String(64), nullable=True)             # 专家专业
    level = db.Column(db.Integer, nullable=False, default=1)      # 矩阵对应指标层级
    matrix_json = db.Column(db.Text, nullable=False)              # 判断矩阵（JSON 二维数组）
    cr = db.Column(db.Float, nullable=True)                       # 该专家矩阵的一致性比例
    created_at = db.Column(db.DateTime, default=utcnow)


class IndicatorData(db.Model):
    """指标实测数据：按微地质单元组织。"""
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
        """把重金属 JSON 解析成字典。

        字段是手工可改的文本，被脏写或导入半个 JSON 时不能让整页 500：
        解析失败按「未检测」处理（空字典），并把原文留在库里供排查。
        """
        if not self.heavy_metals:
            return {}
        try:
            data = json.loads(self.heavy_metals)
        except (ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}


class EvaluationResult(db.Model):
    """评价结果。"""
    __tablename__ = "evaluation_results"

    id = db.Column(db.Integer, primary_key=True)
    patch_id = db.Column(db.Integer, db.ForeignKey("mine_patches.id"), nullable=False)
    final_score = db.Column(db.Float, nullable=True)              # 最终评价因子 F
    grade = db.Column(db.String(32), nullable=True)               # 适宜性等级
    measures = db.Column(db.Text, nullable=True)                  # 推荐措施
    unit_scores = db.Column(db.Text, nullable=True)               # 各单元得分 JSON
    # 计算参数快照：本次用的权重来源、参照生态系统基准、各指标理想取值。
    # 参数现在可以在界面上改，不留快照就无法复现这一次的结果。
    params_json = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)


class ScoreDetail(db.Model):
    """得分明细：每一层指标的权重、标准化值、加权贡献，供追溯与复核。"""
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
