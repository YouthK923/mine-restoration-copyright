# -*- coding: utf-8 -*-
import os, sys, datetime
sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.abspath(__file__))
rows = []
for n in sorted(os.listdir(BASE)):
    p = os.path.join(BASE, n)
    st = os.stat(p)
    if os.path.isdir(p):
        # size of dir contents
        tot = sum(os.path.getsize(os.path.join(dp, f))
                  for dp, dn, fn in os.walk(p) for f in fn)
        rows.append(('DIR', n, tot, st.st_mtime))
    else:
        rows.append(('FILE', n, st.st_size, st.st_mtime))
for t, n, s, m in sorted(rows, key=lambda r: r[3]):
    print('%-5s %10s  %s  %s' % (t, ('%.1fKB' % (s/1024)) if s else '-',
                                 datetime.datetime.fromtimestamp(m).strftime('%m-%d %H:%M:%S'), n))
print()
print('总计 %d 项' % len(rows))
