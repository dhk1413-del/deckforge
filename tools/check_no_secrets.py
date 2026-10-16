# -*- coding: utf-8 -*-
"""密钥门禁：任何模型 API key（以及私钥、运行数据）都不许进入 git 或推送到 GitHub。

用法：
    python3 tools/check_no_secrets.py --staged          # 检查 git 索引（pre-commit 用）
    python3 tools/check_no_secrets.py --head            # 检查 HEAD 树（默认）
    python3 tools/check_no_secrets.py --range A..B      # 检查一段提交（pre-push 用）
    python3 tools/check_no_secrets.py --range <sha>     # 检查该提交及其全部祖先（新分支）
    python3 tools/check_no_secrets.py --all             # 检查全部历史（审计用）

三层检查：
  1. 路径：`.env` / `data/` / `*.db` / `*.pem` 等绝不允许入库的文件名；
  2. 形态：sk- / ghp_ / AIza / AKIA / PEM / JWT / 赋值式长串 等密钥特征；
  3. 真值：把本机**真实**密钥（`.env` 与数据库 settings 表）当作字面量搜一遍。

实现要点：所有对象经一次 `git cat-file --batch` 取出、在 Python 里匹配（不用 git grep 的
POSIX 正则，避免 `(?i)`/`\\s` 静默失效）；**绝不回显命中的内容**，只打印 `文件:行号` 与
规则名——否则门禁自己就成了泄漏点。门禁自身出错时**失败关闭**（exit 2），不默认放行。
退出码：0 = 干净；1 = 命中；2 = 门禁故障。
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DB_PATH = os.path.join(ROOT, "data", "deckforge.db")
ENV_FILES = [os.path.join(ROOT, ".env"), os.path.join(ROOT, "config", ".env")]
ENV_KEY_NAMES = ("GUAIHUB_API_KEY", "DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY",
                 "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
MAX_OBJECTS = 20000          # 上限，避免在超大仓库上把门禁拖死

# 绝不允许入库的路径（相对仓库根，正则）
FORBIDDEN_PATHS = [
    (r"(^|/)\.env$", "环境变量文件（密钥）"),
    (r"(^|/)\.env\.(local|.*\.local)$", "环境变量文件（密钥）"),
    (r"(^|/)config/\.env$", "环境变量文件（密钥）"),
    (r"(^|/)data/", "运行时数据（数据库内含用户密钥）"),
    (r"\.(db|db-wal|db-shm|sqlite|sqlite3)$", "SQLite 数据库（settings 表存密钥）"),
    (r"\.(pem|key|p12|pfx)$", "私钥 / 证书"),
    (r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$", "SSH 私钥"),
    (r"(^|/)credentials\.json$", "云凭据文件"),
    (r"^web/dist/", "前端构建产物（不入库）"),
]

# 密钥形态（Python 正则）
PATTERN_RULES = [
    ("OpenAI 风格 sk- key", r"sk-[A-Za-z0-9_\-]{16,}"),
    ("Anthropic sk-ant key", r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    ("GitHub token gh?_", r"gh[pousr]_[A-Za-z0-9]{20,}"),
    ("GitHub 细粒度 PAT", r"github_pat_[A-Za-z0-9_]{20,}"),
    ("Google API key", r"AIza[0-9A-Za-z_\-]{30,}"),
    ("AWS Access Key ID", r"AKIA[0-9A-Z]{16}"),
    ("Slack token", r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    ("PEM 私钥", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("JWT", r"eyJ[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{10,}"),
    ("赋值式密钥（长串，非变量引用）",
     r"(?i)(api[_\-]?key|apikey|access[_\-]?token|auth[_\-]?token|secret[_\-]?key"
     r"|client[_\-]?secret|password|passwd)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{20,}"),
]
COMPILED = [(name, re.compile(rx)) for name, rx in PATTERN_RULES]
# 注意：FORBIDDEN_PATHS 是 (正则, 说明)，别把两者写反——反了会拿中文说明去当正则，
# 结果是路径规则静默失效（这个坑正是靠「探针必须有拦截」的测试才发现的）。
FORBIDDEN = [(label, re.compile(rx)) for rx, label in FORBIDDEN_PATHS]


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True)


def fail(msg, code=2):
    sys.stderr.write("[check_no_secrets] ✗ %s\n" % msg)
    raise SystemExit(code)


# ── 对象枚举 ────────────────────────────────────────────────────────────

def objects_staged():
    """索引里的对象：sha -> 路径。"""
    out = git("ls-files", "-s", "--cached").stdout
    items = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 2 and path:
            items[parts[1]] = path
    return items


def objects_head():
    out = git("ls-tree", "-r", "HEAD").stdout
    items = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and parts[1] == "blob" and path:
            items[parts[2]] = path
    return items


def objects_revs(revs):
    """一段提交里可达的全部对象：sha -> 路径（取第一个见到的路径）。"""
    out = git("rev-list", "--objects", *revs).stdout
    items = {}
    for line in out.splitlines():
        sha, _, path = line.partition(" ")
        if sha and path and sha not in items:
            items[sha] = path
    return items


def history_names():
    """历史上被添加过的文件路径（含后来删掉的）。"""
    out = git("log", "--all", "--pretty=format:", "--name-only", "--diff-filter=A").stdout
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


# ── 真实密钥收集（只在本机读取，绝不打印） ──────────────────────────────

def read_env_keys():
    values = []
    for path in ENV_FILES:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    name, _, value = line.partition("=")
                    name = name.strip()
                    if name.startswith("export "):
                        name = name[7:].strip()
                    value = value.strip().strip("'\"")
                    if name.endswith(("_API_KEY", "_TOKEN", "_SECRET")) and len(value) >= 8:
                        values.append(value)
        except OSError:
            continue
    for name in ENV_KEY_NAMES:
        value = os.environ.get(name, "")
        if len(value) >= 8:
            values.append(value)
    return values


def read_db_keys():
    if not os.path.isfile(DB_PATH):
        return []
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % DB_PATH, uri=True, timeout=3)
        try:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    values = []
    for key, value in rows:
        if not isinstance(value, str):
            continue
        low = (key or "").lower()
        if not any(tag in low for tag in ("key", "token", "secret")):
            continue
        if len(value) < 8 or any(ch.isspace() for ch in value):
            continue
        if set(value) <= set("*•·"):        # 界面回显用的掩码，不是真值
            continue
        values.append(value)
    return values


def known_keys():
    seen, ordered = set(), []
    for value in read_env_keys() + read_db_keys():
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


# ── 批量取内容 ──────────────────────────────────────────────────────────

def batch_contents(shas):
    """一次 git cat-file --batch 取回全部对象内容：sha -> bytes（非 blob 也返回，调用方过滤）。"""
    if not shas:
        return {}
    proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    payload = ("\n".join(shas) + "\n").encode()
    out, err = proc.communicate(payload)
    if proc.returncode != 0:
        fail("git cat-file 失败（退出码 %s）：%s" % (proc.returncode, err.decode("utf-8", "replace")[:200]))
    blobs, pos = {}, 0
    while True:
        nl = out.find(b"\n", pos)
        if nl < 0:
            break
        header = out[pos:nl].decode("utf-8", "replace").split()
        pos = nl + 1
        if len(header) < 3:
            continue
        sha, otype, size = header[0], header[1], int(header[2])
        body = out[pos:pos + size]
        pos += size + 1
        if otype == "blob":
            blobs[sha] = body
    return blobs


# ── 检查执行 ────────────────────────────────────────────────────────────

def scan(findings, sha_to_path, blobs, keys, mode_label):
    for sha, path in sha_to_path.items():
        for name, rx in FORBIDDEN:
            if rx.search(path):
                findings.append("%s → 路径规则「%s」" % (path, name))
                break

    checked_text = 0
    for sha, body in blobs.items():
        path = sha_to_path.get(sha, sha[:12])
        if b"\0" in body[:8000]:            # 二进制：只查路径，不查内容
            continue
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            continue
        checked_text += 1
        lines = text.splitlines()
        for name, rx in COMPILED:
            for lineno, line in enumerate(lines, 1):
                if rx.search(line):
                    findings.append("%s:%d → 密钥形态「%s」" % (path, lineno, name))
                    break
        for value in keys:
            for lineno, line in enumerate(lines, 1):
                if value in line:
                    findings.append("%s:%d → 本机真实密钥（值已隐去）" % (path, lineno))
                    break
    print("[check_no_secrets] 检查范围：%s；对象 %d 个（文本 %d）。"
          % (mode_label, len(sha_to_path), checked_text))


def main():
    ap = argparse.ArgumentParser(description="密钥门禁：密钥不进 git、不上 GitHub")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="检查 git 索引")
    group.add_argument("--head", action="store_true", help="检查 HEAD 树")
    group.add_argument("--all", action="store_true", help="检查全部历史")
    group.add_argument("--range", metavar="A..B|SHA", help="检查提交范围")
    args = ap.parse_args()

    if git("rev-parse", "--git-dir").returncode != 0:
        sys.stderr.write("[check_no_secrets] 不在 git 仓库里，跳过。\n")
        return 0

    findings = []
    if args.staged:
        sha_to_path, label = objects_staged(), "git 索引"
    elif args.all:
        sha_to_path, label = objects_revs(["--all"]), "全部历史"
    elif args.range:
        revs = git("rev-list", args.range).stdout.split() or [args.range]
        sha_to_path, label = objects_revs(revs), "提交范围 %s" % args.range
    else:
        sha_to_path, label = objects_head(), "HEAD 树"

    if len(sha_to_path) > MAX_OBJECTS:
        sha_to_path = dict(list(sha_to_path.items())[:MAX_OBJECTS])

    # 1) 路径规则（含历史上添加过、后来删掉的路径）
    for path in history_names():
        for name, rx in FORBIDDEN:
            if rx.search(path):
                findings.append("%s → 路径规则「%s」（历史）" % (path, name))
                break

    # 2) + 3) 内容
    keys = known_keys()
    if not keys:
        print("[check_no_secrets] 本机未发现已填密钥（零 key 状态），跳过真值比对。")
    blobs = batch_contents(list(sha_to_path.keys()))
    scan(findings, sha_to_path, blobs, keys, label)

    if findings:
        print("[check_no_secrets] ✗ 拦截：命中 %d 处，禁止提交/推送。" % len(findings))
        for item in sorted(set(findings))[:40]:
            print("    " + item)
        print("    （命中内容一律不回显；请把密钥放进 .env 或设置页，并从索引/提交里移除。）")
        return 1

    print("[check_no_secrets] ✓ 通过：未发现密钥、私钥或运行数据。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
