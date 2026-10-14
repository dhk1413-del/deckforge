#!/usr/bin/env bash
# Rebuild all guide formats, retaining original PNG resolution.
# DOCS_PYTHON must contain python-docx and Pillow; SOFFICE can select a runtime.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${DOCS_PYTHON:-.venv/bin/python}"
SOFFICE="${SOFFICE:-soffice}"
if [ "$SOFFICE" = soffice ] && ! command -v soffice >/dev/null 2>&1 && [ -x /Applications/LibreOffice.app/Contents/MacOS/soffice ]; then
  SOFFICE=/Applications/LibreOffice.app/Contents/MacOS/soffice
fi
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The bundled LibreOffice runtime needs explicit access to macOS CJK fonts.
if [ -d /System/Library/Fonts ] && [ -z "${FONTCONFIG_FILE:-}" ]; then
  cat > "$WORK/fonts.conf" <<EOF
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
<dir>/System/Library/Fonts</dir>
<dir>/System/Library/Fonts/Supplemental</dir>
<cachedir>$WORK/fontcache</cachedir>
</fontconfig>
EOF
  export FONTCONFIG_FILE="$WORK/fonts.conf"
fi

"$PY" tools/build_manual.py
"$SOFFICE" "-env:UserInstallation=file://$WORK/profile" --headless \
  --convert-to 'pdf:writer_pdf_Export:{"ReduceImageResolution":{"type":"boolean","value":"false"},"UseLosslessCompression":{"type":"boolean","value":"true"}}' \
  --outdir "$WORK" docs/使用说明.docx
test -s "$WORK/使用说明.pdf"
cp "$WORK/使用说明.pdf" docs/使用说明.pdf
echo "已生成 Markdown 对应的 HTML、Word 和 PDF；保留原图像素。"
