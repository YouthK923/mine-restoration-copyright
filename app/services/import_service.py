# -*- coding: utf-8 -*-
"""指标数据批量导入。

支持 CSV 与 Excel（.xlsx/.xls）。一行对应一个微地质单元，
按「单元类型」匹配图斑内已有的微地质单元后写入指标数据。

表头约定（缺失列按不适用处理）：
    单元类型, 土石比, 土层厚度, pH, 有机质,
    Hg, As, Ni, Cu, Cd, Pb, Cr, Zn,
    植被覆盖度, Shannon, 坡度, 坡向
"""
import csv
import io
import json

from app.utils.constants import HEAVY_METALS, ASPECT_TYPES, UNIT_TYPES

# 表头（顺序即导出模板顺序）
HEADERS = (["单元类型", "土石比", "土层厚度", "pH", "有机质"]
           + list(HEAVY_METALS)
           + ["植被覆盖度", "Shannon", "坡度", "坡向"])

FIELD_ALIASES = {
    "单元类型": "unit_type",
    "土石比": "soil_ratio",
    "土层厚度": "thickness",
    "pH": "ph", "PH": "ph", "ph": "ph",
    "有机质": "organic_matter",
    "植被覆盖度": "coverage",
    "Shannon": "shannon", "shannon": "shannon", "生物多样性": "shannon",
    "坡度": "slope",
    "坡向": "aspect",
}
for _m in HEAVY_METALS:
    FIELD_ALIASES[_m] = "hm_" + _m


def build_template_csv():
    """生成导入模板（含表头与示例行）。"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    # 示例：碎石边坡一行，说明每列含义
    row = {h: "" for h in HEADERS}
    row.update({"单元类型": "碎石边坡", "土石比": "0.34", "土层厚度": "10",
                "pH": "9.24", "有机质": "4.89", "Hg": "0.05", "As": "5.17",
                "Ni": "12.60", "Cu": "11.70", "Cd": "0.04", "Pb": "6.50",
                "植被覆盖度": "87.92", "Shannon": "0.60",
                "坡度": "28.75", "坡向": "阳坡"})
    w.writerow([row[h] for h in HEADERS])
    return buf.getvalue()


def _read_rows(filename, stream):
    """读取上传文件为「表头 -> 值」的字典列表。"""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        text = stream.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return [dict(r) for r in reader]
    if ext in ("xlsx", "xls"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(stream.read()), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        out = []
        for r in rows[1:]:
            if all(c is None or str(c).strip() == "" for c in r):
                continue
            out.append({header[i]: (r[i] if i < len(r) else None)
                        for i in range(len(header)) if header[i]})
        return out
    raise ValueError("不支持的文件类型：.%s" % ext)


def _num(value):
    if value is None:
        return None, None
    s = str(value).strip()
    if s == "":
        return None, None
    try:
        return float(s), None
    except ValueError:
        return None, "「%s」不是有效数值" % s


def parse_upload(filename, stream, unit_type_map):
    """解析上传文件。

    参数
    ----
    unit_type_map : dict，{单元类型: MicroUnit 对象}

    返回
    ----
    (parsed, errors)
      parsed : list[dict]，每项 {unit_type, fields{...}, heavy_metals{}}
      errors : list[str]，逐行问题说明
    """
    rows = _read_rows(filename, stream)
    parsed, errors = [], []
    if not rows:
        return [], ["文件为空或没有数据行"]

    # 表头校验
    unknown = [h for h in (rows[0].keys() if rows else []) if h not in FIELD_ALIASES]
    if unknown:
        errors.append("存在无法识别的列，将被忽略：%s" % "、".join(map(str, unknown)))

    for idx, raw in enumerate(rows, start=2):     # 第 1 行是表头
        rec = {}
        for k, v in raw.items():
            key = FIELD_ALIASES.get(str(k).strip())
            if key:
                rec[key] = v

        unit_type = str(rec.get("unit_type") or "").strip()
        if not unit_type:
            errors.append("第 %d 行：缺少「单元类型」" % idx)
            continue
        if unit_type not in unit_type_map:
            errors.append("第 %d 行：图斑内不存在单元类型「%s」（现有：%s）"
                          % (idx, unit_type, "、".join(unit_type_map) or "无"))
            continue
        if unit_type not in UNIT_TYPES:
            errors.append("第 %d 行：单元类型「%s」不是系统支持的三种之一"
                          % (idx, unit_type))
            continue

        fields, heavy = {}, {}
        ok = True
        for key, val in rec.items():
            if key in ("unit_type",):
                continue
            if key.startswith("hm_"):
                n, err = _num(val)
                if err:
                    errors.append("第 %d 行：%s %s" % (idx, key[3:], err))
                    ok = False
                elif n is not None:
                    heavy[key[3:]] = n
                continue
            if key == "aspect":
                s = str(val).strip() if val is not None else ""
                if s == "":
                    fields["aspect"] = None
                elif s in ASPECT_TYPES:
                    fields["aspect"] = s
                else:
                    errors.append("第 %d 行：坡向「%s」无效（应为 %s）"
                                  % (idx, s, "、".join(ASPECT_TYPES)))
                    ok = False
                continue
            n, err = _num(val)
            if err:
                errors.append("第 %d 行：%s %s" % (idx, key, err))
                ok = False
            else:
                fields[key] = n

        if ok:
            parsed.append({"unit_type": unit_type, "fields": fields,
                           "heavy_metals": heavy})

    return parsed, errors
