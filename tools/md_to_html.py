# -*- coding: utf-8 -*-
"""把 `docs/使用说明.md` 这类说明文档转成可打印的 HTML（供 LibreOffice 转 PDF / DOCX，或直接用浏览器打印）。

用法：
    .venv/bin/python tools/md_to_html.py docs/使用说明.md docs/使用说明.html            # 图片以 base64 内嵌（单文件自包含）
    .venv/bin/python tools/md_to_html.py docs/使用说明.md /tmp/manual.html --images path  # 图片写绝对路径（给 LibreOffice 用）

只实现仓库文档实际用到的 Markdown 子集：标题、段落、无序/有序列表、表格、围栏代码、引用、
水平线、行内 `code`/**粗体**/*斜体*/[链接](url)/图片语法。不做 HTML 透传，避免引入注入面。
"""
from __future__ import annotations

import base64
import io
import os
import re
import sys

IMAGE_EXT = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
             '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml'}


def esc(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inline(text: str, base_dir: str, embed: bool, img_width: int = 0, asset_dir: str = '') -> str:
    """行内元素：图片 → 链接 → 代码 → 粗体 → 斜体。

    img_width > 0 时给 <img> 写显式 width 属性：LibreOffice 的 HTML 导入不认 CSS max-width，
    不给宽度它就会按原图像素宽（1440px→1080pt）塞进 A4，导致图片被裁。
    """
    def image(match):
        alt, src = match.group(1), match.group(2)
        path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if asset_dir and not os.path.isabs(src):
            mirror = os.path.join(asset_dir, src)
            if os.path.isfile(mirror):
                path = mirror   # LibreOffice 不认 CSS/width，改用预缩放副本
        if not os.path.isfile(path):
            return '<em>[缺失图片：%s]</em>' % esc(src)
        ext = os.path.splitext(path)[1].lower()
        mime = IMAGE_EXT.get(ext, 'application/octet-stream')
        if embed:
            data = base64.b64encode(io.open(path, 'rb').read()).decode()
            url = 'data:%s;base64,%s' % (mime, data)
        else:
            url = 'file://' + os.path.abspath(path)
        size = ' width="%d"' % img_width if img_width else ''
        return '<img src="%s" alt="%s"%s/>' % (url, esc(alt), size)

    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', image, text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'<em>\1</em>', text)
    return text


def convert(md_path: str, embed: bool = True, title: str | None = None, img_width: int = 0, asset_dir: str = '') -> str:
    base_dir = os.path.dirname(os.path.abspath(md_path))
    lines = io.open(md_path, encoding='utf-8').read().split('\n')
    def inl(text: str) -> str:
        return inline(text, base_dir, embed, img_width, asset_dir)
    out, i = [], 0
    in_code = False
    code_buf: list[str] = []
    list_kind = None            # 'ul' | 'ol'
    in_table = False

    def close_list():
        nonlocal list_kind
        if list_kind:
            out.append('</%s>' % list_kind)
            list_kind = None

    def close_table():
        nonlocal in_table
        if in_table:
            out.append('</tbody></table>')
            in_table = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith('```'):
            if in_code:
                out.append('<pre><code>%s</code></pre>' % esc('\n'.join(code_buf)))
                code_buf, in_code = [], False
            else:
                close_list(); close_table(); in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if not stripped:
            close_list(); close_table()
            i += 1
            continue

        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', stripped):
            close_list(); close_table(); out.append('<hr/>'); i += 1
            continue

        heading = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if heading:
            close_list(); close_table()
            level = len(heading.group(1))
            out.append('<h%d>%s</h%d>' % (level, inl(heading.group(2)), level))
            i += 1
            continue

        if stripped.startswith('>'):
            close_list(); close_table()
            quote = [stripped.lstrip('>').strip()]
            i += 1
            while i < len(lines) and lines[i].strip().startswith('>'):
                quote.append(lines[i].strip().lstrip('>').strip())
                i += 1
            out.append('<blockquote>%s</blockquote>' % inl(' '.join(quote)))
            continue

        # 表格：| a | b |  + 分隔行
        if stripped.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[\s:|-]+\|$', lines[i + 1].strip()):
            close_list()
            header = [c.strip() for c in stripped.strip('|').split('|')]
            out.append('<table><thead><tr>%s</tr></thead><tbody>'
                       % ''.join('<th>%s</th>' % inl(c) for c in header))
            in_table = True
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                out.append('<tr>%s</tr>' % ''.join('<td>%s</td>' % inl(c) for c in cells))
                i += 1
            close_table()
            continue

        bullet = re.match(r'^[-*]\s+(.*)$', stripped)
        ordered = re.match(r'^\d+[.)]\s+(.*)$', stripped)
        if bullet or ordered:
            close_table()
            kind = 'ul' if bullet else 'ol'
            if list_kind != kind:
                close_list()
                out.append('<%s>' % kind)
                list_kind = kind
            out.append('<li>%s</li>' % inl((bullet or ordered).group(1)))
            i += 1
            continue

        close_list(); close_table()
        out.append('<p>%s</p>' % inl(stripped))
        i += 1

    close_list(); close_table()
    if in_code:
        out.append('<pre><code>%s</code></pre>' % esc('\n'.join(code_buf)))

    doc_title = title or os.path.splitext(os.path.basename(md_path))[0]
    return HTML_TEMPLATE % (esc(doc_title), '\n'.join(out))


HTML_TEMPLATE = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>%s</title>
<style>
  :root { --ink:#101828; --sub:#5A6B87; --line:#E3EBF9; --accent:#1E78FA; --bg:#FFFFFF; }
  body { margin:0 auto; padding:40px 48px 64px; max-width:900px; background:var(--bg); color:var(--ink);
         font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,-apple-system,sans-serif;
         font-size:14px; line-height:1.75; }
  h1 { font-size:26px; margin:0 0 6px; }
  h2 { font-size:20px; margin:34px 0 10px; padding-bottom:6px; border-bottom:1px solid var(--line); }
  h3 { font-size:16px; margin:22px 0 8px; }
  h4 { font-size:14px; margin:18px 0 6px; color:var(--sub); }
  p { margin:10px 0; }
  a { color:var(--accent); text-decoration:none; }
  code { background:#F1F6FD; border-radius:4px; padding:1px 5px; font-size:12.5px;
         font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
  pre { background:#F7FAFF; border:1px solid var(--line); border-radius:10px; padding:12px 14px; overflow:auto; }
  pre code { background:none; padding:0; }
  blockquote { margin:12px 0; padding:10px 16px; border-left:4px solid var(--accent); background:#F7FAFF; color:var(--sub); }
  table { width:100%%; border-collapse:collapse; margin:12px 0; font-size:13px; }
  th,td { border:1px solid var(--line); padding:7px 10px; text-align:left; vertical-align:top; }
  th { background:#F5F8FF; }
  img { max-width:100%%; border:1px solid var(--line); border-radius:10px; margin:8px 0; }
  hr { border:0; border-top:1px solid var(--line); margin:24px 0; }
  ul,ol { margin:8px 0 8px 22px; padding:0; }
  li { margin:4px 0; }
  @media print { body { padding:0 8mm; font-size:12px; } h2 { page-break-after:avoid; } img { page-break-inside:avoid; } }
</style></head>
<body>
%s
</body></html>
'''


def main():
    positional = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(positional) < 2:
        print(__doc__)
        return 1
    md_path, out_path = positional[0], positional[1]
    embed = '--images=path' not in sys.argv
    img_width = 0
    for arg in sys.argv:
        if arg.startswith('--img-width='):
            img_width = int(arg.split('=', 1)[1])
    asset_dir = ''
    for arg in sys.argv:
        if arg.startswith('--asset-dir='):
            asset_dir = arg.split('=', 1)[1]
    html = convert(md_path, embed=embed, img_width=img_width, asset_dir=asset_dir)
    io.open(out_path, 'w', encoding='utf-8').write(html)
    print('✓ %s → %s（图片：%s）' % (md_path, out_path, 'base64 内嵌' if embed else '绝对路径'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
