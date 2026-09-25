# -*- coding: utf-8 -*-
import sys, re, zipfile, os
sys.stdout.reconfigure(encoding='utf-8')
z = zipfile.ZipFile(os.path.join(os.environ['TEMP'], 'dsh_ref_cn.docx'))
s = z.read('word/styles.xml').decode('utf-8')
print('=== 含 4F81BD / 345A8A 的样式 ===')
for m in re.finditer(r'<w:style\b(.*?)</w:style>', s, re.S):
    blk = m.group(0)
    if '4F81BD' in blk or '345A8A' in blk:
        sid = re.search(r'w:styleId="([^"]*)"', blk)
        nm = re.search(r'<w:name w:val="([^"]*)"', blk)
        print('  styleId=%-16r  name=%-16r' % (sid.group(1) if sid else None,
                                               nm.group(1) if nm else None))
print()
print('=== 全部 styleId 一览 ===')
ids = re.findall(r'w:styleId="([^"]*)"', s)
print(' ', ids)
