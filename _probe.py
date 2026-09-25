# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
import fitz

BASE = os.path.dirname(os.path.abspath(__file__))
files = {
 'biansu_manual': '变压器抗短路能力评估系统V1.0-说明书(1).pdf',
 'biansu_code': '变压器抗短路能力评估系统V1.0-代码(1).pdf',
 'dianwang_manual': '电网安全风险数据分析系统-用户手册.pdf',
 'dianwang_code': '电网安全风险数据分析系统-源代码.pdf',
}
KEYS = ['软件', '著作权', '登记', '申请', '源程序', '说明书', '用户手册', '开发完成', '首次发表', '版本号', '页', '签字', '盖章', '单位', '名称']

for k, f in files.items():
    doc = fitz.open(os.path.join(BASE, f))
    p0 = doc[0]
    print('='*70)
    print(k, f, 'pages=', doc.page_count, 'size=', [round(x,1) for x in (p0.rect.width, p0.rect.height)])
    # fonts used
    fonts = set()
    for pg in doc:
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    fonts.add((s['font'], round(s['size'],1)))
    print(' fonts:', sorted(fonts)[:12])
    # header/footer: top and bottom bands text
    for idx in [0, 1, min(3, doc.page_count-1)]:
        pg = doc[idx]
        h = pg.rect.height
        top = pg.get_text('text', clip=fitz.Rect(0, 0, pg.rect.width, h*0.12)).strip().replace('\n',' / ')
        bot = pg.get_text('text', clip=fitz.Rect(0, h*0.88, pg.rect.width, h)).strip().replace('\n',' / ')
        print(f'  p{idx+1} TOP: {top!r}')
        print(f'  p{idx+1} BOT: {bot!r}')

# code line density of dianwang_code full text
doc = fitz.open(os.path.join(BASE, files['dianwang_code']))
tot = 0
for pg in doc:
    t = pg.get_text('text')
    tot += len(t.splitlines())
print('='*70)
print('dianwang_code total text lines (incl header/lineno):', tot)
