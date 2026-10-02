# -*- coding: utf-8 -*-
"""权重方案的存取与生效权重解析。

系统有两套权重来源：

1. 系统内置的默认权重（app.utils.constants.DEFAULT_WEIGHTS），
   是**权威取值来源**，案例复算与报告结论以此为准；
2. 通过层次分析法在本系统中实际算出的权重，保存在
   weight_schemes / weight_items 两张表中，可标记为「生效」。

本模块负责把这两者合成为计算引擎直接可用的嵌套权重结构：
以系统内置权重为底，用生效方案中已保存的条目覆盖。
没有任何生效方案时，即完全使用系统内置权重。

这样既保证默认行为与内置取值一致，又使 AHP 计算结果真正参与评价，
而不是算完即弃。
"""
import copy

from app.models import db, WeightScheme, WeightItem
from app.utils.constants import DEFAULT_WEIGHTS
from app.services.indicator_service import TREE

# 方案名称：每个微地质单元类型固定一个可生效的方案
ACTIVE_NAME = "自定义权重方案（AHP 计算结果）"


def _code_maps():
    """由指标树导出 编码 → 名称 的映射，避免名称在两处各写一遍。"""
    l1, l2 = {}, {}
    for row in TREE:
        code, name, level, parent = row[0], row[1], row[2], row[3]
        if level == 1:
            l1[code] = name
        elif level == 2:
            l2[code] = (l1.get(parent, parent), name)
    return l1, l2


def effective_weights(unit_type):
    """返回该单元类型当前生效的权重。

    返回 (weights, source_label, scheme)
        weights      嵌套权重结构，可直接交给标准化与评价引擎
        source_label 权重来源说明，用于界面与报告标注
        scheme       生效的权重方案对象，无自定义方案时为 None
    """
    base = DEFAULT_WEIGHTS.get(unit_type)
    if base is None:
        return None, "未定义该微地质单元类型的权重", None

    scheme = WeightScheme.query.filter_by(unit_type=unit_type,
                                          name=ACTIVE_NAME).first()
    if scheme is None:
        return copy.deepcopy(base), "系统默认权重", None

    merged = copy.deepcopy(base)
    l1_map, l2_map = _code_maps()
    applied = 0
    for item in WeightItem.query.filter_by(scheme_id=scheme.id).all():
        code, w = item.indicator_code, item.weight
        if w is None or w <= 0:
            continue
        if code in l1_map and l1_map[code] in merged["l1"]:
            merged["l1"][l1_map[code]] = w
            applied += 1
        elif code in l2_map:
            l1_name, l2_name = l2_map[code]
            if l1_name in merged["l2"] and l2_name in merged["l2"][l1_name]:
                merged["l2"][l1_name][l2_name] = w
                applied += 1

    if applied == 0:
        return copy.deepcopy(base), "系统默认权重", None
    return merged, "自定义方案（%d 项覆盖系统内置权重）" % applied, scheme


def save_weights(unit_type, code_weight_pairs, note=None):
    """把一组「指标编码 → 权重」写入生效方案（已存在则更新对应条目）。

    仅覆盖本次传入的条目，其余条目保留，便于分层次（一级 / 二级）
    分次录入而无需一次填完。
    """
    scheme = WeightScheme.query.filter_by(unit_type=unit_type,
                                          name=ACTIVE_NAME).first()
    if scheme is None:
        scheme = WeightScheme(unit_type=unit_type, name=ACTIVE_NAME,
                              level=1, is_default=True)
        db.session.add(scheme)
        db.session.flush()
    if note:
        scheme.level = scheme.level or 1
    if not scheme.is_default:
        scheme.is_default = True

    written = 0
    for code, w in code_weight_pairs:
        if w is None or w <= 0:
            continue
        item = WeightItem.query.filter_by(scheme_id=scheme.id,
                                          indicator_code=code).first()
        if item is None:
            item = WeightItem(scheme_id=scheme.id, indicator_code=code)
            db.session.add(item)
        item.weight = float(w)
        written += 1
    db.session.commit()
    return scheme, written


def reset_weights(unit_type):
    """删除该单元类型的自定义方案，恢复为系统默认权重。"""
    schemes = WeightScheme.query.filter_by(unit_type=unit_type,
                                           name=ACTIVE_NAME).all()
    n = 0
    for s in schemes:
        WeightItem.query.filter_by(scheme_id=s.id).delete(
            synchronize_session=False)
        db.session.delete(s)
        n += 1
    db.session.commit()
    return n


def scheme_items(unit_type):
    """返回该单元类型已保存的自定义权重条目 {指标编码: 权重}。"""
    scheme = WeightScheme.query.filter_by(unit_type=unit_type,
                                          name=ACTIVE_NAME).first()
    if scheme is None:
        return {}, None
    items = {i.indicator_code: i.weight
             for i in WeightItem.query.filter_by(scheme_id=scheme.id).all()}
    return items, scheme


def summary():
    """各单元类型的权重来源概览，供权重首页展示。"""
    rows = []
    for unit_type in DEFAULT_WEIGHTS:
        weights, label, scheme = effective_weights(unit_type)
        rows.append({
            "unit_type": unit_type,
            "label": label,
            "custom": scheme is not None,
        })
    return rows
