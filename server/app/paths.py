# -*- coding: utf-8 -*-
"""路径常量与 .env 读取（无任何内部依赖，供 config / db 共用，避免循环导入）。

.env 认两个位置：工作区根 `.env` 与 `config/.env`（模板在 config/，后者优先）。
数据目录可用 `DECKFORGE_DATA` 重定向（相对路径按工作区根解析）——改完需重启后端。
"""
import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(ROOT, "config")
STYLE_DIR = os.path.join(ROOT, "style-packs")
UI_DIR = os.path.join(ROOT, "ui-design")
ENV_FILES = [os.path.join(ROOT, ".env"), os.path.join(CONFIG_DIR, ".env")]
VERSION_FILE = os.path.join(ROOT, "VERSION")


def app_version() -> str:
    """应用版本号：仓库根 `VERSION` 是**唯一真源**（发版时只改这一处）。

    前端 `web/package.json` 的 `version` 受 npm 约束必须是字面量，无法直接引用本文件；
    两者的同步由 `tools/check_version_sync.py` 在门禁里强制校验，不一致直接报错。
    """
    try:
        with io.open(VERSION_FILE, encoding="utf-8") as fh:
            value = fh.read().strip()
    except OSError:
        return "0.0.0"
    return value or "0.0.0"


def load_env() -> dict:
    """合并 ENV_FILES 的键值（后读覆盖先读）；只做 `KEY=VALUE` 简单解析。"""
    env = {}
    for path in ENV_FILES:
        if not os.path.exists(path):
            continue
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


DATA_DIR = os.path.abspath(os.path.join(ROOT, os.environ.get("DECKFORGE_DATA") or load_env().get("DECKFORGE_DATA") or "data"))
FILES_DIR = os.path.join(DATA_DIR, "files")

os.makedirs(FILES_DIR, exist_ok=True)
