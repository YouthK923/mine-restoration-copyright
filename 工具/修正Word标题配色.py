# -*- coding: utf-8 -*-
"""
把用户已编辑的 DOCX 的标题样式改为「黑体 + 纯黑」。
严格只修改 styles.xml 的样式定义与 theme 配色：
  - 不触碰 word/document.xml（正文内容零改动，用户的编辑完整保留）
  - 不触碰表格、段落、图片
先备份。
"""
import os, sys, re, shutil, zipfile
sys.stdout.reconfigure(encoding='utf-8')

# 目标文档：归类后计划书位于 文档/ 目录
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FN = os.path.join(BASE, '文档', '软著功能计划.docx')
BAK = FN.replace('.docx', '_改色前备份.docx')

if not os.path.exists(BAK):
    shutil.copy2(FN, BAK)
    print('已备份 ->', BAK)
else:
    print('备份已存在，跳过:', BAK)

z = zipfile.ZipFile(FN)
names = z.namelist()
parts = {n: z.read(n) for n in names}
z.close()

# 改动前的 document.xml 指纹，用于事后证明正文未被改动
import hashlib
doc_before = parts['word/document.xml']
doc_hash_before = hashlib.sha256(doc_before).hexdigest()

# ---------- 1) styles.xml ----------
styles = parts['word/styles.xml'].decode('utf-8')

HEADING_IDS = ['2', '4', '5', '6', '7', '8', '9', '10', '11',   # heading 1-9
               '16',   # Title
               '26',   # Abstract Title
               '39']   # TOC Heading

def blacken(style_id):
    global styles
    m = re.search(r'<w:style\b[^>]*?w:styleId="' + style_id + r'"[^>]*?>.*?</w:style>',
                  styles, re.S)
    if not m:
        print('  未找到样式 id=%s' % style_id); return 0
    blk = m.group(0)
    nb = blk
    n = 0

    # a) 已有 <w:color .../> -> 强制 val=000000 并去掉主题引用
    def fix_color(mm):
        nonlocal n
        n += 1
        return '<w:color w:val="000000"/>'
    if '<w:color' in nb:
        nb = re.sub(r'<w:color\b[^>]*?/>', fix_color, nb)
    else:
        # b) 没有 color 元素 -> 在 rPr 内插入
        if '<w:rPr>' in nb:
            nb = nb.replace('<w:rPr>', '<w:rPr><w:color w:val="000000"/>', 1)
        else:
            nb = nb.replace('</w:style>',
                            '<w:rPr><w:color w:val="000000"/></w:rPr></w:style>')
        n += 1

    # c) 清除 Run 级主题色引用（themeColor 会让 Word 忽略显式 val）
    nb = re.sub(r'\s+w:themeColor="[^"]*"', '', nb)
    nb = re.sub(r'\s+w:themeTint="[^"]*"', '', nb)
    nb = re.sub(r'\s+w:themeShade="[^"]*"', '', nb)

    # d) 确保中文字体为黑体（用户要求标题黑体）
    if 'w:eastAsia=' in nb:
        nb = re.sub(r'w:eastAsia="[^"]*"', 'w:eastAsia="黑体"', nb)
    nb = re.sub(r'\s+w:eastAsiaTheme="[^"]*"', '', nb)

    styles = styles.replace(blk, nb)
    return n

print('--- 修改标题样式颜色 ---')
for sid in HEADING_IDS:
    c = blacken(sid)
    if c:
        print('  样式 id=%-3s -> 已设为纯黑 (改动 %d 处 color)' % (sid, c))

print('styles.xml 中剩余 4F81BD:', styles.count('4F81BD'))
print('styles.xml 中剩余 335B8A:', styles.count('335B8A'))
print('styles.xml 中剩余 345A8A:', styles.count('345A8A'))
print('styles.xml 中剩余 366091:', styles.count('366091'))

# ---------- 2) theme1.xml ---------- 把主题强调色也压成黑，双保险 ----------
theme = parts['word/theme/theme1.xml'].decode('utf-8')
accent_before = re.findall(r'<a:accent(\d)>\s*<a:srgbClr val="([0-9A-Fa-f]{6})"', theme)
print('--- 主题强调色（改前）:', accent_before)
theme_new = re.sub(r'(<a:accent\d>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}(")',
                   r'\g<1>000000\g<2>', theme)
print('    主题强调色（改后）:',
      re.findall(r'<a:accent(\d)>\s*<a:srgbClr val="([0-9A-Fa-f]{6})"', theme_new))
# hyperlink 色也一并压黑（避免目录/链接仍是蓝色）
theme_new = re.sub(r'(<a:hlink>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}(")',
                   r'\g<1>000000\g<2>', theme_new)

# ---------- 3) 写回 ----------
parts['word/styles.xml'] = styles.encode('utf-8')
parts['word/theme/theme1.xml'] = theme_new.encode('utf-8')

TMP = FN + '.tmp'
zo = zipfile.ZipFile(TMP, 'w', zipfile.ZIP_DEFLATED)
for n in names:
    zo.writestr(n, parts[n])
zo.close()
os.replace(TMP, FN)

# ---------- 4) 校验 ----------
z2 = zipfile.ZipFile(FN)
doc_after = z2.read('word/document.xml')
doc_hash_after = hashlib.sha256(doc_after).hexdigest()
print()
print('=== 校验 ===')
print('  document.xml SHA256 改前:', doc_hash_before[:32])
print('  document.xml SHA256 改后:', doc_hash_after[:32])
print('  正文是否被动过:', '❌ 被改动了！' if doc_hash_before != doc_hash_after else '✅ 完全未改动')
print('  文件大小:', os.path.getsize(FN), 'bytes')
