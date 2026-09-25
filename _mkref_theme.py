# -*- coding: utf-8 -*-
"""Patch eastAsia theme fonts in the reference docx so Chinese renders correctly."""
import os, sys, re, zipfile, io, subprocess
sys.stdout.reconfigure(encoding='utf-8')

PANDOC = r'D:\Pandoc\pandoc.exe'
OUT = os.path.join(os.environ['TEMP'], 'dsh_ref_cn.docx')

p = subprocess.run([PANDOC, '--print-default-data-file', 'reference.docx'],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
zin = zipfile.ZipFile(io.BytesIO(p.stdout))
theme = zin.read('word/theme/theme1.xml').decode('utf-8')

print('--- majorFont / minorFont BEFORE ---')
for m in re.finditer(r'<a:(major|minor)Font>.*?<a:latin[^>]*/>', theme, re.S):
    print(m.group(0)[:200])

# set latin + ea for major and minor fonts
def set_font(block_name, latin, ea):
    global theme
    m = re.search(r'<a:%sFont>.*?</a:%sFont>' % (block_name, block_name), theme, re.S)
    if not m:
        print('  block not found:', block_name); return
    blk = m.group(0)
    nb = blk
    # latin typeface
    nb = re.sub(r'(<a:latin typeface=")[^"]*(")', r'\g<1>%s\g<2>' % latin, nb, count=1)
    if '<a:ea ' in nb:
        nb = re.sub(r'(<a:ea typeface=")[^"]*(")', r'\g<1>%s\g<2>' % ea, nb, count=1)
    else:
        nb = nb.replace('<a:cs ', '<a:ea typeface="%s"/><a:cs ' % ea, 1)
        if '<a:ea ' not in nb:
            nb = re.sub(r'(<a:latin typeface="[^"]*"/>)', r'\1<a:ea typeface="%s"/>' % ea, nb, count=1)
    theme = theme.replace(blk, nb)

set_font('major', 'Times New Roman', '黑体')
set_font('minor', 'Times New Roman', '宋体')

print('--- AFTER ---')
for m in re.finditer(r'<a:(major|minor)Font>.*?</a:(major|minor)Font>', theme, re.S):
    blk = m.group(0)
    lat = re.search(r'<a:latin typeface="([^"]*)"', blk)
    ea = re.search(r'<a:ea typeface="([^"]*)"', blk)
    print(m.group(1), '-> latin:', lat.group(1) if lat else None,
          '| ea:', ea.group(1) if ea else None)

zout = zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED)
for n in zin.namelist():
    if n == 'word/theme/theme1.xml':
        zout.writestr(n, theme.encode('utf-8'))
    else:
        zout.writestr(n, zin.read(n))
zout.close(); zin.close()
print('patched reference:', OUT)
