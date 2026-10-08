# -*- coding: utf-8 -*-
"""桌面启动器（被 工具/打包exe.py 打包成 exe）。

它不是系统本身，只是「双击即用」的入口：
  1. 找到同目录下 portable_runtime\\python.exe（内嵌运行时，免安装）
  2. 后台跑 seed_demo.py 写好演示数据
  3. 后台跑 run.py 起服务（--no-browser，浏览器由本窗口开，避免开两个标签）
  4. 轮询端口，就绪后自动打开浏览器
  5. 关窗口或点「停止并退出」→ 结束服务进程，不留后台残留
  6. 全过程写 启动日志.txt（出问题时把这个文件发给开发者即可）

端口被占用时不再盲目跳过：先探测它是不是本系统（能返回登录页就视为已有实例，
直接开浏览器）；如果是别的程序占着，问过用户后再结束它并启动。

用 tkinter 写窗口：标准库，打包进 exe 没问题（内嵌运行时里不装 tkinter，
所以界面代码只放在这个启动器里）。
"""
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import messagebox, scrolledtext

# 打包成 exe 后标准输出可能是 GBK 代码页：打印中文（或含替换字符的文本）会
# 抛 UnicodeEncodeError 直接崩掉。统一改成 UTF-8 并容错。
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 让内嵌运行时也按 UTF-8 输出，日志与窗口里的中文才不会变成乱码
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

NAME = "历史遗留废弃矿山自然恢复适宜性评价系统 V1.0"
PORT = 5000
URL = "http://127.0.0.1:%d" % PORT

HERE = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__))
RUNTIME = os.path.join(HERE, "portable_runtime")
PYTHON = os.path.join(RUNTIME, "python.exe")
BOOT = os.path.join(RUNTIME, "_start.py")
LOG = os.path.join(HERE, "启动日志.txt")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log_line(text):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   text.rstrip()))
    except Exception:
        pass


def port_busy(port=PORT):
    with socket.socket() as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_our_app(timeout=2.0):
    try:
        with urllib.request.urlopen(URL + "/login", timeout=timeout) as r:
            body = r.read(4000).decode("utf-8", "replace")
            return r.status == 200 and "历史遗留废弃矿山" in body
    except Exception:
        return False


def pid_on_port(port=PORT):
    """用 netstat 找出占用端口的进程号。"""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace",
                             creationflags=NO_WINDOW).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper().startswith("TCP") \
                and parts[1].endswith(":%d" % port) and parts[3] == "LISTENING":
            if parts[4].isdigit():
                return int(parts[4])
    return None


class Launcher:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.server_ready = False
        root.title(NAME)
        root.geometry("640x380")
        root.minsize(540, 320)

        tk.Label(root, text=NAME, font=("Microsoft YaHei", 13, "bold")).pack(pady=(14, 2))
        self.status = tk.Label(root, text="正在启动，请稍候……",
                               font=("Microsoft YaHei", 10), fg="#1f4e5f")
        self.status.pack(pady=(0, 8))

        self.log = scrolledtext.ScrolledText(root, height=10, font=("Consolas", 9),
                                             state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=14)

        bar = tk.Frame(root)
        bar.pack(pady=10)
        self.open_btn = tk.Button(bar, text="打开系统", width=14, state="disabled",
                                  command=self.open_browser, font=("Microsoft YaHei", 10))
        self.open_btn.pack(side="left", padx=6)
        tk.Button(bar, text="停止并退出", width=14, command=self.quit,
                  font=("Microsoft YaHei", 10)).pack(side="left", padx=6)

        root.protocol("WM_DELETE_WINDOW", self.quit)
        log_line("启动器开始运行，目录：%s" % HERE)
        threading.Thread(target=self.start, daemon=True).start()

    # ---- 界面 ----
    def write(self, text):
        log_line(text)
        def do():
            self.log.configure(state="normal")
            self.log.insert("end", text if text.endswith("\n") else text + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(0, do)

    def set_status(self, text, color="#1f4e5f"):
        self.root.after(0, lambda: self.status.configure(text=text, fg=color))

    # ---- 启动 ----
    def start(self):
        if not os.path.exists(PYTHON) or not os.path.exists(BOOT):
            self.write("[错误] 找不到内嵌运行环境：%s" % RUNTIME)
            self.root.after(0, lambda: messagebox.showerror(
                "缺少运行环境",
                "找不到内嵌运行环境：\n%s\n\n请确认解压时保持了文件夹结构，"
                "不要把 exe 单独拷出来。" % RUNTIME))
            return

        if port_busy():
            if is_our_app():
                self.write("[提示] 检测到本系统已在运行，直接打开浏览器。")
                self.ready(already=True)
                return
            pid = pid_on_port()
            if pid:
                self.write("[注意] 端口 %d 被其它程序占用（PID %s）。" % (PORT, pid))
                answer = {"v": False}
                done = threading.Event()

                def ask():
                    answer["v"] = messagebox.askyesno(
                        "端口被占用",
                        "端口 %d 被另一个程序占用（进程号 %s）。\n\n"
                        "是否结束它并启动本系统？\n"
                        "（如果不确定，选「否」，然后手动关闭那个程序再重试）" % (PORT, pid))
                    done.set()
                self.root.after(0, ask)
                done.wait()
                if not answer["v"]:
                    self.set_status("端口被占用，已取消启动", "#a33")
                    self.write("[已取消] 用户选择不结束占用端口的进程。")
                    return
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, creationflags=NO_WINDOW)
                self.write("[已处理] 已结束 PID %s。" % pid)
                time.sleep(1)

        self.write("运行环境：%s" % RUNTIME)
        self.write("准备演示数据……")
        rc = self.run_sync([PYTHON, BOOT, "seed_demo.py"])
        if rc != 0:
            self.write("[错误] 演示数据准备失败（返回码 %d），下面的信息可用于排查。" % rc)

        self.write("启动服务……")
        self.proc = subprocess.Popen(
            [PYTHON, BOOT, "run.py", "--port", str(PORT), "--no-browser"],
            cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=NO_WINDOW)
        log_line("服务进程已启动，PID=%s" % self.proc.pid)
        threading.Thread(target=self.pump, args=(self.proc,), daemon=True).start()

        for _ in range(120):
            if port_busy():
                self.ready()
                return
            if self.proc.poll() is not None:
                self.write("[错误] 服务进程提前退出（返回码 %s）。" % self.proc.returncode)
                self.set_status("启动失败，请把 启动日志.txt 发给开发者", "#a33")
                return
            time.sleep(0.5)
        self.set_status("启动超时，请把 启动日志.txt 发给开发者", "#a33")

    def run_sync(self, args):
        try:
            p = subprocess.run(args, cwd=HERE, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               creationflags=NO_WINDOW)
            if p.stdout:
                self.write(p.stdout)
            if p.stderr:
                self.write(p.stderr)
            return p.returncode
        except Exception as e:
            self.write("[错误] %s" % e)
            return 1

    def pump(self, proc):
        try:
            for line in proc.stdout:
                self.write(line.rstrip())
        except Exception:
            pass

    def ready(self, already=False):
        self.server_ready = True
        self.set_status("系统已启动（演示账号 admin / admin123）" if not already
                        else "系统已在运行", "#1b7f4b")
        self.root.after(0, lambda: self.open_btn.configure(state="normal"))
        self.write("服务已就绪：%s" % URL)
        if not already:
            threading.Thread(target=self.open_browser, daemon=True).start()
        else:
            self.open_browser()

    def open_browser(self):
        try:
            webbrowser.open(URL)
            log_line("已请求打开浏览器：%s" % URL)
        except Exception as e:
            log_line("打开浏览器失败：%s" % e)

    def quit(self):
        if self.proc and self.proc.poll() is None:
            self.write("正在停止服务……")
            try:
                self.proc.terminate()
                self.proc.wait(timeout=8)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        log_line("启动器退出")
        self.root.destroy()


