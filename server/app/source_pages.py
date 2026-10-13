# -*- coding: utf-8 -*-
"""上传原稿的 PPTX 页缩略图。

这是纯辅助预览能力：任何失败都只写入状态文件，绝不影响原稿解析或后续生成。
缩略图、转换后的 PDF 与大图均落在项目目录。它们以原稿指纹共同失效，避免
每次点开原页都重新启动 LibreOffice。
"""
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict, List

from . import config

SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/local/bin/soffice",
    "/opt/homebrew/bin/soffice",
]
THUMB_WIDTH = 420
LARGE_WIDTH = 1100
RENDER_TIMEOUT = 900
STATUS_FILE = "source_pages.json"

_running: set = set()
_guard = threading.Lock()
_cache_locks: Dict[str, threading.Lock] = {}


def _project_dir(pid: str) -> str:
    return os.path.join(config.FILES_DIR, pid)


def _pages_dir(pid: str) -> str:
    return os.path.join(_project_dir(pid), "source-pages")


def _status_path(pid: str) -> str:
    return os.path.join(_project_dir(pid), STATUS_FILE)


def _pdf_path(pid: str) -> str:
    return os.path.join(_pages_dir(pid), "source.pdf")


def _source_info(pptx_path: str) -> Dict[str, Any]:
    """用于缓存校验的原稿标识；文件更新后绝不可复用旧的 PDF/PNG。"""
    stat = os.stat(pptx_path)
    return dict(name=os.path.basename(pptx_path), size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def _same_source(status: Dict[str, Any], pptx_path: str) -> bool:
    try:
        return status.get("source") == _source_info(pptx_path)
    except OSError:
        return False


def _lock_for(pid: str) -> threading.Lock:
    with _guard:
        return _cache_locks.setdefault(pid, threading.Lock())


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_status(pid: str) -> Dict[str, Any]:
    try:
        with open(_status_path(pid), encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_status(pid: str, data: Dict[str, Any]) -> None:
    os.makedirs(_project_dir(pid), exist_ok=True)
    target = _status_path(pid)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, target)


def find_soffice() -> str:
    configured = os.environ.get("DECKFORGE_SOFFICE", "")
    if configured and os.path.exists(configured):
        return configured
    for path in SOFFICE_CANDIDATES:
        if os.path.exists(path):
            return path
    found = shutil.which("soffice")
    if found:
        return found
    raise RuntimeError("未找到 LibreOffice")


def _pdf_from_pptx(pptx_path: str) -> tuple:
    """转换到临时 PDF，调用方负责清理返回的临时目录。"""
    soffice = find_soffice()
    tmp = tempfile.mkdtemp(prefix="deckforge_source_pages_")
    profile = tempfile.mkdtemp(prefix="deckforge_lo_profile_")
    cmd = [soffice, "--headless", "--norestore", "--nologo", "--nolockcheck",
           "-env:UserInstallation=file://%s" % profile,
           "--convert-to", "pdf", "--outdir", tmp, pptx_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT)
        pdfs = [name for name in os.listdir(tmp) if name.lower().endswith(".pdf")]
        if not pdfs:
            detail = (proc.stderr or proc.stdout or "").strip()[:300]
            raise RuntimeError("LibreOffice 未产出 PDF%s" % ("：" + detail if detail else ""))
        return os.path.join(tmp, pdfs[0]), tmp, profile, os.path.basename(soffice)
    except Exception:
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def _ensure_pdf(pid: str, pptx_path: str, status: Dict[str, Any]) -> tuple:
    """返回与当前原稿匹配的项目内 PDF。调用者必须持有项目缓存锁。"""
    source = _source_info(pptx_path)
    cached = _pdf_path(pid)
    if status.get("source") == source and os.path.isfile(cached):
        return cached, source, status

    # 指纹不同意味着所有派生物都不可信；先删掉再原子替换新的 PDF。
    shutil.rmtree(_pages_dir(pid), ignore_errors=True)
    os.makedirs(_pages_dir(pid), exist_ok=True)
    pdf_path = tmp = profile = None
    try:
        pdf_path, tmp, profile, converter = _pdf_from_pptx(pptx_path)
        pending = cached + ".tmp"
        shutil.copyfile(pdf_path, pending)
        os.replace(pending, cached)
        # 旧缩略图和大图已被删掉，状态也必须同步清空；否则原稿被就地替换时会把
        # 已不存在的旧缩略图 URL 当成 ready 返回。
        next_status = dict(status, page_count=0, ready=False, pages=[], source=source,
                           converter="LibreOffice/%s + PyMuPDF" % converter, pdf_generated_at=_now())
        _write_status(pid, next_status)
        return cached, source, next_status
    finally:
        if profile:
            shutil.rmtree(profile, ignore_errors=True)
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _pages_meta(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_pages = raw.get("pages")
    pages: List[Any] = raw_pages if isinstance(raw_pages, list) else []
    return [p for p in pages if isinstance(p, dict) and p.get("page_no")]


def _thumbs_exist(pid: str, pages: List[Dict[str, Any]]) -> bool:
    """缩略图文件是否真的都在磁盘上（只看文件，不看状态）。"""
    if not pages:
        return False
    return all(os.path.isfile(os.path.join(_pages_dir(pid), "p%02d.png" % int(p["page_no"]))) for p in pages)


def _cache_usable(pid: str, old: Dict[str, Any], pptx_path: str) -> bool:
    """缓存能否复用：状态 ready + **缩略图文件真的都在** + 原稿未变。

    三者缺一不可。历史 bug：`start()` 只看了 `ready + pages` 两个状态位，
    于是"状态说 ready、缩略图却被删/写坏"的项目**永远不会重建**，界面一直给 404 碎图。
    """
    if not old.get("ready") or not _thumbs_exist(pid, _pages_meta(old)):
        return False
    return not (os.path.isfile(pptx_path) and not _same_source(old, pptx_path))


def ensure_pdf(pid: str, pptx_path: str) -> str:
    """对外：返回与当前原稿指纹匹配的项目内 PDF（必要时用 LibreOffice 转一次并缓存）。

    供「图片转可编辑」复用：PPTX 只需转换一次，缩略图、大图与逐页高清图共用这份 PDF。
    """
    if not pptx_path.lower().endswith(".pptx"):
        raise ValueError("原稿不是可用的 PPTX")
    with _lock_for(pid):
        return _ensure_pdf(pid, pptx_path, _read_status(pid))[0]


def build_pages(pid: str, pptx_path: str, width: int = THUMB_WIDTH) -> Dict[str, Any]:
    """同步构建缩略图；供后台任务和离线测试调用。已有完整缓存时不重转。"""
    if not pptx_path.lower().endswith(".pptx"):
        raise ValueError("原稿不是可用的 PPTX")
    with _lock_for(pid):
        old = _read_status(pid)
        # 兼容早期只存缩略图的缓存：原稿已不存在时只能保留已有预览；正常路径一定校验指纹。
        if _cache_usable(pid, old, pptx_path):
            return old
        if not os.path.isfile(pptx_path):
            raise ValueError("原稿不是可用的 PPTX")

        pdf_path, source, cached_status = _ensure_pdf(pid, pptx_path, old)
        import fitz
        os.makedirs(_pages_dir(pid), exist_ok=True)
        doc = fitz.open(pdf_path)
        pages: List[Dict[str, int]] = []
        for index in range(doc.page_count):
            page = doc[index]
            zoom = float(width) / float(page.rect.width or 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            file_name = "p%02d.png" % (index + 1)
            pix.save(os.path.join(_pages_dir(pid), file_name))
            pages.append(dict(page_no=index + 1, width=pix.width, height=pix.height))
        doc.close()
        result: Dict[str, Any] = dict(cached_status, page_count=len(pages), ready=True, generating=False, pages=pages,
                                      source=source, generated_at=_now())
        _write_status(pid, result)
        return result


def is_running(pid: str) -> bool:
    """该项目是否有后台缩略图构建在跑（删除项目前必须问一次）。

    构建线程会往 `data/files/<pid>/source-pages/` 写文件；若项目中途被删除，
    线程会把刚删掉的目录重建出来，留下一个"没有项目记录的孤儿目录"。
    """
    with _guard:
        return pid in _running


def start(pid: str, pptx_path: str) -> bool:
    """登记一次后台构建。True 表示调用方应创建 task；缓存/进行中则 False。"""
    with _guard:
        old = _read_status(pid)
        # 必须与 build_pages 用同一套判断：只信状态位会导致缓存坏了永不重建。
        if pid in _running or _cache_usable(pid, old, pptx_path):
            return False
        _running.add(pid)
        _write_status(pid, dict(page_count=0, ready=False, generating=True, pages=[], started_at=_now()))
        return True


async def build_background(pid: str, pptx_path: str) -> None:
    try:
        await asyncio.to_thread(build_pages, pid, pptx_path)
    except Exception as exc:  # 预览降级，不能让上传/生成失败
        _write_status(pid, dict(page_count=0, ready=False, generating=False, pages=[], error=str(exc), failed_at=_now()))
    finally:
        with _guard:
            _running.discard(pid)


def response(pid: str) -> Dict[str, Any]:
    raw = _read_status(pid)
    pages = _pages_meta(raw)
    # 缩略图文件不齐时**不能**对外宣称 ready，否则前端拿到一群 404 碎图；
    # 同时给出可读原因，界面会显示「不可用」，而 build 接口会因缓存不可用而重建。
    intact = _thumbs_exist(pid, pages)
    ready = bool(raw.get("ready")) and intact
    error = raw.get("error") or ("" if ready or not raw.get("ready") else "缩略图缓存不完整，点「重新生成」可修复")
    return dict(page_count=int(raw.get("page_count") or len(pages)), ready=ready,
                generating=bool(raw.get("generating")), pages=[
                    dict(page_no=int(page["page_no"]),
                         thumb_url="/files/%s/source-pages/p%02d.png" % (pid, int(page["page_no"])),
                         width=int(page.get("width") or 0), height=int(page.get("height") or 0))
                    for page in pages
                ], error=error)


def clear(pid: str) -> None:
    """仅新上传 PPTX 时清掉同项目旧原稿预览缓存。"""
    shutil.rmtree(_pages_dir(pid), ignore_errors=True)
    try:
        os.unlink(_status_path(pid))
    except FileNotFoundError:
        pass


def large_page_png(pptx_path: str, page_no: int, width: int = LARGE_WIDTH) -> bytes:
    """从共用 PDF 生成并缓存一张大图；同页二次访问只读磁盘。"""
    if page_no < 1:
        raise ValueError("页码必须从 1 开始")
    pid = os.path.basename(os.path.dirname(pptx_path))
    with _lock_for(pid):
        status = _read_status(pid)
        if not os.path.isfile(pptx_path):
            raise ValueError("原稿不是可用的 PPTX")
        pdf_path, _source, _status = _ensure_pdf(pid, pptx_path, status)
        large_path = os.path.join(_pages_dir(pid), "large-p%02d.png" % page_no)
        if os.path.isfile(large_path):
            with open(large_path, "rb") as f:
                return f.read()
        import fitz
        doc = fitz.open(pdf_path)
        try:
            if page_no > doc.page_count:
                raise ValueError("原稿页不存在")
            page = doc[page_no - 1]
            zoom = float(width) / float(page.rect.width or 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            data = pix.tobytes("png")
            pending = large_path + ".tmp"
            with open(pending, "wb") as f:
                f.write(data)
            os.replace(pending, large_path)
            return data
        finally:
            doc.close()


def render_generated_page(pptx_path: str, width: int = 2048) -> bytes:
    """Render a generated one-page native deck without touching original-page caches."""
    pdf_path, tmp, profile, _converter = _pdf_from_pptx(pptx_path)
    try:
        import fitz
        with fitz.open(pdf_path) as doc:
            if doc.page_count != 1:
                raise ValueError("原生图表渲染必须只有一页")
            page = doc[0]
            zoom = width / page.rect.width
            return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
