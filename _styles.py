# -*- coding: utf-8 -*-
import sys, re, zipfile
sys.stdout.reconfigure(encoding='utf-8')
FN = '软件著作权登记项目计划书_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.docx'
z = zipfile.ZipFile(FN)
s = z.read('word/styles.xml').decode('utf-8')

print('=== 所有 style 的 styleId + 是否有颜色 + 是否基于 ===')
for m in re.finditer(r'<w:style\b[^>]*?w:styleId="([^"]+)"[^>]*?>(.*?)</w:style>', s, re.S):
    sid, blk = m.group(1), m.group(2)
    nm = re.search(r'<w:name w:val="([^"]*)"', blk)
    cols = re.findall(r'<w:color\b[^>]*?w:val="([^"]+)"', blk)
    base = re.search(r'<w:basedOn w:val="([^"]*)"', blk)
    ea = re.findall(r'w:eastAsia="([^"]*)"', blk)
    print('  id=%-16s name=%-14s color=%-9s basedOn=%-10s ea=%s'
          % (sid, nm.group(1) if nm else '?', cols or '-', base.group(1) if base else '-', ea or '-'))
