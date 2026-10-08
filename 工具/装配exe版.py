# -*- coding: utf-8 -*-
r"""装配并打包「免安装 exe 版」：材料 + 可运行软件，一个压缩包搞定。

布局：
    历史遗留废弃矿山自然恢复适宜性评价系统V1.0_免安装exe版_日期\
    ├── 交付说明.md
    ├── 01_提交材料\        源程序提交版 60 页、说明书 31 页、登记信息表底稿
    ├── 02_备查材料\        源程序全文 279 页、说明书 Word 版
    ├── 03_运行版\          双击其中的 exe 即可用系统（内嵌 Python，免安装）
    │   ├── 历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe
    │   ├── 使用说明.txt
    │   ├── portable_runtime\  app\  run.py  seed_demo.py  ...
    │   └── 启动（免安装）.bat     （exe 被安全策略拦下时的备用入口）
    └── 04_项目文档\        开发日志、功能计划、演示脚本、分工、形式要求核实报告
"""
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"D:\自然恢复软著")
DIST_EXE = ROOT / "构建缓存" / "dist" / "历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe"
RUNTIME = ROOT / "portable_runtime"
BASE = "历史遗留废弃矿山自然恢复适宜性评价系统V1.0_免安装exe版_20261008"
OUT_DIR = ROOT / "交付包" / "exe版"
STAGE = OUT_DIR / BASE
ZIP = OUT_DIR / (BASE + ".zip")
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}

SUBMIT = [
    "软著材料/源程序_提交版（前30页+后30页）_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf",
    "软著材料/说明书_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf",
    "软著材料/登记信息表底稿.docx",
]
BACKUP = [
    "软著材料/源程序_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.pdf",
    "软著材料/说明书_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.docx",
]
DOCS = [
    "文档/开发日志.docx", "文档/软著功能计划.docx", "文档/演示脚本.docx",
    "文档/制作步骤与分工.docx", "文档/软著登记申请材料形式要求_联网核实报告.docx",
]
SOURCE = ["run.py", "seed_demo.py", "requirements.txt", "README.md", "启动（免安装）.bat"]

USAGE = """历史遗留废弃矿山自然恢复适宜性评价系统 V1.0 —— 免安装版
==============================================================

怎么用（三步）
--------------
1. 把整个压缩包解压到磁盘上（不要只从压缩包窗口里双击运行）；
2. 进 03_运行版\\，双击「历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe」；
3. 弹出的小窗口里等十几秒 → 浏览器自动打开系统 → 用 admin / admin123 登录。

窗口上两个按钮：
  「打开系统」   —— 手动再打开一次浏览器
  「停止并退出」 —— 结束系统（直接关窗口也一样，不会留后台进程）

不用装 Python，不用联网，不用管理员权限，不用装数据库。
系统数据存在 03_运行版\\app\\app.db（本机文件）；想清空重来，删掉它再启动即可。

出问题怎么办
------------
- 窗口里会显示运行信息，同时写入同目录的「启动日志.txt」。
- 想先自己体检：在这个目录打开命令行，执行
      "历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe" --check
  它会依次检查运行环境、依赖、演示数据、服务与登录页，并打印结果。
  把「启动日志.txt」发给我们即可定位问题。
- 双击 exe 没反应 / 被拦下：
    * Windows 提示「已保护你的电脑」→ 点「更多信息 → 仍要运行」（exe 未签名，属常见提示）；
    * 杀毒软件报警 → 同样是未签名 exe 的误报，可加白名单；
    * 实在不行，改双击「启动（免安装）.bat」，效果完全一样。
- 提示端口 5000 被占用：窗口会告诉你是哪个进程占用并询问是否结束它；
  如果占用的是本系统（上次没退干净），直接确认即可。

随包材料
--------
软著登记材料在上一层的 01_提交材料\\（要提交的就是那两份 PDF）、
02_备查材料\\、04_项目文档\\。本文件夹只放可运行的系统本身。
"""

