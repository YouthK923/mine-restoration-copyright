# -*- coding: utf-8 -*-
import os, sys, re
sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.abspath(__file__))
FN = '20261095_审改稿.docx（8.10）.docx'
import zipfile
xml = zipfile.ZipFile(os.path.join(BASE, FN)).read('word/document.xml').decode('utf-8')

# Split into paragraphs, drop table content, print full text of every paragraph
paras = re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
print('paragraphs:', len(paras))
KEY = ['坡向', '阳坡', '阴坡', '标准化', '极值', '理想', '权重', '岩质边', '碎石', '半阳', '半阴', '朝向']
print('\n--- paragraphs containing key terms ---')
for i, p in enumerate(paras):
    ts = re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', p, re.S)
    txt = ''.join(ts).replace('&amp;','&')
    if any(k in txt for k in KEY):
        print(f'[p{i}] {txt}')
