# -*- coding: utf-8 -*-
"""把桌面启动器打包成 exe（做法②：单文件夹 + exe 启动器）。

产物：
    构建缓存/dist/历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe
发布前由 工具/打包exe.py --install 复制到 交付包/exe版/ 的对应位置，
与 portable_runtime/、app/、源码放在同一个文件夹里。

为什么启动器要单独打包：
    exe 只是「入口」——找内嵌运行时、起服务、开浏览器；
    真正的系统代码仍是 folder 里的 app/（源码可见、可核对、可修）。

用法：
    python 工具/打包exe.py            # 只打包
    python 工具/打包exe.py --install   # 打包并拷进交付包目录
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "构建缓存"
VENV_PY = BUILD / "build_venv" / "Scripts" / "python.exe"
ENTRY = ROOT / "工具" / "exe启动器.py"
ICON = ROOT / "app" / "static" / "favicon.ico"
NAME = "历史遗留废弃矿山自然恢复适宜性评价系统V1.0"
DIST = BUILD / "dist"
INSTALL_DIR = ROOT / "交付包" / "exe版" / "历史遗留废弃矿山自然恢复适宜性评价系统V1.0"

VERSION_FILE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0), prodvers=(1, 0, 0, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('080404B0', [
        StringStruct('CompanyName', '历史遗留废弃矿山自然恢复适宜性评价系统项目组'),
        StringStruct('FileDescription', '历史遗留废弃矿山自然恢复适宜性评价系统 V1.0'),
        StringStruct('FileVersion', '1.0.0.0'),
        StringStruct('InternalName', 'MineRestorationSuitability'),
        StringStruct('OriginalFilename', '历史遗留废弃矿山自然恢复适宜性评价系统V1.0.exe'),
        StringStruct('ProductName', '历史遗留废弃矿山自然恢复适宜性评价系统'),
        StringStruct('ProductVersion', 'V1.0'),
        StringStruct('LegalCopyright', '历史遗留废弃矿山自然恢复适宜性评价系统 V1.0')
    ])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""


def main():
    if not VENV_PY.exists():
        raise SystemExit("没找到构建环境，请先执行：\n"
                         "  python -m venv 构建缓存/build_venv\n"
                         "  构建缓存/build_venv/Scripts/python -m pip install pyinstaller")
    if not ICON.exists():
        print("[提示] 没找到图标 %s，将不带图标打包" % ICON)

    vf = BUILD / "version_info.txt"
    vf.write_text(VERSION_FILE, encoding="utf-8")

    cmd = [str(VENV_PY), "-m", "PyInstaller", "--noconfirm", "--clean",
           "--onefile", "--noconsole",
           "--name", NAME,
           "--distpath", str(DIST),
           "--workpath", str(BUILD / "pyi_work"),
           "--specpath", str(BUILD),
           "--version-file", str(vf)]
    if ICON.exists():
        cmd += ["--icon", str(ICON)]
    cmd.append(str(ENTRY))

    print("开始打包启动器（首次约 1 分钟）……")
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    exe = DIST / (NAME + ".exe")
    if r.returncode != 0 or not exe.exists():
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise SystemExit("打包失败")
    print("打包完成：%s（%.1f MB）" % (exe, exe.stat().st_size / 1048576))

    if "--install" in sys.argv:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exe, INSTALL_DIR / exe.name)
        print("已复制到：%s" % (INSTALL_DIR / exe.name))


if __name__ == "__main__":
    main()
