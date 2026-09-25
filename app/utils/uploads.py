# -*- coding: utf-8 -*-
"""上传文件处理（M2 遥感影像、M7 批量导入）。"""
import os
import re
import uuid
from datetime import datetime

from werkzeug.utils import secure_filename


def _safe_ext(filename):
    return os.path.splitext(filename)[1].lower().lstrip(".")


def ext_allowed(filename, allowed):
    return _safe_ext(filename) in allowed


def save_upload(file_storage, subdir, allowed_ext, upload_root):
    """保存上传文件，返回相对 static 的路径（如 uploads/patches/xxx.png）。

    文件名重命名为「时间戳_随机串.扩展名」，避免中文名与重名问题。
    """
    if file_storage is None or not file_storage.filename:
        return None, "未选择文件"
    ext = _safe_ext(file_storage.filename)
    if ext not in allowed_ext:
        return None, "不支持的文件类型：.%s" % ext

    target_dir = os.path.join(upload_root, subdir)
    os.makedirs(target_dir, exist_ok=True)

    # 仅保留安全字符，并加时间戳与随机串防重名
    base = secure_filename(os.path.splitext(file_storage.filename)[0]) or "file"
    base = re.sub(r"[^A-Za-z0-9_\-]", "", base)[:40] or "file"
    name = "%s_%s.%s" % (datetime.now().strftime("%Y%m%d%H%M%S"),
                         uuid.uuid4().hex[:6], ext)
    abs_path = os.path.join(target_dir, name)
    file_storage.save(abs_path)

    rel = os.path.join("uploads", subdir, name).replace("\\", "/")
    return rel, None


def remove_upload(rel_path, upload_root):
    """删除已保存的上传文件（相对 static 的路径）。"""
    if not rel_path:
        return
    abs_path = os.path.join(upload_root, rel_path.replace("uploads/", "", 1))
    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except OSError:
        pass
