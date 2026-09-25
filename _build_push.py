# -*- coding: utf-8 -*-
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')


def run(args, timeout=300):
    p = subprocess.run(args, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
    return (p.stdout or p.stderr).strip(), p.returncode


def g(*a):
    return run(['git', '-c', 'core.quotepath=false'] + list(a))


MD = '软著功能计划.md'
DOCX = '软著功能计划.docx'

# 1) 重新生成中文排版模板
out, rc = run(['python', '_mkref.py'])
print('生成模板 exit=%d' % rc)

# 2) Markdown -> Word
out, rc = run(['pandoc', MD, '-o', DOCX,
               '--reference-doc', r'C:\Users\29918\AppData\Local\Temp\dsh_ref_cn.docx',
               '-f', 'markdown+pipe_tables'])
print('pandoc exit=%d  %s' % (rc, out[:200]))

# 3) 提交并推送
g('add', '-A')
msg = '''精简计划书为功能计划，删除原计划书

- 删除原《软件著作权登记项目计划书》的 md 与两个 docx
- 新增《软著功能计划》：面向非技术读者，9 个功能模块每个仅说明
  功能内容与论文依据，篇幅精简
- 保留系统流程、软著材料要求、实施步骤与预期成果

另：删除误提交的 _push_plan.py'''
out, rc = run(['git', 'commit', '-m', msg])
print(out[:700])
print()

out, rc = g('push')
print('push exit=%d' % rc)
print(out[:300])
print()
print('本地/远程差异:', g('rev-list', '--left-right', '--count', 'main...origin/main')[0])
print('HEAD:', g('log', '-1', '--oneline', '--decorate')[0])