README = """# 免安装 exe 版 · 历史遗留废弃矿山自然恢复适宜性评价系统 V1.0

| 目录 | 内容 |
|---|---|
| `01_提交材料/` | **要提交给版权中心的只有这里的两份 PDF**：源程序提交版（60 页）、说明书（31 页）；另附登记信息表底稿 |
| `02_备查材料/` | 源程序全文 279 页、说明书 Word 版（供核对与批注） |
| `03_运行版/` | 可运行的系统：双击其中的 exe 即可，**不需要装 Python、不需要联网** |
| `04_项目文档/` | 开发日志、软著功能计划、演示脚本、制作步骤与分工、形式要求核实报告（均为 Word） |

## 打开系统
进 `03_运行版/`，双击「历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe」，
等窗口提示「系统已启动」，浏览器会自动打开 http://127.0.0.1:5000 ，
演示账号 **admin / admin123**。关掉那个小窗口即停止系统。

详见 `03_运行版/使用说明.txt`；运行信息会写进同目录的 `启动日志.txt`。

## 还没有确定的四项（需要人工填）
1. 著作权人（个人姓名或单位工商登记全称）
2. 开发完成日期（须早于或等于首次发表日期）
3. 首次发表日期（未发表可勾选「未发表」）
4. 经办人信息与诚信声明（现行申请表要求亲笔手抄、签名、填身份证号）

填在 `01_提交材料/登记信息表底稿.docx` 里，再照它填官方申请表。

## 口径说明
- 限制性指标四项：政策约束、区位约束、土壤污染、地质灾害。
- 坡度以 25° 为分界，超过后按 (90−坡度)/(90−25) 线性折减（方法未给区间外折算方式时的工程补充，说明书 4.1 已写明）。
- 权重、标准化取值、等级阈值、指标结构与评价流程均与现行方法逐项核对一致；内置标准库 12 项。
- 材料形式自检 22 项全部符合；19 套自检全部通过。
"""


def copy_tree(src, dst, skip_data=True):
    for f in sorted(Path(src).rglob("*")):
        if not f.is_file() or any(p in EXCLUDE_DIRS for p in f.parts):
            continue
        if skip_data and (f.name in ("app.db", ".secret_key", "启动日志.txt")
                          or f.suffix == ".pyc"):
            continue
        target = Path(dst) / f.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)


def build_stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    (STAGE / "交付说明.md").write_text(README, encoding="utf-8", newline="\n")

    for rel in SUBMIT:
        dst = STAGE / "01_提交材料" / Path(rel).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    for rel in BACKUP:
        dst = STAGE / "02_备查材料" / Path(rel).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    for rel in DOCS:
        src = ROOT / rel
        if src.exists():
            dst = STAGE / "04_项目文档" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    run = STAGE / "03_运行版"
    run.mkdir(parents=True)
    shutil.copy2(DIST_EXE, run / DIST_EXE.name)
    (run / "使用说明.txt").write_text(USAGE, encoding="utf-8", newline="\r\n")
    for rel in SOURCE:
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, run / src.name)
    copy_tree(ROOT / "app", run / "app")
    copy_tree(RUNTIME, run / "portable_runtime")

    files = [f for f in STAGE.rglob("*") if f.is_file()]
    print("装配完成：%d 个文件，%.1f MB"
          % (len(files), sum(f.stat().st_size for f in files) / 1048576))
    for sub in ("01_提交材料", "02_备查材料", "03_运行版", "04_项目文档"):
        n = len([f for f in (STAGE / sub).rglob("*") if f.is_file()])
        print("   %-12s %d 个文件" % (sub, n))


def do_zip():
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(STAGE.rglob("*")):
            if f.is_file():
                z.write(f, "%s/%s" % (BASE, f.relative_to(STAGE).as_posix()))
    print("压缩包：%s（%.1f MB）" % (ZIP, ZIP.stat().st_size / 1048576))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_stage()
    do_zip()
    # 免安装 bat 版被 exe 版取代（内容重复），删掉以免混淆
    for old in OUT_DIR.glob("*_免安装版_20261008*"):
        if old.is_dir():
            shutil.rmtree(old)
        else:
            old.unlink()
        print("已删除被取代的旧包：", old.name)
    print()
    print("交付包/ 现有：")
    for p in sorted((ROOT / "交付包").iterdir()):
        if p.name.startswith("_"):
            continue
        print("   %-74s %s" % (p.name[:74], "文件夹" if p.is_dir()
                              else "%.1f MB" % (p.stat().st_size / 1048576)))


if __name__ == "__main__":
    main()
