# -*- coding: utf-8 -*-
"""在桌面（以及开始菜单）创建系统快捷方式，双击即可启动。

用法：
    python 工具/创建桌面快捷方式.py                  创建（桌面叫「启动」）
    python 工具/创建桌面快捷方式.py --name 矿山评价   自定义快捷方式名称
    python 工具/创建桌面快捷方式.py --remove         删除已创建的快捷方式

桌面与开始菜单的命名分开：
    桌面      「启动」—— 双击就用，名字短一点
    开始菜单  软件全称 —— 便于按关键词搜索到

实现说明
--------
快捷方式（.lnk）通过 PowerShell 的 WScript.Shell 创建。为避免中文路径
在命令行传参时被转成乱码，这里把脚本写成 UTF-8 带 BOM 的临时 .ps1 再执行，
而不是用 -Command 拼接字符串。

桌面路径用 [Environment]::GetFolderPath('Desktop') 取得，
可正确处理「桌面被 OneDrive 重定向」的情况。
"""
import os
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(BASE, "启动.bat")
ICO = os.path.join(BASE, "app", "static", "favicon.ico")
DESKTOP_NAME = "启动"                       # 桌面快捷方式名，可用 --name 改
MENU_NAME = "历史遗留废弃矿山自然恢复适宜性评价系统"   # 开始菜单用全称便于搜索
DESC = "历史遗留废弃矿山自然恢复适宜性评价系统 V1.0"
# 早期版本用过的名字，重建时一并清掉，避免桌面上留两个
LEGACY = ("自然恢复适宜性评价系统",)


def ensure_icon():
    """图标缺失时先生成。"""
    if os.path.exists(ICO):
        return True
    gen = os.path.join(BASE, "工具", "生成图标.py")
    if not os.path.exists(gen):
        return False
    subprocess.run([sys.executable, gen], cwd=BASE)
    return os.path.exists(ICO)


def ps_quote(s):
    """PowerShell 单引号字符串转义（单引号内两个单引号表示一个）。"""
    return "'" + s.replace("'", "''") + "'"


def run_ps(body):
    """把 PowerShell 脚本写成 UTF-8 带 BOM 的临时文件再执行。"""
    fd, path = tempfile.mkstemp(suffix=".ps1")
    os.close(fd)
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as fh:
        fh.write(body)
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", path],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        return (p.stdout or "").strip(), (p.stderr or "").strip(), p.returncode
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def create():
    if not os.path.exists(BAT):
        print("[错误] 找不到启动脚本：%s" % BAT)
        return 1
    if not ensure_icon():
        print("[提示] 未能生成图标，快捷方式将使用默认图标")

    body = """
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$programs = [Environment]::GetFolderPath('Programs')

# 先清掉旧名字，避免桌面上/开始菜单里重复出现两个图标
foreach ($dir in @($desktop, $programs)) {{
  foreach ($old in @({legacy})) {{
    $p = Join-Path $dir ($old + '.lnk')
    if (Test-Path $p) {{ Remove-Item $p -Force; Write-Output ('[清理旧图标] ' + $p) }}
  }}
}}

$targets = @(
  @{{ Dir = $desktop;  Name = {dname} }},
  @{{ Dir = $programs; Name = {mname} }}
)
foreach ($t in $targets) {{
  $lnk = $shell.CreateShortcut((Join-Path $t.Dir ($t.Name + '.lnk')))
  $lnk.TargetPath = {bat}
  $lnk.WorkingDirectory = {base}
  $lnk.Description = {desc}
  if (Test-Path {ico}) {{ $lnk.IconLocation = {ico} }}
  $lnk.WindowStyle = 1
  $lnk.Save()
  Write-Output ('[已创建] ' + $lnk.FullName)
}}
""".format(legacy=", ".join(ps_quote(x) for x in LEGACY),
           dname=ps_quote(DESKTOP_NAME), mname=ps_quote(MENU_NAME),
           bat=ps_quote(BAT), base=ps_quote(BASE),
           desc=ps_quote(DESC), ico=ps_quote(ICO))

    out, err, code = run_ps(body)
    if code != 0:
        print("[错误] 创建快捷方式失败")
        if err:
            print(err[:500])
        return 1

    for line in out.splitlines():
        line = line.strip()
        if line:
            print("  " + line)
    print()
    print("以后双击桌面上的「%s」图标即可启动系统，" % DESKTOP_NAME)
    print("服务就绪后会自动打开浏览器（http://127.0.0.1:5000）。")
    print()
    print("不想用「%s」这个名字的话，可以换成别的：" % DESKTOP_NAME)
    print("    python 工具/创建桌面快捷方式.py --name 矿山适宜性评价")
    print("也可以直接在桌面上右键图标 → 重命名。")
    print()
    print("提示：快捷方式里记录的是当前项目路径，")
    print("      如果移动或重命名了项目文件夹，请重新运行本脚本。")
    return 0


def remove():
    names = (DESKTOP_NAME, MENU_NAME) + LEGACY
    body = """
$ErrorActionPreference = 'SilentlyContinue'
$dirs = @([Environment]::GetFolderPath('Desktop'),
          [Environment]::GetFolderPath('Programs'))
foreach ($d in $dirs) {{
  foreach ($n in @({names})) {{
    $p = Join-Path $d ($n + '.lnk')
    if (Test-Path $p) {{ Remove-Item $p -Force; Write-Output ('removed: ' + $p) }}
  }}
}}
""".format(names=", ".join(ps_quote(x) for x in names))
    out, err, code = run_ps(body)
    print(out or "没有找到已创建的快捷方式")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--name" and i + 1 < len(argv):
            DESKTOP_NAME = argv[i + 1]
    if "--remove" in argv:
        sys.exit(remove())
    sys.exit(create())
