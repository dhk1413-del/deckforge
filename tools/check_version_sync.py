# -*- coding: utf-8 -*-
"""版本号一致性门禁：仓库根 `VERSION` 是唯一真源，别处只许引用或保持同步。

四处必须对齐：
  1. `VERSION` 文件（真源，且必须是 `主.次.补丁`）；
  2. `web/package.json` 的 `version`（npm 要求字面量，改版本时容易漏）；
  3. `CHANGELOG.md` 最上面那条版本条目（防止"打了 tag 却没写变更记录"）；
  4. `server/app/main.py` 不得再出现写死的 `VERSION = "x.y.z"`（应调用 paths.app_version()）。

用法：
    .venv/bin/python tools/check_version_sync.py
退出码：0 = 一致；1 = 不一致（会把每处实际值打出来）。
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main():
    problems = []

    version_path = os.path.join(ROOT, "VERSION")
    if not os.path.isfile(version_path):
        print("[version] ✗ 缺少 VERSION 文件（版本号唯一真源）")
        return 1
    version = read_text(version_path).strip()
    print("[version] VERSION 真源 = %s" % version)
    if not SEMVER.match(version):
        problems.append("VERSION 内容 %r 不是 主.次.补丁 形式" % version)

    # 2) web/package.json
    pkg_path = os.path.join(ROOT, "web", "package.json")
    try:
        pkg_version = json.loads(read_text(pkg_path)).get("version", "")
    except (OSError, ValueError) as exc:
        problems.append("读 web/package.json 失败：%s" % exc)
        pkg_version = ""
    print("[version] web/package.json = %s" % (pkg_version or "(缺失)"))
    if pkg_version != version:
        problems.append("web/package.json 是 %s，与 VERSION 的 %s 不一致" % (pkg_version or "空", version))

    # 3) CHANGELOG.md 最上面一条（跳过 [Unreleased]）
    changelog_path = os.path.join(ROOT, "CHANGELOG.md")
    if os.path.isfile(changelog_path):
        match = re.search(r"^##\s*\[(\d+\.\d+\.\d+)\]", read_text(changelog_path), re.M)
        top = match.group(1) if match else ""
        print("[version] CHANGELOG.md 首条 = %s" % (top or "(缺失)"))
        if not top:
            problems.append("CHANGELOG.md 里找不到形如 `## [x.y.z]` 的版本条目")
        elif top != version:
            problems.append("CHANGELOG.md 首条是 %s，与 VERSION 的 %s 不一致" % (top, version))
    else:
        problems.append("缺少 CHANGELOG.md（发版必须有变更记录）")

    # 4) main.py 不许写死版本号
    main_path = os.path.join(ROOT, "server", "app", "main.py")
    if os.path.isfile(main_path):
        hard = re.search(r"^\s*VERSION\s*=\s*[\"'][^\"']+[\"']", read_text(main_path), re.M)
        if hard:
            problems.append("server/app/main.py 写死了版本号（%s）——应调用 paths.app_version()"
                            % hard.group(0).strip())
        else:
            print("[version] server/app/main.py 未写死版本号（读 VERSION，正确）")

    if problems:
        print("[version] ✗ 不一致 %d 处：" % len(problems))
        for item in problems:
            print("    - " + item)
        return 1

    print("[version] ✓ 版本号四处一致，均为 %s。" % version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
