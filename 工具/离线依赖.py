# -*- coding: utf-8 -*-
"""把依赖做成离线 wheel，随源码一起拷给别人（对方没有网络也能装）。

用途：把系统源码发给师兄/评审人时，附上 `offline_wheels/`，
对方在源码目录里执行

    pip install --no-index --find-links offline_wheels -r requirements.txt

即可离线装好依赖；`启动.bat` 也会优先用这份离线依赖。

用法：
    python 工具/离线依赖.py            # 下载到 offline_wheels/
    python 工具/离线依赖.py --check    # 只看看现在有没有、有多少

说明：wheel 是二进制包，体积约 20 MB，已加入 .gitignore，不进版本控制。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "offline_wheels")
REQ = os.path.join(ROOT, "requirements.txt")


def main():
    if "--check" in sys.argv:
        if not os.path.isdir(OUT):
            print("还没有 offline_wheels/，需要时运行：python 工具/离线依赖.py")
            return
        files = [f for f in os.listdir(OUT) if f.endswith(".whl")]
        total = sum(os.path.getsize(os.path.join(OUT, f)) for f in files)
        print("offline_wheels/ 里有 %d 个 wheel，合计 %.1f MB"
              % (len(files), total / 1048576))
        return

    os.makedirs(OUT, exist_ok=True)
    print("正在下载依赖到 %s …" % os.path.relpath(OUT, ROOT))
    r = subprocess.run([sys.executable, "-m", "pip", "download", "-r", REQ,
                        "-d", OUT, "--only-binary", ":all:"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("下载失败：请检查网络，或先 pip install 好依赖再试")
    files = sorted(f for f in os.listdir(OUT) if f.endswith(".whl"))
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in files)
    print("完成：%d 个 wheel，合计 %.1f MB" % (len(files), total / 1048576))
    for f in files:
        print("   ", f)
    print()
    print("把这些文件随源码一起拷给别人，对方执行：")
    print("    pip install --no-index --find-links offline_wheels -r requirements.txt")


if __name__ == "__main__":
    main()
