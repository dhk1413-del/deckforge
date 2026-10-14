#!/usr/bin/env bash
# 从 docs/使用说明.md 生成三种格式：自包含 HTML（浏览器看）、PDF、DOCX。
#
# 为什么要预缩放图片：LibreOffice 的 HTML 导入既不认 CSS max-width，也不认 <img width>，
# 会按原图像素宽摆放（1440px → 1080pt），塞进 A4（版心约 468pt）就会被裁。这里先把图片缩到
# 620px 宽再喂给 LibreOffice，PDF/Word 里的图就正好落在版心内。
#
# 用法：bash tools/build_manual.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
SOFFICE="${SOFFICE:-/Applications/LibreOffice.app/Contents/MacOS/soffice}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/screenshots" "$WORK/diagrams"

echo "== 1/4 预缩放图片到 620px =="
"$PY" - "$WORK" <<'PY'
import glob, os, sys
from PIL import Image
work = sys.argv[1]
for path in glob.glob('docs/screenshots/*.png'):
    im = Image.open(path).convert('RGB')
    if im.width > 620:
        im = im.resize((620, round(im.height * 620 / im.width)), Image.LANCZOS)
    im.save(os.path.join(work, 'screenshots', os.path.basename(path)), 'PNG', optimize=True)
print('   截图 %d 张' % len(glob.glob(os.path.join(work, 'screenshots', '*.png'))))
PY

if [ -x "$CHROME" ]; then
  for f in docs/diagrams/*.svg; do
    name="$(basename "$f" .svg)"
    prof="$WORK/chrome-$name"
    rm -rf "$prof"
    "$CHROME" --headless=new --disable-gpu --no-first-run --no-default-browser-check \
      --user-data-dir="$prof" --window-size=1320,900 --default-background-color=FFFFFFFF \
      --screenshot="$WORK/diagrams/$name.png" "file://$(pwd)/$f" >/dev/null 2>&1
  done
  "$PY" - "$WORK" <<'PY'
import glob, os, sys
from PIL import Image
work = sys.argv[1]
for path in glob.glob(os.path.join(work, 'diagrams', '*.png')):
    im = Image.open(path).convert('RGB')
    bbox = Image.eval(im, lambda v: 255 - v).getbbox()      # 裁掉空白边
    if bbox:
        im = im.crop(bbox)
    if im.width > 620:
        im = im.resize((620, round(im.height * 620 / im.width)), Image.LANCZOS)
    im.save(path, 'PNG', optimize=True)
print('   流程图 %d 张' % len(glob.glob(os.path.join(work, 'diagrams', '*.png'))))
PY
else
  echo "   ⚠ 未找到 Chrome，流程图改用仓库里的 SVG（Word 里可能偏大）"
  cp docs/diagrams/*.svg "$WORK/diagrams/"
fi

echo "== 2/4 自包含 HTML（全分辨率，浏览器/打印用） =="
"$PY" tools/md_to_html.py docs/使用说明.md docs/使用说明.html --img-width=760

echo "== 3/4 生成给 LibreOffice 的中间 HTML（内嵌缩放图） =="
"$PY" tools/md_to_html.py docs/使用说明.md "$WORK/manual.html" --asset-dir="$WORK"

echo "== 4/4 LibreOffice 转 PDF / DOCX =="
"$SOFFICE" --headless --infilter="HTML (StarWriter)" --convert-to 'pdf:writer_pdf_Export' --outdir "$WORK" "$WORK/manual.html" >/dev/null
"$SOFFICE" --headless --infilter="HTML (StarWriter)" --convert-to 'docx:MS Word 2007 XML' --outdir "$WORK" "$WORK/manual.html" >/dev/null
cp "$WORK/manual.pdf" "docs/使用说明.pdf"
cp "$WORK/manual.docx" "docs/使用说明.docx"
echo "✓ docs/使用说明.html（%.1f MB） / .pdf / .docx" >/dev/null
ls -la docs/使用说明.*
