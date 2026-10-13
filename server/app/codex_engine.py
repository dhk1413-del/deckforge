"""Codex CLI boundary; probing never starts a model task."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.parse import urlparse

from . import config, db


def binary() -> str:
    candidate = os.environ.get('CODEX_BIN')
    if candidate is not None:
        return shutil.which(candidate) or ''
    return shutil.which('codex') or ''


def proxy_url() -> str:
    candidates = [db.setting_get('codex:proxy_url', ''), config.http_proxy_url()]
    candidates += [f'http://127.0.0.1:{port}' for port in (65532, 7897, 1080, 7890)]
    for candidate in dict.fromkeys(candidates):
        try:
            parsed = urlparse(candidate)
            if not parsed.hostname:
                continue
            with socket.create_connection((parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)), timeout=1):
                return candidate
        except (OSError, ValueError):
            continue
    return ''


def available() -> dict:
    exe = binary()
    result = dict(ok=False, binary=exe, version='', proxy='', reason='未找到 Codex CLI')
    if not exe:
        return result
    try:
        proc = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=10)
        result.update(ok=proc.returncode == 0, version=proc.stdout.strip(),
                      proxy=proxy_url(), reason='' if proc.returncode == 0 else proc.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as exc:
        result['reason'] = str(exc)
    return result


def run(prompt: str, workdir: str, images: list[str] | None = None,
        timeout: int = 900, model: str | None = None) -> dict:
    start = time.monotonic()
    exe = binary()
    result = dict(ok=False, code=-1, stdout='', stderr='', seconds=0, cmd=[], artifacts=[])
    if not exe:
        return dict(result, reason='未找到 Codex CLI')
    root = Path(workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    before = {p.resolve() for p in root.rglob('*') if p.is_file()}
    cmd = [exe, 'exec', '--skip-git-repo-check', '--sandbox', 'workspace-write', '-C', str(root)]
    if model:
        cmd += ['--model', model]
    cmd += (['-i', *images] if images else []) + ['--', prompt]
    env = os.environ.copy()
    proxy = proxy_url()
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
        env.pop(key, None)
    if proxy:
        env.update(HTTPS_PROXY=proxy, HTTP_PROXY=proxy)
    env.update(NO_PROXY='127.0.0.1,localhost')
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(root))
        result.update(ok=proc.returncode == 0, code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    except subprocess.TimeoutExpired:
        result.update(reason='timeout', stderr='Codex 转换超时')
    except OSError as exc:
        result.update(reason=str(exc), stderr=str(exc))
    result.update(cmd=cmd, seconds=round(time.monotonic() - start, 3),
                  artifacts=[str(p) for p in root.rglob('*') if p.is_file() and p.resolve() not in before])
    return result
