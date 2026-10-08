# -*- coding: utf-8 -*-
r"""打一个交付包：完整系统 + 提交材料，并同时留一份解压后的文件夹便于查看。

   交付包/
   ├── 历史遗留废弃矿山自然恢复适宜性评价系统V1.0.zip      ← 发这一个
   └── 历史遗留废弃矿山自然恢复适宜性评价系统V1.0/          ← 同一个包解压后的样子

zip 内部：
   历史遗留废弃矿山自然恢复适宜性评价系统V1.0/
   ├── 完整系统\   双击 exe 即可用（内嵌 Python，免安装）
   └── 提交材料\   源程序提交版 PDF、说明书 PDF、登记信息表底稿

前置：先跑 `python 工具/构建免安装运行时.py` 与 `python 工具/打包exe.py`。
"""
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\自然恢复软著")
OUT = ROOT / "交付包"
RUNTIME = ROOT / "portable_runtime"
EXE = ROOT / "构建缓存" / "dist" / "历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe"
BASE = "历史遗留废弃矿山自然恢复适宜性评价系统V1.0"
ZIP = OUT / (BASE + ".zip")
FOLDER = OUT / BASE

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


def copy_tree(src_root, dst_root, skip_data=True):
    n = 0
    for f in sorted(Path(src_root).rglob("*")):
        if not f.is_file() or any(p in EXCLUDE_DIRS for p in f.parts):
            continue
        if skip_data and (f.name in SKIP_FILES or f.suffix == ".pyc"):
            continue
        dst = Path(dst_root) / f.relative_to(src_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        n += 1
    return n


def build_folder():
    if not EXE.exists() or not RUNTIME.is_dir():
        raise SystemExit("缺少构建产物：请先运行 工具/构建免安装运行时.py "
                         "与 工具/打包exe.py")
    if FOLDER.exists():
        shutil.rmtree(FOLDER)
    system = FOLDER / "完整系统"
    submit = FOLDER / "提交材料"
    system.mkdir(parents=True)
    submit.mkdir(parents=True)

    shutil.copy2(EXE, system / (BASE + ".exe"))
    (system / "使用说明.txt").write_text(USAGE, encoding="utf-8", newline="\r\n")
    for rel in SYSTEM_FILES:
        p = ROOT / rel
        if p.exists():
            shutil.copy2(p, system / p.name)
    n_app = copy_tree(ROOT / "app", system / "app")
    n_rt = copy_tree(RUNTIME, system / "portable_runtime")

    (submit / "说明.txt").write_text(SUBMIT_README, encoding="utf-8", newline="\r\n")
    for rel in SUBMIT_FILES:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit("缺少材料：%s" % p)
        shutil.copy2(p, submit / p.name)

    files = [f for f in FOLDER.rglob("*") if f.is_file()]
    print("解压目录：%s" % FOLDER.name)
    print("   完整系统  %d 个文件（app %d、运行时 %d）" % (n_app + n_rt + 6, n_app, n_rt))
    print("   提交材料  %d 个文件" % (len(SUBMIT_FILES) + 1))
    print("   合计 %d 个文件，%.1f MB"
          % (len(files), sum(f.stat().st_size for f in files) / 1048576))


def do_zip():
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(FOLDER.rglob("*")):
            if f.is_file():
                z.write(f, "%s/%s" % (BASE, f.relative_to(FOLDER).as_posix()))
    print("压缩包：%s（%.1f MB，%d 个文件）"
          % (ZIP.name, ZIP.stat().st_size / 1048576, len(zipfile.ZipFile(ZIP).namelist())))


def clean_old():
    for p in sorted(OUT.iterdir()):
        if p in (ZIP, FOLDER):
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        print("已删除：%s" % p.name)


def main():
    OUT.mkdir(exist_ok=True)
    build_folder()
    do_zip()
    clean_old()
    print()
    print("交付包/：")
    for p in sorted(OUT.iterdir()):
        print("   %-56s %s" % (p.name, "文件夹" if p.is_dir()
                              else "%.1f MB" % (p.stat().st_size / 1048576)))


if __name__ == "__main__":
    main()
