# -*- coding: utf-8 -*-
"""把 文档/ 与 软著材料/ 下的 Markdown 转成带中文模板的 Word。

用法：python 工具/生成文档Word.py
前置：D:\\Pandoc\\pandoc.exe；中文模板由 工具/生成Word中文模板.py 产出。
说明：说明书另有专门的 Word 版，由 工具/make_manual_docx.py 生成（与 PDF 版同源）。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANDOC = r"D:\Pandoc\pandoc.exe"

# 需要出 Word 的文稿（送审包只带 docx；md 作为源文件留在仓库里）
SOURCES = [
    os.path.join("文档", "软著功能计划.md"),
    os.path.join("文档", "制作步骤与分工.md"),
    os.path.join("文档", "演示脚本.md"),
    os.path.join("文档", "开发日志.md"),
    os.path.join("文档", "软著登记申请材料形式要求_联网核实报告.md"),
    os.path.join("软著材料", "登记信息表底稿.md"),
]


def build_reference():
    """生成（或复用）中文 reference.docx。"""
    ref = os.path.join(os.environ["TEMP"], "dsh_ref_cn.docx")
    script = os.path.join(ROOT, "工具", "生成Word中文模板.py")
    r = subprocess.run([sys.executable, script], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(ref):
        print(r.stdout)
        print(r.stderr)
        raise SystemExit("中文模板生成失败")
    return ref


def main():
    if not os.path.exists(PANDOC):
        raise SystemExit("未找到 pandoc：%s" % PANDOC)
    ref = build_reference()
    print("中文模板：%s" % ref)

    for name in SOURCES:
        src = os.path.join(ROOT, name)
        if not os.path.exists(src):
            print("  [跳过] %s（不存在）" % name)
            continue
        out = os.path.splitext(src)[0] + ".docx"
        r = subprocess.run(
            [PANDOC, src, "-o", out, "--reference-doc", ref,
             "--from", "gfm+tex_math_dollars", "--toc", "--toc-depth=2"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print("  [失败] %s\n%s" % (name, r.stderr))
            continue
        print("  [完成] %-24s %8.1f KB -> %s"
              % (name, os.path.getsize(out) / 1024, os.path.basename(out)))


if __name__ == "__main__":
    main()
