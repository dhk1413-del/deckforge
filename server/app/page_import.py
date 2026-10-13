# -*- coding: utf-8 -*-
"""图片转可编辑（首页模式②）第 1 段：把任意来源渲染成「每页一张图」。

支持：
  `.pdf`                  → PyMuPDF 逐页渲染
  `.png/.jpg/.jpeg/.webp` → 一张 = 一页（多张按传入顺序拼接）
  `.pptx`                 → 复用原稿缩略图链路的 PDF 缓存（LibreOffice 只转一次），再逐页渲染

产物：`data/files/<pid>/pages/pNN.png`（宽 1600，保持原比例）+ `pages.json` 状态。
把结果登记成 slides 行之后（见 `register_slides`），既有两条流水线可直接复用：
  · 「导出图片版」读 `slides.image_path`；
  · 「⑥ 转可编辑」以该页图为视觉基准做视觉识别 + 原生重建（绝不嵌整页图）。

缓存口径与 `source_pages` 对齐：原稿指纹变了才重渲；**状态与文件不一致即判定不可用**
（教训：只信状态位会让坏缓存永不重建）。
"""
import json
import os
import shutil
import threading
from datetime import datetime
from typing import Any, Dict, List

from . import config, db, source_pages

PAGE_WIDTH = 1600
STATUS_FILE = "pages.json"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

_guard = threading.Lock()
_cache_locks: Dict[str, threading.Lock] = {}


def _project_dir(pid: str) -> str:
    return os.path.join(config.FILES_DIR, pid)


def _pages_dir(pid: str) -> str:
    return os.path.join(_project_dir(pid), "pages")


def _status_path(pid: str) -> str:
    return os.path.join(_project_dir(pid), STATUS_FILE)


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


def _source_info(path: str) -> Dict[str, Any]:
    """用于缓存校验的来源标识（名/大小/纳秒 mtime）。"""
    stat = os.stat(path)
    return dict(name=os.path.basename(path), size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def page_image(pid: str, page_no: int) -> str:
    return os.path.join(_pages_dir(pid), "p%02d.png" % int(page_no))


def files_intact(pid: str, pages: List[Dict[str, Any]]) -> bool:
    return bool(pages) and all(os.path.isfile(page_image(pid, p["page_no"])) for p in pages)


def cache_usable(pid: str, status: Dict[str, Any], fingerprint: List[Dict[str, Any]]) -> bool:
    """状态 ready + 页图真的都在 + 来源指纹一致，三者缺一不可。"""
    if not status.get("ready") or not files_intact(pid, status.get("pages") or []):
        return False
    return status.get("source") == fingerprint


def _render_pdf(pdf_path: str, out_dir: str, start: int, width: int = PAGE_WIDTH) -> List[Dict[str, int]]:
    import fitz

    doc = fitz.open(pdf_path)
    try:
        out: List[Dict[str, int]] = []
        for index in range(doc.page_count):
            page = doc[index]
            zoom = float(width) / float(page.rect.width or 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            page_no = start + index
            pix.save(os.path.join(out_dir, "p%02d.png" % page_no))
            out.append(dict(page_no=page_no, width=pix.width, height=pix.height))
        return out
    finally:
        doc.close()


def _render_image(path: str, out_dir: str, page_no: int, width: int = PAGE_WIDTH) -> List[Dict[str, int]]:
    from PIL import Image

    with Image.open(path) as raw:
        image = raw.convert("RGB")
        if image.width != width:
            image = image.resize((width, max(1, round(image.height * width / image.width))), Image.LANCZOS)
        image.save(os.path.join(out_dir, "p%02d.png" % page_no), "PNG")
        return [dict(page_no=page_no, width=image.width, height=image.height)]


def render_pages(pid: str, paths: List[str], width: int = PAGE_WIDTH) -> Dict[str, Any]:
    """把 1..N 个来源渲染成每页一张 PNG；同一批来源重复调用命中缓存。"""
    paths = [p for p in (paths or []) if p and os.path.isfile(p)]
    if not paths:
        raise ValueError("没有可用的原稿文件")
    fingerprint = [_source_info(p) for p in paths]
    with _lock_for(pid):
        old = _read_status(pid)
        if cache_usable(pid, old, fingerprint):
            return old

        out_dir = _pages_dir(pid)
        shutil.rmtree(out_dir, ignore_errors=True)          # 来源变了：旧页图全部作废
        os.makedirs(out_dir, exist_ok=True)
        pages: List[Dict[str, int]] = []
        renderer: List[str] = []
        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".pptx":
                pages += _render_pdf(source_pages.ensure_pdf(pid, path), out_dir, len(pages) + 1, width)
                renderer.append("LibreOffice→PyMuPDF")
            elif ext == ".pdf":
                pages += _render_pdf(path, out_dir, len(pages) + 1, width)
                renderer.append("PyMuPDF")
            elif ext in IMAGE_EXTS:
                pages += _render_image(path, out_dir, len(pages) + 1, width)
                renderer.append("Pillow")
            else:
                raise ValueError("不支持的原稿格式：%s（支持 PDF / 图片 / PPTX）" % (ext or "无后缀"))

        result: Dict[str, Any] = dict(ready=True, page_count=len(pages), pages=pages, source=fingerprint,
                                      renderer="+".join(dict.fromkeys(renderer)), generated_at=_now())
        _write_status(pid, result)
        return result


def register_slides(pid: str, status: Dict[str, Any]) -> int:
    """把原页登记成 slides 行（`image_path` 指向原页图），使既有流水线可直接复用。

    幂等：同一页已存在时只补图片与尺寸，**保留已转可编辑的成果**
    （`editable` / `native_scene_json` / `native_status` 不动）。
    """
    written = 0
    for page in status.get("pages") or []:
        page_no = int(page["page_no"])
        data = dict(source_page_no=page_no, display_order=page_no, image_path=page_image(pid, page_no), width=int(page.get("width") or 0),
                    height=int(page.get("height") or 0), status="done", provider="import",
                    model="原页导入", size="原比例")
        row = db.q1("SELECT id FROM slides WHERE project_id=? AND page_no=?", (pid, page_no))
        if row:
            db.update("slides", row["id"], data)
        else:
            db.insert("slides", dict(id=db.uid("s"), project_id=pid, page_no=page_no,
                                     title="原稿 P%02d" % page_no, role="content", layout="cards_4",
                                     outline="", points_json="[]", must_keep_json="[]", keep=1,
                                     editable=0, native_status="pending", native_object_count=0,
                                     native_warnings_json="[]", created_at=db.now(), updated_at=db.now(),
                                     **data))
        written += 1
    return written


def response(pid: str) -> Dict[str, Any]:
    """对外状态：页图不齐时不得宣称 ready（前端据此如实降级）。"""
    raw = _read_status(pid)
    pages = [p for p in (raw.get("pages") or []) if isinstance(p, dict) and p.get("page_no")]
    intact = files_intact(pid, pages)
    return dict(ready=bool(raw.get("ready")) and intact, page_count=len(pages) if intact else 0,
                renderer=raw.get("renderer", ""), generated_at=raw.get("generated_at", ""),
                pages=[dict(page_no=int(p["page_no"]), width=int(p.get("width") or 0),
                            height=int(p.get("height") or 0)) for p in pages] if intact else [])


def clear(pid: str) -> None:
    shutil.rmtree(_pages_dir(pid), ignore_errors=True)
    try:
        os.unlink(_status_path(pid))
    except FileNotFoundError:
        pass
