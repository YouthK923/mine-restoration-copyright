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

msg = '''重写计划书：以论文为唯一技术依据，突出系统功能与项目流程

- 删除原第五章"需要说明的技术问题"，不再讨论论文数值差异
- 明确以论文方法为唯一技术依据，全部算法严格依据论文实现
- 主体改为系统功能设计（9 个功能模块，逐模块说明功能构成与实现）
- 新增项目流程设计：软件使用流程（12 步业务流）与项目开发流程（6 阶段）
- 补充软著形式要求、源程序规模规划、文档规划、形式合规措施
- 技术依据一章完整复述论文的指标、权重、标准化、合成与判定方法'''

out, rc = run(['git', 'commit', '-m', msg])
print(out[:700])
print()

out, rc = g('push')
print('push exit=%d' % rc)
print(out[:300])
print()
print('本地/远程差异:', g('rev-list', '--left-right', '--count', 'main...origin/main')[0])
print('HEAD:', g('log', '-1', '--oneline', '--decorate')[0])
