# -*- coding: utf-8 -*-
"""Build a Chinese-friendly pandoc reference.docx entirely inside Python."""
import os, sys, re, zipfile, io, subprocess
sys.stdout.reconfigure(encoding='utf-8')

PANDOC = r'D:\Pandoc\pandoc.exe'
RAW = os.path.join(os.environ['TEMP'], 'dsh_ref_raw.docx')
OUT = os.path.join(os.environ['TEMP'], 'dsh_ref_cn.docx')

# 1) get pandoc's default reference.docx as BYTES (no PowerShell in the middle)
p = subprocess.run([PANDOC, '--print-default-data-file', 'reference.docx'],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if p.returncode != 0:
    print('pandoc failed:', p.stderr.decode('utf-8', 'replace')); sys.exit(1)
data = p.stdout
print('pandoc reference.docx bytes:', len(data), 'magic:', data[:4])
open(RAW, 'wb').write(data)

zin = zipfile.ZipFile(io.BytesIO(data))
styles = zin.read('word/styles.xml').decode('utf-8')
theme = zin.read('word/theme/theme1.xml').decode('utf-8')

# --- patch theme eastAsia fonts (they OVERRIDE explicit w:rFonts w:eastAsia) ---
def set_theme_font(block_name, latin, ea):
    global theme
    m = re.search(r'<a:%sFont>.*?</a:%sFont>' % (block_name, block_name), theme, re.S)
    if not m:
        print('  theme block not found:', block_name); return
    blk = m.group(0)
    nb = re.sub(r'(<a:latin typeface=")[^"]*(")', r'\g<1>%s\g<2>' % latin, blk, count=1)
    if '<a:ea ' in nb:
        nb = re.sub(r'(<a:ea typeface=")[^"]*(")', r'\g<1>%s\g<2>' % ea, nb, count=1)
    else:
        nb = re.sub(r'(<a:latin typeface="[^"]*"/>)', r'\1<a:ea typeface="%s"/>' % ea, nb, count=1)
    theme = theme.replace(blk, nb)

set_theme_font('major', 'Times New Roman', '黑体')
set_theme_font('minor', 'Times New Roman', '宋体')
for b in ('major', 'minor'):
    m = re.search(r'<a:' + b + r'Font>.*?</a:' + b + r'Font>', theme, re.S)
    blk = m.group(0)
    lat = re.search(r'<a:latin typeface="([^"]*)"', blk)
    ea = re.search(r'<a:ea typeface="([^"]*)"', blk)
    print('  theme %sFont -> latin=%s ea=%s' % (b, lat.group(1) if lat else None,
                                                ea.group(1) if ea else None))

CN_BODY = '宋体'
CN_HEAD = '黑体'
EN_BODY = 'Times New Roman'
EN_CODE = 'Consolas'

# --- add eastAsia font to every rFonts element ---
def add_ea(m):
    tag = m.group(0)
    if 'w:eastAsia=' in tag:
        return tag
    if tag.endswith('/>'):
        return tag[:-2] + ' w:eastAsia="%s"/>' % CN_BODY
    return tag[:-1] + ' w:eastAsia="%s">' % CN_BODY
styles = re.sub(r'<w:rFonts\b[^>]*?/?>', add_ea, styles)

# --- force headings to 黑体 ---
for sid in ('Heading1', 'Heading2', 'Heading3', 'Heading4', 'Title', 'Subtitle'):
    m = re.search(r'<w:style [^>]*w:styleId="%s"[^>]*>.*?</w:style>' % sid, styles, re.S)
    if not m:
        continue
    blk = m.group(0)
    new = re.sub(r'w:eastAsia="[^"]*"', 'w:eastAsia="%s"' % CN_HEAD, blk)
    if 'w:eastAsia=' not in new:
        new = re.sub(r'(<w:rFonts\b[^>]*?)/>', r'\1 w:eastAsia="%s"/>' % CN_HEAD, new)
    # remove theme override so the explicit eastAsia font wins
    new = re.sub(r'\s+w:eastAsiaTheme="[^"]*"', '', new)
    styles = styles.replace(blk, new)

# --- font sizes (half-points) ---
def set_size(style_id, half_pts):
    global styles
    m = re.search(r'<w:style [^>]*w:styleId="%s"[^>]*>.*?</w:style>' % style_id, styles, re.S)
    if not m:
        print('  (style not found:', style_id, ')'); return
    blk = m.group(0)
    if '<w:sz ' in blk:
        nb = re.sub(r'<w:sz w:val="\d+"/>', '<w:sz w:val="%d"/>' % half_pts, blk)
        nb = re.sub(r'<w:szCs w:val="\d+"/>', '<w:szCs w:val="%d"/>' % half_pts, nb)
    else:
        nb = blk.replace('</w:style>',
                         '<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:style>' % (half_pts, half_pts))
    styles = styles.replace(blk, nb)

set_size('Normal', 24)       # 12pt
set_size('Title', 36)        # 18pt
set_size('Heading1', 32)     # 16pt
set_size('Heading2', 28)     # 14pt
set_size('Heading3', 26)     # 13pt
set_size('Heading4', 24)     # 12pt
set_size('Compact', 24)
set_size('Table', 22)        # 11pt in tables

# --- 标题一律纯黑（pandoc 默认是主题蓝 4F81BD / 335B8A / 366091）---
# 注意：pandoc 原始模板的 styleId 是 Heading1..Heading9 / Title / AbstractTitle / TOCHeading
#       （Word 另存后才会变成数字 2/4/5…，两种都要能处理）
BLACK_STYLES = (['Heading%d' % i for i in range(1, 10)]
                + ['Title', 'Subtitle', 'AbstractTitle', 'TOCHeading'])

def force_black(style_id):
    global styles
    m = re.search(r'<w:style\b[^>]*?w:styleId="' + re.escape(style_id) + r'"[^>]*?>.*?</w:style>',
                  styles, re.S)
    if not m:
        return False
    blk = m.group(0)
    nb = blk
    if '<w:color' in nb:
        nb = re.sub(r'<w:color\b[^>]*?/>', '<w:color w:val="000000"/>', nb)
    elif '<w:rPr>' in nb:
        nb = nb.replace('<w:rPr>', '<w:rPr><w:color w:val="000000"/>', 1)
    else:
        nb = nb.replace('</w:style>', '<w:rPr><w:color w:val="000000"/></w:rPr></w:style>')
    nb = re.sub(r'\s+w:themeColor="[^"]*"', '', nb)
    nb = re.sub(r'\s+w:themeTint="[^"]*"', '', nb)
    nb = re.sub(r'\s+w:themeShade="[^"]*"', '', nb)
    changes = 1 if nb != blk else 0
    styles = styles.replace(blk, nb)
    return True

n_ok = 0
for sid in BLACK_STYLES:
    if force_black(sid):
        n_ok += 1
print('  标题样式处理：命中 %d / %d 个' % (n_ok, len(BLACK_STYLES)))
print('  styles.xml 剩余 4F81BD:', styles.count('4F81BD'),
      ' 剩余 335B8A:', styles.count('335B8A'),
      ' 剩余 345A8A:', styles.count('345A8A'),
      ' 剩余 366091:', styles.count('366091'))

# --- 主题强调色一并压黑，避免 Word 从主题重算颜色 ---
theme = re.sub(r'(<a:accent\d>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}(")',
               r'\g<1>000000\g<2>', theme)
theme = re.sub(r'(<a:hlink>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}(")',
               r'\g<1>000000\g<2>', theme)
print('  主题强调色已压黑')

# --- add 1.5 line spacing + first-line indent-free, comfortable margins in sectPr ---
doc = zin.read('word/document.xml').decode('utf-8')
sect = re.search(r'<w:sectPr\b.*?</w:sectPr>', doc, re.S)
if sect:
    blk = sect.group(0)
    if '<w:pgMar' in blk:
        nb = re.sub(r'<w:pgMar\b[^>]*/>',
                    '<w:pgMar w:top="1440" w:right="1247" w:bottom="1440" w:left="1247" '
                    'w:header="851" w:footer="992" w:gutter="0"/>', blk)
    else:
        nb = blk.replace('</w:sectPr>',
                         '<w:pgMar w:top="1440" w:right="1247" w:bottom="1440" w:left="1247" '
                         'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>')
    doc = doc.replace(blk, nb)

# --- remove ALL eastAsiaTheme overrides so explicit eastAsia fonts win ---
styles = re.sub(r'\s+w:eastAsiaTheme="[^"]*"', '', styles)

# --- write out ---
zout = zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED)
for n in zin.namelist():
    if n == 'word/styles.xml':
        zout.writestr(n, styles.encode('utf-8'))
    elif n == 'word/document.xml':
        zout.writestr(n, doc.encode('utf-8'))
    elif n == 'word/theme/theme1.xml':
        zout.writestr(n, theme.encode('utf-8'))
    else:
        zout.writestr(n, zin.read(n))
zout.close(); zin.close()
print('reference written:', OUT, os.path.getsize(OUT), 'bytes')
print('eastAsia rFonts count:', styles.count('w:eastAsia='))
print('eastAsiaTheme remaining:', styles.count('eastAsiaTheme'))
