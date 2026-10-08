# -*- coding: utf-8 -*-
r"""打两个交付物：一是可运行的完整系统，二是要提交的软著材料。

   交付包/
   ├── 历史遗留废弃矿山自然恢复适宜性评价系统V1.0_完整系统.zip
   │   └── 历史遗留废弃矿山自然恢复适宜性评价系统V1.0\
   │       ├── 历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe   双击即用
   │       ├── 使用说明.txt
   │       ├── 启动（免安装）.bat        exe 被拦时的备用入口
   │       ├── portable_runtime\         内嵌 Python 与依赖（免安装）
   │       └── app\ run.py seed_demo.py requirements.txt
   └── 历史遗留废弃矿山自然恢复适宜性评价系统V1.0_提交材料.zip
       └── 提交材料\  源程序提交版 PDF、说明书 PDF、登记信息表底稿

前置：先跑 `python 工具/构建免安装运行时.py` 与 `python 工具/打包exe.py`。
"""
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\自然恢复软著")
OUT = ROOT / "交付包"
RUNTIME = ROOT / "portable_runtime"
EXE = ROOT / "构建缓存" / "dist" / "历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe"
NAME = "历史遗留废弃矿山自然恢复适宜性评价系统V1.0"
SYSTEM_ZIP = OUT / (NAME + "_完整系统.zip")
SUBMIT_ZIP = OUT / (NAME + "_提交材料.zip")

SYSTEM_FILES = ["启动（免安装）.bat", "run.py", "seed_demo.py", "requirements.txt"]
SUBMIT_FILES = [
    "软著材料/源程序_提交版（前30页+后30页）_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf",
    "软著材料/说明书_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf",
    "软著材料/登记信息表底稿.docx",
]
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_FILES = {"app.db", ".secret_key", "启动日志.txt"}

USAGE = """历史遗留废弃矿山自然恢复适宜性评价系统 V1.0
============================================

1. 双击「历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe」
2. 等十几秒，浏览器自动打开 http://127.0.0.1:5000
3. 演示账号 admin / admin123 ；关闭小窗口即退出系统

不用装 Python、不用联网、不用管理员权限。
若 Windows 提示「已保护你的电脑」，点「更多信息 → 仍要运行」。
出问题看同目录的 启动日志.txt，或先运行：
    "历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe" --check
也可以用备用入口「启动（免安装）.bat」启动。
"""

SUBMIT_README = """软著登记提交材料
================

1. 源程序_提交版（前30页+后30页）_……V1.0.pdf   源程序鉴别材料，60 页
2. 说明书_……V1.0.pdf                        文档鉴别材料，31 页
3. 登记信息表底稿.docx                        申请表字段底稿

提交时用上面两份 PDF。底稿里标「待填」的四项需人工确定：
著作权人、开发完成日期、首次发表日期、经办人信息与诚信声明。
"""


def add_tree(z, src_root, arc_root, skip_data=True):
    n = 0
    for f in sorted(Path(src_root).rglob("*")):
        if not f.is_file() or any(p in EXCLUDE_DIRS for p in f.parts):
            continue
        if skip_data and (f.name in SKIP_FILES or f.suffix == ".pyc"):
            continue
        z.write(f, "%s/%s" % (arc_root, f.relative_to(src_root).as_posix()))
        n += 1
    return n


def build_system():
    if not EXE.exists() or not RUNTIME.is_dir():
        raise SystemExit("缺少构建产物：请先运行 工具/构建免安装运行时.py "
                         "与 工具/打包exe.py")
    if SYSTEM_ZIP.exists():
        SYSTEM_ZIP.unlink()
    with zipfile.ZipFile(SYSTEM_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(EXE, "%s/%s.exe" % (NAME, NAME))
        z.writestr("%s/使用说明.txt" % NAME, USAGE.encode("utf-8"))
        for rel in SYSTEM_FILES:
            p = ROOT / rel
            if p.exists():
                z.write(p, "%s/%s" % (NAME, p.name))
        add_tree(z, ROOT / "app", NAME + "/app")
        add_tree(z, RUNTIME, NAME + "/portable_runtime")
    print("完整系统：%s（%.1f MB）" % (SYSTEM_ZIP.name,
                                    SYSTEM_ZIP.stat().st_size / 1048576))
    with zipfile.ZipFile(SYSTEM_ZIP) as z:
        print("   文件 %d 个" % len(z.namelist()))


def build_submit():
    if SUBMIT_ZIP.exists():
        SUBMIT_ZIP.unlink()
    with zipfile.ZipFile(SUBMIT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("提交材料/说明.txt", SUBMIT_README.encode("utf-8"))
        for rel in SUBMIT_FILES:
            p = ROOT / rel
            if not p.exists():
                raise SystemExit("缺少材料：%s" % p)
            z.write(p, "提交材料/%s" % p.name)
    print("提交材料：%s（%.1f MB）" % (SUBMIT_ZIP.name,
                                    SUBMIT_ZIP.stat().st_size / 1048576))
    with zipfile.ZipFile(SUBMIT_ZIP) as z:
        for n in z.namelist():
            print("   %s" % n)


def clean_old():
    """删掉旧的交付物与临时目录，只留上面两个 zip。"""
    for p in sorted(OUT.iterdir()):
        if p in (SYSTEM_ZIP, SUBMIT_ZIP):
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        print("已删除：%s" % p.name)


def main():
    OUT.mkdir(exist_ok=True)
    build_system()
    build_submit()
    print()
    clean_old()
    print()
    print("交付包/：")
    for p in sorted(OUT.iterdir()):
        print("   %-64s %6.1f MB" % (p.name, p.stat().st_size / 1048576))


if __name__ == "__main__":
    main()
