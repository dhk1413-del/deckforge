# -*- coding: utf-8 -*-
"""门禁检查：deckforge-standalone.html 必须与 ui-design/app.css 的令牌集合同步。

背景：standalone 单文件版由 tools/build_standalone.py 从 ui-design/app.css 内联生成，
会随设计令牌一起漂移（曾停在旧版本、无人察觉）。本检查让「忘了重新生成」在门禁里
直接暴露，而不是把过期产物悄悄发出去。

修复方式：python tools/build_standalone.py
"""
import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_CSS = os.path.join(ROOT, "ui-design", "app.css")
STANDALONE = os.path.join(ROOT, "deckforge-standalone.html")
# 只比对设计令牌（CSS 自定义属性），不比对文案，避免误报
PATTERN = r'--((?:color|radius|spacing|text|shadow|font)-[a-z0-9-]+)'


def main() -> int:
    if not os.path.exists(STANDALONE):
        print("  ✗ 缺少 deckforge-standalone.html；运行 python tools/build_standalone.py 生成")
        return 1
    if not os.path.exists(APP_CSS):
        print("  ✗ 缺少 ui-design/app.css")
        return 1
    css = set(re.findall(PATTERN, io.open(APP_CSS, encoding="utf-8").read()))
    std = set(re.findall(PATTERN, io.open(STANDALONE, encoding="utf-8").read()))
    missing = sorted(css - std)
    if missing:
        print("  ✗ standalone 与 app.css 不同步：缺 %d 个令牌 %s" % (len(missing), missing[:8]))
        print("    修复：python tools/build_standalone.py")
        return 1
    print("  ✓ standalone 令牌与 app.css 同步（%d 个）" % len(css))
    return 0


if __name__ == "__main__":
    sys.exit(main())
