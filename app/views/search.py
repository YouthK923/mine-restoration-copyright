# -*- coding: utf-8 -*-
"""全局搜索：在评价项目、矿山图斑、标准与政策文件中查找关键词。

顶栏的搜索框指向本模块。只做关键词包含匹配，不做分词，
但覆盖名称、编号、行政区、矿种、文号、摘要等常用检索字段。
"""
from sqlalchemy import or_

from flask import Blueprint, render_template, request

from app.models import db, Project, MinePatch, Standard

bp = Blueprint("search", __name__)

LIMIT = 50          # 每类结果上限，避免一次渲染过多


@bp.route("/search")
def index():
    q = (request.args.get("q") or "").strip()
    projects, patches, standards = [], [], []

    if q:
        like = "%" + q + "%"
        projects = Project.query.filter(or_(
            Project.name.like(like),
            Project.code.like(like),
            Project.description.like(like),
        )).order_by(Project.id.desc()).limit(LIMIT).all()

        patches = MinePatch.query.filter(or_(
            MinePatch.name.like(like),
            MinePatch.admin_region.like(like),
            MinePatch.mineral_type.like(like),
        )).order_by(MinePatch.id.desc()).limit(LIMIT).all()

        standards = Standard.query.filter(or_(
            Standard.name.like(like),
            Standard.doc_number.like(like),
            Standard.province.like(like),
            Standard.summary.like(like),
        )).order_by(Standard.id).limit(LIMIT).all()

    total = len(projects) + len(patches) + len(standards)
    return render_template("search.html", q=q, projects=projects,
                           patches=patches, standards=standards, total=total)
