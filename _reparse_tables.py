# -*- coding: utf-8 -*-
import os, sys, zipfile, re
sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.abspath(__file__))
FN = '20261095_审改稿.docx（8.10）.docx'
z = zipfile.ZipFile(os.path.join(BASE, FN))
print('--- parts ---')
for n in z.namelist():
    print(' ', n, z.getinfo(n).file_size)

xml = z.read('word/document.xml').decode('utf-8')
print('\n--- document.xml length:', len(xml))

# find all tables: split on <w:tbl> ... </w:tbl>
tbls = re.findall(r'<w:tbl[ >].*?</w:tbl>', xml, re.S)
print('tables found:', len(tbls))

def cell_text(tc):
    # all w:t inside
    ts = re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', tc, re.S)
    txt = ''.join(ts)
    txt = txt.replace('&amp;','&').replace('&lt;','<').replace('&gt;','>').replace('&quot;','"').replace('&apos;',"'")
    tags = set(re.findall(r'<w:([A-Za-z]+)[ />]', tc))
    extra = []
    for k in ('drawing','object','pict','oMath','oMathPara','txbxContent','sym'):
        if k in tags: extra.append(k)
    return txt, extra

for i, tbl in enumerate(tbls, 1):
    rows = re.findall(r'<w:tr[ >].*?</w:tr>', tbl, re.S)
    print(f'\n================ TABLE {i}  rows={len(rows)} ================')
    for ri, row in enumerate(rows, 1):
        cells = re.findall(r'<w:tc>.*?</w:tc>', row, re.S)
        out = []
        for c in cells:
            t, extra = cell_text(c)
            out.append(t + (('<' + ','.join(extra) + '>') if extra else ''))
        print(f'  r{ri}: ' + ' | '.join(repr(x) for x in out))