def main():
    if "--check" in sys.argv:
        # 无界面自检：不弹窗口，跑一遍「查运行时 → 写演示数据 → 起服务 → 探端口」，
        # 结果打到控制台与 启动日志.txt，用于排错（发布前我也用它做验证）。
        sys.exit(check_mode())
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    Launcher(root)
    root.mainloop()


def check_mode():
    """返回 0 表示一切正常。"""
    print("启动器自检：")
    print("  目录      : %s" % HERE)
    log_line("== 自检模式 ==")
    if not (os.path.exists(PYTHON) and os.path.exists(BOOT)):
        print("  [失败] 找不到内嵌运行环境：%s" % RUNTIME)
        return 1
    print("  运行时    : 找到 portable_runtime\\python.exe")
    import shutil as _sh
    if _sh.which("python"):
        print("  [提示] 这台机器本身装了 Python，自检仍用内嵌运行时")
    # 依赖自检
    r = subprocess.run([PYTHON, "-c",
                        "import flask, flask_login, flask_wtf, flask_sqlalchemy,"
                        " numpy, openpyxl, docx; print('依赖 OK', flask.__version__)"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NO_WINDOW)
    print("  依赖      : %s" % (r.stdout or r.stderr).strip()[:60])
    if r.returncode != 0:
        return 1
    if port_busy():
        print("  [失败] 端口 %d 已被占用（可能是上次没退干净）" % PORT)
        return 1
    r = subprocess.run([PYTHON, BOOT, "seed_demo.py"], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       creationflags=NO_WINDOW)
    print("  演示数据  : 返回码 %d" % r.returncode)
    log_line(r.stdout or "")
    if r.returncode != 0:
        print(r.stdout[-500:], r.stderr[-500:])
        return 1
    proc = subprocess.Popen([PYTHON, BOOT, "run.py", "--port", str(PORT),
                             "--no-browser"], cwd=HERE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", creationflags=NO_WINDOW)
    try:
        for _ in range(60):
            if port_busy():
                break
            if proc.poll() is not None:
                print("  [失败] 服务进程提前退出：%s" % proc.returncode)
                return 1
            time.sleep(0.5)
        else:
            print("  [失败] 等待服务就绪超时")
            return 1
        print("  服务      : 已就绪 %s（HTTP 状态见下）" % URL)
        try:
            with urllib.request.urlopen(URL + "/login", timeout=5) as resp:
                body = resp.read(4000).decode("utf-8", "replace")
            ok = resp.status == 200 and "历史遗留废弃矿山" in body
            print("  登录页    : HTTP %d，标题匹配 %s" % (resp.status, ok))
            log_line("自检：登录页 HTTP %d，匹配 %s" % (resp.status, ok))
            return 0 if ok else 1
        except Exception as e:
            print("  [失败] 访问登录页出错：%s" % e)
            return 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
