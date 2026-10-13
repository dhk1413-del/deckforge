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
