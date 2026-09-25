# -*- coding: utf-8 -*-
import zipfile, re, sys
sys.stdout.reconfigure(encoding='utf-8')
FN = '软件著作权登记项目计划书_历史遗留废弃矿山自然恢复适宜性评价系统V1.0.docx'
z = zipfile.ZipFile(FN)
s = z.read('word/styles.xml').decode('utf-8')
print('--- Normal style block ---')
m = re.search(r'<w:style [^>]*w:styleId="Normal".*?</w:style>', s, re.S)
print(m.group(0)[:700] if m else 'NOT FOUND')
print()
print('Heading1 block ---')
m = re.search(r'<w:style [^>]*w:styleId="Heading1".*?</w:style>', s, re.S)
print(m.group(0)[:700] if m else 'NOT FOUND')
print()
print('eastAsia 宋体 count:', s.count('w:eastAsia="宋体"'))
print('eastAsia 黑体 count:', s.count('w:eastAsia="黑体"'))
