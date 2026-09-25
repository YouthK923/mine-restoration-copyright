# -*- coding: utf-8 -*-
"""在桌面（以及开始菜单）创建系统快捷方式，双击即可启动。

用法：
    python 工具/创建桌面快捷方式.py            创建（桌面 + 开始菜单）
    python 工具/创建桌面快捷方式.py --remove   删除已创建的快捷方式

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
NAME = "自然恢复适宜性评价系统"
DESC = "历史遗留废弃矿山自然恢复适宜性评价系统 V1.0"


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
$targets = @()
$desktop = [Environment]::GetFolderPath('Desktop')
$targets += (Join-Path $desktop {name})
$targets += (Join-Path ([Environment]::GetFolderPath('Programs')) {name})
foreach ($path in $targets) {{
  $lnk = $shell.CreateShortcut($path + '.lnk')
  $lnk.TargetPath = {bat}
  $lnk.WorkingDirectory = {base}
  $lnk.Description = {desc}
  if (Test-Path {ico}) {{ $lnk.IconLocation = {ico} }}
  $lnk.WindowStyle = 1
  $lnk.Save()
  Write-Output $lnk.FullName
}}
""".format(name=ps_quote(NAME), bat=ps_quote(BAT), base=ps_quote(BASE),
           desc=ps_quote(DESC), ico=ps_quote(ICO))

    out, err, code = run_ps(body)
    if code != 0:
        print("[错误] 创建快捷方式失败")
        if err:
            print(err[:500])
        return 1

    print("已在以下位置创建快捷方式：")
    for line in out.splitlines():
        line = line.strip()
        if line:
            print("  " + line)
    print()
    print("以后双击桌面上的「%s」即可启动系统，" % NAME)
    print("服务就绪后会自动打开浏览器（http://127.0.0.1:5000）。")
    print()
    print("提示：快捷方式里记录的是当前项目路径，")
    print("      如果移动或重命名了项目文件夹，请重新运行本脚本。")
    return 0


def remove():
    body = """
$ErrorActionPreference = 'SilentlyContinue'
$paths = @()
$paths += (Join-Path ([Environment]::GetFolderPath('Desktop')) {name})
$paths += (Join-Path ([Environment]::GetFolderPath('Programs')) {name})
foreach ($p in $paths) {{
  if (Test-Path ($p + '.lnk')) {{
    Remove-Item ($p + '.lnk') -Force
    Write-Output ('removed: ' + $p + '.lnk')
  }}
}}
""".format(name=ps_quote(NAME))
    out, err, code = run_ps(body)
    print(out or "没有找到已创建的快捷方式")
    return 0


if __name__ == "__main__":
    if "--remove" in sys.argv:
        sys.exit(remove())
    sys.exit(create())
