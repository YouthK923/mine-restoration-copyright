# -*- coding: utf-8 -*-
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')


def run(args, timeout=240):
    p = subprocess.run(args, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
    return (p.stdout or p.stderr).strip(), p.returncode


def g(*a):
    return run(['git', '-c', 'core.quotepath=false'] + list(a))


g('add', '-A')

msg = '''删除误提交的临时脚本

上一步提交时误将 _push_plan.py 一并提交，现移除。'''

out, rc = run(['git', 'commit', '-m', msg])
print(out[:700])
print()

out, rc = g('push')
print('push exit=%d' % rc)
print(out[:300])
print()
print('本地/远程差异:', g('rev-list', '--left-right', '--count', 'main...origin/main')[0])
print('HEAD:', g('log', '-1', '--oneline', '--decorate')[0])
