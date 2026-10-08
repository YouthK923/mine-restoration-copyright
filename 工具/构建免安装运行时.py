# -*- coding: utf-8 -*-
"""构建免安装运行时：内嵌 Python + 依赖，产出 portable_runtime/。

给「电脑上没有 Python、也不想装」的人用：把 `portable_runtime/` 与源码放在一起，
双击 `启动（免安装）.bat` 就能跑，不需要安装任何东西、不需要管理员权限、不需要联网。

它会做四件事：
  1. 下载官方 embeddable Python（python-3.12.7-embed-amd64.zip，约 10 MB）到构建目录；
  2. 解到 `portable_runtime/`；
  3. 用仓库里 `offline_wheels/` 的离线轮子把依赖装进 `Lib/site-packages`；
  4. 写一个引导脚本 `portable_runtime/_start.py`。

为什么要引导脚本：embeddable 包里的 `python312._pth` 会**接管 sys.path**，
不会像正常 Python 那样把「脚本所在目录」加进去，于是 `import app` 会失败。
引导脚本负责把源码目录（运行时的上一级）插进 sys.path 再执行目标脚本。

用法：
    python 工具/离线依赖.py            # 先把依赖下到 offline_wheels/
    python 工具/构建免安装运行时.py      # 产出 portable_runtime/
"""
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "portable_runtime"
WHEELS = ROOT / "offline_wheels"
BUILD = ROOT / "构建缓存"
EMBED_URL = ("https://www.python.org/ftp/python/3.12.7/"
             "python-3.12.7-embed-amd64.zip")
PROXY = os.environ.get("DSH_BUILD_PROXY", "http://127.0.0.1:7897")

BOOTSTRAP = '''# -*- coding: utf-8 -*-
"""免安装运行时的引导脚本：把源码目录加进 sys.path，再执行目标脚本。

为什么需要它：embeddable Python 的 `python312._pth` 接管了 sys.path，
不会自动包含「脚本所在目录」，直接 `python run.py` 会报 `No module named 'app'`。
"""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

target = sys.argv[1] if len(sys.argv) > 1 else "run.py"
sys.argv = sys.argv[1:] or ["run.py"]
runpy.run_path(os.path.join(ROOT, target), run_name="__main__")
'''


def download(url, dest):
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print("   已有缓存：%s" % dest.name)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("   下载 %s …" % url)
    handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    opener = urllib.request.build_opener(handler)
    try:
        with opener.open(url, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as e:
        print("   走代理失败（%s），改直连再试一次" % e)
        urllib.request.urlretrieve(url, dest)
    print("   完成：%.1f MB" % (dest.stat().st_size / 1048576))


def main():
    if not WHEELS.is_dir() or not list(WHEELS.glob("*.whl")):
        raise SystemExit("没找到 offline_wheels/，请先运行：python 工具/离线依赖.py")

    embed = BUILD / "python-embed-amd64.zip"
    print("1) 准备官方 embeddable Python")
    download(EMBED_URL, embed)

    print("2) 解到 %s" % RUNTIME.name)
    if RUNTIME.exists():
        import shutil
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True)
    with zipfile.ZipFile(embed) as z:
        z.extractall(RUNTIME)

    print("3) 打开搜索路径（Lib\\site-packages）")
    pth = next(RUNTIME.glob("python*._pth"))
    lines = []
    for ln in pth.read_text(encoding="utf-8").splitlines():
        lines.append("import site" if ln.strip() == "#import site" else ln)
    if "Lib\\site-packages" not in lines:
        lines.append("Lib\\site-packages")
    if "." not in lines:
        lines.append(".")
    pth.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("4) 用离线轮子安装依赖")
    site = RUNTIME / "Lib" / "site-packages"
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index",
                        "--find-links", str(WHEELS), "-r",
                        str(ROOT / "requirements.txt"), "--target", str(site)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        raise SystemExit("依赖安装失败")

    print("5) 写引导脚本 _start.py")
    (RUNTIME / "_start.py").write_text(BOOTSTRAP, encoding="utf-8", newline="\n")

    print("6) 自检：用内嵌 Python 导入依赖并试跑")
    py = RUNTIME / "python.exe"
    r = subprocess.run([str(py), str(RUNTIME / "_start.py"), "-c_check"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    r = subprocess.run([str(py), "-c",
                        "import flask, flask_login, flask_wtf, flask_sqlalchemy,"
                        " numpy, openpyxl, docx; print('依赖 OK', flask.__version__)"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print("   ", (r.stdout or r.stderr).strip()[:120])

    files = [f for f in RUNTIME.rglob("*") if f.is_file()]
    print("7) 运行时完成：%d 个文件，%.1f MB"
          % (len(files), sum(f.stat().st_size for f in files) / 1048576))
    print()
    print("打包时把 portable_runtime/ 与 启动（免安装）.bat 一起放进源码目录即可。")


if __name__ == "__main__":
    main()
