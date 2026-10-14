# -*- coding: utf-8 -*-
"""风格构建（Style Builder）：上传 pptx / 图片 → 实测设计基因 → 落成一套新风格包。

链路：upload（落盘 + 代表页 PNG）→ analyze（证据提取 + 定性描述 + 令牌合成）→ save（写盘）。

铁律（本模块的设计前提，违反即返工）：
  1. **色值只能来自证据**。pptx 优先读 `ppt/theme/theme*.xml` 的 `<a:clrScheme>`/`<a:fontScheme>`，
     再以渲染页像素统计（HSV 分桶 + 3×3 分格）交叉复核；图片输入只有像素统计这一路证据。
     代码里**没有任何一处**把 LLM 输出的颜色/字号写进令牌——视觉模型返回的颜色值会被主动抹掉。
  2. LLM（DeepSeek）只负责写文字（prose 段落 / prompt.md 正文）；yaml 令牌由代码生成。
     LLM 或视觉模型不可用 → 降级为「模板化文字 + 实测数据填充」，绝不失败。
  3. prompt.md ≤ 1500 字符（render.assemble_prompt 只取前 1500）。
  4. 落盘分两步：analyze 只返回结果供界面预览，save 才写入 style-packs/（不产生垃圾包）。
  5. 任何降级/缺失都进 warnings，不假装可用。
"""
import asyncio
import base64
import io
import json
import os
import re
import shutil
import uuid
import zipfile
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image

from . import config, db, pipeline, providers, source_pages, stylepacks

# ────────────────────────── 常量 ──────────────────────────

BUILDER_ROOT = os.path.join(config.FILES_DIR, "style-builder")
STATE_FILE = "builder.json"
PPTX_EXT = (".pptx",)
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
PDF_EXT = (".pdf",)
SUPPORTED_EXT = PPTX_EXT + PDF_EXT + IMAGE_EXT

PROMPT_LIMIT = 1500               # render.assemble_prompt 只取前 1500 字符（硬约束）
RENDER_WIDTH = 900                # 代表页 PNG 宽度（够清晰，又不至于让 90 页渲染过慢）
STATS_WIDTH = 220                 # 像素统计用缩略图宽度（HSV 分桶足够）
IMAGE_MAX_WIDTH = 1400            # 图片输入归一化后的最大宽度
MAX_STATS_PAGES = 24              # 像素统计最多抽样多少页（大文件不至于久等）
PREVIEW_MIN, PREVIEW_MAX = 3, 6   # 落盘的代表页张数区间
VISION_MAX_PAGES = 5              # 定性描述最多几页
THEME_RE = re.compile(r"^ppt/theme/theme\d+\.xml$")
SLIDE_XML_RE = re.compile(r"^ppt/slides/slide\d+\.xml$")
SLOT_RE = re.compile(r"<a:(dk1|lt1|dk2|lt2|accent[1-6]|hlink|folHlink)>\s*"
                     r"(?:<a:srgbClr val=\"([0-9A-Fa-f]{6})\"|<a:sysClr[^>]*lastClr=\"([0-9A-Fa-f]{6})\")")
FACETYPE_RE = re.compile(r"<(?:a:)?(latin|ea)\s+typeface=\"([^\"]+)\"")

# 颜色 → 中文/英文色名（只用于**命名**，不用于取值；取值一律来自实测）
_HUE_WORDS = [(15, "red", "红"), (45, "orange", "橙"), (70, "yellow", "黄"), (105, "green", "绿"),
              (160, "teal", "青绿"), (200, "cyan", "天青"), (250, "blue", "蓝"), (290, "purple", "紫"),
              (330, "magenta", "品红"), (361, "red", "红")]
NEUTRAL_WORDS = (("ink", "近黑", "ink"), ("slate", "灰蓝", "slate"), ("gray", "灰", "gray"),
                 ("warm", "暖灰", "warm-gray"))

NEGATIVE_WORDS = ("watermark, logo, page number, signature, extra decorative English text, lorem ipsum, "
                  "glassmorphism, neon glow, heavy gradient overlay, oversaturated colors, cluttered collage, "
                  "distorted text, corrupted characters, cropped text, 3D skeuomorphic icons")

VISION_STYLE_PROMPT = """看这张 16:9 PPT 页面的渲染图，只做**定性**描述，输出严格 JSON（不要 Markdown、不要解释）：
{"layout":"版式结构（分栏/栅格/环绕/上下分层等）",
"graphic_language":"图形语言（直角/圆角/圆形/胶囊/线条/渐变/图标风格）",
"hierarchy":"层级与留白（标题与正文字号关系、信息密度、页边距观感）",
"mood":"整体气质（3~6 个词）",
"elements":["版式元素清单"],
"donts":["这一页刻意避免的做法"]}
**禁止输出任何颜色值、字号数值、字体名**——颜色与字号由代码实测，你只需描述结构与气质。"""

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ────────────────────────── 路径与状态 ──────────────────────────

def _builder_dir(bid: str) -> str:
    return os.path.join(BUILDER_ROOT, bid)


def _pages_dir(bid: str) -> str:
    return os.path.join(_builder_dir(bid), "source-pages")


def _state_path(bid: str) -> str:
    return os.path.join(_builder_dir(bid), STATE_FILE)


def _pages_pid(bid: str) -> str:
    """交给 source_pages 的 pid：`style-builder/<bid>`（它只把 pid 当 FILES_DIR 下的一段路径）。

    好处：PDF/PNG 缓存正好落在 `<builder_dir>/source-pages/`，与图片输入共用同一目录与同一套读取逻辑。
    """
    return "style-builder/%s" % bid


def _read_state(bid: str) -> Dict[str, Any]:
    try:
        with io.open(_state_path(bid), encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _normalize_state(data: Dict[str, Any]) -> bool:
    """统一持久化/响应出口：警告保留首次出现顺序，清理不适用的空证据。"""
    result = data.get("result") or {}
    warnings = list(data.get("warnings") or []) + list(result.get("warnings") or [])
    changed = False
    if data.get("kind") in ("pdf", "image"):
        evidence = result.get("evidence") or {}
        for key in ("theme", "structure"):
            if key not in evidence:
                continue
            value = evidence[key]
            # 兼容旧 theme 占位：file/name 为空字符串，slots/fonts 为空字典。
            if not value or (isinstance(value, dict) and not any(value.values())):
                del evidence[key]
                changed = True
            else:
                source = value.get("source") if isinstance(value, dict) else None
                warnings.append("%s 输入：保留已有 %s 证据，来源：%s" %
                                (data["kind"].upper(), key, source or "已有保存证据（未标注来源）"))
    warnings = list(dict.fromkeys(warnings))
    if data.get("warnings") != warnings:
        if isinstance(data.get("warnings"), list):
            data["warnings"][:] = warnings  # 上传返回值也引用这份列表。
        else:
            data["warnings"] = warnings
        changed = True
    if result and result.get("warnings") != warnings:
        result["warnings"] = warnings
        changed = True
    return changed


def _write_state(bid: str, data: Dict[str, Any]) -> None:
    """原子写状态文件。

    坑（已修）：曾经共用固定的 `<bid>.json.tmp` 名 —— 上传后 `build_pages_background` 与解析作业
    天然并发，两个写入者会互相把对方的 tmp 改走，于是 `os.replace` 抛
    `FileNotFoundError: ... .tmp -> ...`（真机实测踩到：90 页模板解析到“准备代表页”阶段整单失败）。
    现在每个写入者用各自唯一的 tmp 名，并容错重试一次。
    """
    _normalize_state(data)
    os.makedirs(_builder_dir(bid), exist_ok=True)
    target = _state_path(bid)
    tmp = "%s.%d-%s.tmp" % (target, os.getpid(), uuid.uuid4().hex[:8])
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    for attempt in (1, 2):
        try:
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, target)
            return
        except FileNotFoundError:                     # 目录/临时文件被并发清理
            if attempt == 2:
                raise
            os.makedirs(_builder_dir(bid), exist_ok=True)


def _pptx_path(state: Dict[str, Any]) -> str:
    for item in state.get("files") or []:
        path = item.get("path") or ""
        if path.lower().endswith(".pptx") and os.path.isfile(path):
            return path
    return ""


def page_images(bid: str) -> List[Tuple[int, str]]:
    """代表页 PNG（两种输入统一落在 `<builder_dir>/source-pages/pNN.png`）。返回 [(page_no, path)]。"""
    d = _pages_dir(bid)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        m = re.match(r"^p(\d{2,3})\.png$", name)
        if m:
            out.append((int(m.group(1)), os.path.join(d, name)))
    return out


def page_count(bid: str) -> int:
    return len(page_images(bid))


# ────────────────────────── 颜色/对比度工具（纯代码，不依赖模型） ──────────────────────────

def hex_to_rgb(hex6: str) -> Tuple[int, int, int]:
    h = (hex6 or "").lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % (max(0, min(255, int(rgb[0]))), max(0, min(255, int(rgb[1]))), max(0, min(255, int(rgb[2]))))


def _hsv(hex6: str) -> Tuple[float, float, float]:
    r, g, b = hex_to_rgb(hex6)
    return _hsv_rgb(r, g, b)


def _hsv_rgb(r: int, g: int, b: int) -> Tuple[float, float, float]:
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    v = mx / 255.0
    s = 0.0 if mx == 0 else d / float(mx)
    if d == 0:
        h = 0.0
    elif mx == r:
        h = (60.0 * ((g - b) / float(d))) % 360.0
    elif mx == g:
        h = 60.0 * ((b - r) / float(d)) + 120.0
    else:
        h = 60.0 * ((r - g) / float(d)) + 240.0
    return h, s, v


def _luma(hex6: str) -> float:
    r, g, b = [c / 255.0 for c in hex_to_rgb(hex6)]
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4      # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    la, lb = _luma(a), _luma(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _hue_dist(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _color_word(hex6: str) -> Tuple[str, str]:
    """按 HSV 给一个色值起**名字**（只命名，不取值）。返回 (英文, 中文)。"""
    h, s, v = _hsv(hex6)
    if s < 0.12:
        return NEUTRAL_WORDS[0][0] if v < 0.5 else NEUTRAL_WORDS[2][0], \
               (NEUTRAL_WORDS[0][1] if v < 0.5 else NEUTRAL_WORDS[2][1])
    for limit, en, cn in _HUE_WORDS:
        if h < limit:
            return en, cn
    return "color", "彩"


# ────────────────────────── 上传落盘 ──────────────────────────

def _normalize_images(bid: str, files: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """图片输入 → 统一转成 `<builder_dir>/source-pages/pNN.png`（RGB）。返回 (页数, 警告)。"""
    os.makedirs(_pages_dir(bid), exist_ok=True)
    warnings: List[str] = []
    n = 0
    for item in files:
        try:
            with Image.open(item["path"]) as im:
                im = im.convert("RGB")
                if im.width > IMAGE_MAX_WIDTH:
                    im = im.resize((IMAGE_MAX_WIDTH, max(1, round(im.height * IMAGE_MAX_WIDTH / im.width))))
                n += 1
                im.save(os.path.join(_pages_dir(bid), "p%02d.png" % n), "PNG")
        except Exception as exc:                       # noqa: BLE001
            warnings.append("图片无法读取，已跳过：%s（%s）" % (item.get("name"), str(exc)[:80]))
    return n, warnings


def save_uploads(pairs: List[Tuple[str, bytes]]) -> Dict[str, Any]:
    """落盘上传文件并建 builder。pairs = [(filename, raw_bytes)]。"""
    kept: List[Tuple[str, bytes, str]] = []
    warnings: List[str] = []
    for name, raw in pairs:
        ext = os.path.splitext(name or "")[1].lower()
        if not raw:
            continue
        if ext not in SUPPORTED_EXT:
            warnings.append("已忽略不支持的文件：%s（只支持 .pptx / .pdf / .png / .jpg / .jpeg / .webp）" % (name or "?"))
            continue
        kept.append((name or ("file%s" % ext), raw, ext))
    if not kept:
        raise ValueError("没有可用的文件（只支持 .pptx / .pdf / .png / .jpg / .jpeg / .webp）")

    kind = ("pptx" if any(ext in PPTX_EXT for _, _, ext in kept) else
            "pdf" if any(ext in PDF_EXT for _, _, ext in kept) else "image")
    if kind != "image":
        chosen = PPTX_EXT if kind == "pptx" else PDF_EXT
        dropped = [name for name, _, ext in kept if ext not in chosen]
        if dropped:
            warnings.append("同时上传了其他格式，本次只按 %s 解析：" % kind.upper() + "、".join(dropped[:3]))
        kept = [k for k in kept if k[2] in chosen]

    bid = db.uid("sb")
    dest = _builder_dir(bid)
    os.makedirs(dest, exist_ok=True)
    files: List[Dict[str, Any]] = []
    for index, (name, raw, ext) in enumerate(kept, 1):
        fname = ("source%s" % ext) if (kind in ("pptx", "pdf")) else ("img%02d%s" % (index, ext))
        path = os.path.join(dest, fname)
        with open(path, "wb") as f:
            f.write(raw)
        files.append(dict(name=name, size=len(raw), path=path))

    pages = 0
    if kind == "pdf":
        try:
            pages = _render_pdf(bid, files[0]["path"])
        except Exception as exc:
            shutil.rmtree(dest, ignore_errors=True)
            raise ValueError("PDF 无法读取或渲染：%s" % exc) from exc
        warnings.append("PDF 输入：拿不到 OOXML 主题色板与 fontScheme；字体方案尽力来自 PDF 嵌入字体名（可能不完整），提取不到时退化为通用档位；字号/几何只能定性")
    if kind == "image":
        pages, img_warn = _normalize_images(bid, files)
        warnings += img_warn
        if not pages:
            shutil.rmtree(dest, ignore_errors=True)
            raise ValueError("图片都无法读取，请换一张（支持 PNG/JPG/WEBP）")

    _write_state(bid, dict(builder_id=bid, kind=kind, status="uploaded", files=files, pages=pages,
                           previews=[], warnings=warnings, error="", created_at=_now()))
    return dict(builder_id=bid, kind=kind, files=[dict(name=f["name"], size=f["size"]) for f in files],
                pages=pages, warnings=warnings)


def _pdf_path(state: Dict[str, Any]) -> str:
    return next((f["path"] for f in state.get("files", [])
                 if f.get("path", "").lower().endswith(PDF_EXT) and os.path.isfile(f["path"])), "")


def _render_pdf(bid: str, path: str) -> int:
    """直接渲染 PDF；已存在的逐页 PNG 是缓存，不经 LibreOffice。"""
    import fitz

    os.makedirs(_pages_dir(bid), exist_ok=True)
    with fitz.open(path) as doc:
        if not doc.page_count:
            raise ValueError("PDF 没有页面")
        for index, page in enumerate(doc, 1):
            target = os.path.join(_pages_dir(bid), "p%02d.png" % index)
            if os.path.isfile(target):
                continue
            scale = RENDER_WIDTH / page.rect.width
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(target)
        return doc.page_count


def _pdf_fonts(path: str) -> Dict[str, Any]:
    """仅记录 PDF 中实际嵌入的字体名，不把内置字体当作嵌入证据。"""
    import fitz

    names = set()
    with fitz.open(path) as doc:
        for page in doc:
            for font in page.get_fonts():
                if font[0] and font[3] and doc.extract_font(font[0])[3]:
                    names.add(re.sub(r"^[A-Z]{6}\+", "", font[3]))
    return dict(source="pdf_embedded", names=sorted(names)) if names else {}


def start_pages(bid: str) -> bool:
    """pptx：登记一次后台代表页构建（复用 source_pages）。True 表示调用方应建 asyncio task。"""
    state = _read_state(bid)
    if state.get("kind") == "pdf":
        ensure_pages(bid)
        return False
    path = _pptx_path(state)
    if not path:
        return False
    return source_pages.start(_pages_pid(bid), path)


async def build_pages_background(bid: str) -> None:
    state = _read_state(bid)
    if state.get("kind") == "pdf":
        await asyncio.to_thread(ensure_pages, bid)
        return
    path = _pptx_path(state)
    if not path:
        return
    await source_pages.build_background(_pages_pid(bid), path)
    cur = _read_state(bid)
    if cur:
        _write_state(bid, dict(cur, pages=page_count(bid), pages_error=(source_pages.response(_pages_pid(bid)) or {}).get("error", "")))


def ensure_pages(bid: str) -> List[Tuple[int, str]]:
    """确保代表页 PNG 存在（阻塞，调用方自行丢线程）。返回 [(page_no, path)]。"""
    state = _read_state(bid)
    if not state:
        raise ValueError("上传记录不存在")
    if state.get("kind") == "pptx":
        path = _pptx_path(state)
        if not path:
            raise ValueError("PPTX 原文件不存在")
        source_pages.build_pages(_pages_pid(bid), path, width=RENDER_WIDTH)
    elif state.get("kind") == "pdf":
        path = _pdf_path(state)
        if not path:
            raise ValueError("PDF 原文件不存在")
        _render_pdf(bid, path)
    cur = _read_state(bid)
    images = page_images(bid)
    _write_state(bid, dict(cur, pages=len(images)))
    return images


# ────────────────────────── 证据①：pptx 主题 XML ──────────────────────────

def _theme_evidence(pptx_path: str) -> Dict[str, Any]:
    """读 ppt/theme/*.xml：clrScheme 全槽位 + fontScheme。多 theme 取并集（先到先得）。"""
    out: Dict[str, Any] = dict(file="", name="", slots={}, fonts={}, per_theme=[])
    try:
        with zipfile.ZipFile(pptx_path) as z:
            for name in sorted(z.namelist()):
                if not THEME_RE.match(name):
                    continue
                xml = z.read(name).decode("utf-8", "replace")
                slots: Dict[str, str] = {}
                for slot, srgb, sysc in SLOT_RE.findall(xml):
                    val = (srgb or sysc or "").upper()
                    if val and slot not in slots:
                        slots[slot] = "#" + val
                name_m = re.search(r'<a:clrScheme name="([^"]*)"', xml)
                fonts: Dict[str, str] = {}
                for block in ("majorFont", "minorFont"):
                    m = re.search(r"<a:%s>(.*?)</a:%s>" % (block, block), xml, re.S)
                    if not m:
                        continue
                    for kind, face in FACETYPE_RE.findall(m.group(1)):
                        if face.strip() and block not in fonts:
                            fonts[block] = face.strip()
                            break
                out["per_theme"].append(dict(file=name, name=(name_m.group(1) if name_m else ""),
                                             slots=slots, fonts=fonts))
                for k, v in slots.items():
                    out["slots"].setdefault(k, v)
                for k, v in fonts.items():
                    out["fonts"].setdefault(k, v)
                if not out["file"] and slots:
                    out["file"] = name
                    out["name"] = name_m.group(1) if name_m else ""
    except Exception as exc:                            # noqa: BLE001 —— 主题读不到就只靠像素证据
        out["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:120])
    return out


# ────────────────────────── 证据②：pptx 结构（字号/字体/几何/渐变/投影/边距） ──────────────────────────

def _structure_evidence(pptx_path: str) -> Dict[str, Any]:
    """扫 ppt/slides/*.xml：字号、字体、几何体、圆角、渐变、投影、页边距。只做统计，不改文件。"""
    sizes: Counter = Counter()
    faces: Counter = Counter()
    shapes: Counter = Counter()
    radii: Counter = Counter()
    lines: Counter = Counter()
    gradients = 0
    shadows = 0
    margins: List[float] = []
    slides = 0
    try:
        with zipfile.ZipFile(pptx_path) as z:
            slide_names = [n for n in z.namelist() if SLIDE_XML_RE.match(n)]
            for name in slide_names:
                xml = z.read(name).decode("utf-8", "replace")
                slides += 1
                for val in re.findall(r'<a:rPr[^>]*\bsz="(\d+)"', xml):
                    sizes[int(val)] += 1
                for face in re.findall(r'typeface="([^"+][^"]*)"', xml):
                    faces[face.strip()] += 1
                for prst in re.findall(r'<a:prstGeom prst="([^"]+)"', xml):
                    shapes[prst] += 1
                gradients += len(re.findall(r"<a:gradFill", xml))
                shadows += len(re.findall(r"<a:outerShdw", xml))
                for w in re.findall(r'<a:ln w="(\d+)"', xml):
                    lines[int(w)] += 1
                # 圆角：roundRect 的 adj（val/100000 × 短边）→ 像素（12192000 EMU = 13.333in = 2048px 基准）
                for m in re.finditer(r'<a:ext cx="(\d+)" cy="(\d+)"/>(?:(?!</p:sp>).)*?'
                                     r'<a:prstGeom prst="roundRect">\s*<a:avLst>\s*'
                                     r'<a:gd name="adj" fmla="val (\d+)"', xml, re.S):
                    cx, cy, adj = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    short = min(cx, cy)
                    if short <= 0:
                        continue
                    px = int(round(adj / 100000.0 * short / 12192000.0 * 2048))
                    radii[px] += 1
                # 页边距：取「非通栏形状」的最小左边界（通栏底图/色带不算边距）
                xs: List[int] = []
                for m in re.finditer(r'<a:off x="(-?\d+)" y="(-?\d+)"/><a:ext cx="(\d+)" cy="(\d+)"/>', xml):
                    x, cx = int(m.group(1)), int(m.group(3))
                    if x < 0 or cx >= 0.9 * 12192000:
                        continue
                    xs.append(x)
                if xs:
                    margins.append(min(xs) / 12192000.0)
    except Exception as exc:                            # noqa: BLE001
        return dict(error="%s: %s" % (type(exc).__name__, str(exc)[:120]))
    all_sizes = [pt for pt in sizes.elements()]
    top_sizes = [dict(pt=s, count=c) for s, c in sizes.most_common(12)]
    return dict(
        slides=slides,
        sizes_pt=top_sizes,
        size_max_pt=(max(all_sizes) if all_sizes else None),
        size_min_pt=(min(all_sizes) if all_sizes else None),
        fonts=[dict(name=n, count=c) for n, c in faces.most_common(8)],
        shapes=dict(shapes),
        corner_radius_px=[dict(px=p, count=c) for p, c in radii.most_common(12)],
        line_width_emu=[dict(emu=e, count=c) for e, c in lines.most_common(5)],
        gradients=gradients,
        shadows=shadows,
        page_margin_px=(int(round(sorted(margins)[len(margins) // 2] * 2048)) if margins else None),
        source="pptx/ppt/slides/*.xml",
    )


# ────────────────────────── 证据③：像素统计（HSV 分桶 + 3×3 分格） ──────────────────────────

def _page_stats(path: str, page_no: int) -> Dict[str, Any]:
    """单页像素统计：白底占比、浅色底材、饱和色（HSV 分桶 + 精确色众数）、3×3 分格。"""
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.width, im.height
        if w > STATS_WIDTH:
            im = im.resize((STATS_WIDTH, max(1, round(h * STATS_WIDTH / w))))
        w, h = im.width, im.height
        px = list(im.getdata())
    n = len(px)
    if not n:
        return dict(page_no=page_no, error="空图")
    white = 0
    light = 0
    sat_buckets: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
    cells: List[Counter] = [Counter() for _ in range(9)]
    cell_n: List[int] = [0] * 9
    light_exact: Counter = Counter()
    dark_buckets: Dict[Tuple[int, int, int], Counter] = {}
    mid_buckets: Dict[Tuple[int, int, int], Counter] = {}
    for idx, (r, g, b) in enumerate(px):
        bucket = (r >> 3, g >> 3, b >> 3)
        # 3×3 分格：用下标算所在行/列（w、h 已是统计宽度）
        row, col = (idx // max(1, w)) * 3 // max(1, h), (idx % max(1, w)) * 3 // max(1, w)
        cell = min(8, max(0, row * 3 + col))
        cells[cell][bucket] += 1
        cell_n[cell] += 1
        if min(r, g, b) >= 238:
            white += 1
        hh, ss, vv = _hsv_rgb(r, g, b)
        if vv >= 0.86 and ss <= 0.30:
            light += 1
            light_exact[(r, g, b)] += 1
        elif vv <= 0.28:
            dark_buckets.setdefault(bucket, Counter())[(r, g, b)] += 1
        elif 0.18 <= vv <= 0.72 and ss <= 0.25:
            mid_buckets.setdefault(bucket, Counter())[(r, g, b)] += 1
        if ss >= 0.18 and vv >= 0.15:
            rec = sat_buckets.setdefault(bucket, dict(count=0, exact=Counter(), hue=0.0, s=0.0, v=0.0))
            rec["count"] += 1
            rec["exact"][(r, g, b)] += 1
            if not rec["hue"]:
                rec["hue"], rec["s"], rec["v"] = hh, ss, vv
    # 饱和色：桶内**精确色众数**（保证输出的是真实像素值，不是量化桶中心）
    sat = []
    for bucket, rec in sat_buckets.items():
        if rec["count"] / float(n) < 0.004:
            continue
        exact_rgb = rec["exact"].most_common(1)[0][0]
        sat.append(dict(hex=rgb_to_hex(exact_rgb), ratio=round(rec["count"] / float(n), 4),
                        hue=round(rec["hue"], 1), s=round(rec["s"], 3), v=round(rec["v"], 3),
                        cells=dict(("%d" % (i + 1), round(cells[i][bucket] / float(max(1, cell_n[i])), 4))
                                   for i in range(9))))
    sat.sort(key=lambda x: (-x["ratio"], -x["s"]))

    def tops(counter: Counter, limit: int, floor: float) -> List[Dict[str, Any]]:
        return [dict(hex=rgb_to_hex(rgb), ratio=round(cnt / float(n), 4))
                for rgb, cnt in counter.most_common(limit) if cnt / float(n) >= floor]

    def grouped_top(buckets: Dict[Tuple[int, int, int], Counter], limit: int,
                    floor: float) -> List[Dict[str, Any]]:
        """按量化桶聚「同类色」后取桶内精确色众数：抗锯齿会把同一文字色打散成很多近似色，
        只按精确色计数会一个都留不下；先分桶再取桶内众数，输出的仍是**真实出现过的像素值**。"""
        rows = []
        for bucket, counter in buckets.items():
            cnt = sum(counter.values())
            if cnt / float(n) < floor:
                continue
            rows.append(dict(hex=rgb_to_hex(counter.most_common(1)[0][0]), ratio=round(cnt / float(n), 4)))
        rows.sort(key=lambda x: -x["ratio"])
        return rows[:limit]

    return dict(page_no=page_no, width=w, height=h, white_ratio=round(white / float(n), 4),
                light_ratio=round(light / float(n), 4), saturated=sat[:10],
                light_top=tops(light_exact, 8, 0.008),
                dark_top=grouped_top(dark_buckets, 3, 0.002),
                mid_top=grouped_top(mid_buckets, 3, 0.0015))


def _pixel_evidence(pages: List[Tuple[int, str]]) -> Dict[str, Any]:
    """跨页聚合。返回 per_page 指标 + 全局色表（含出现页）。"""
    per_page: Dict[int, Dict[str, Any]] = {}
    color_acc: Dict[str, Dict[str, Any]] = {}
    light_acc: Dict[str, Dict[str, Any]] = {}
    mid_acc: Dict[str, Dict[str, Any]] = {}
    dark_acc: Dict[str, Dict[str, Any]] = {}
    for page_no, path in pages:
        try:
            st = _page_stats(path, page_no)
        except Exception as exc:                        # noqa: BLE001
            per_page[page_no] = dict(page_no=page_no, error="%s: %s" % (type(exc).__name__, str(exc)[:80]))
            continue
        per_page[page_no] = st
        for c in st.get("saturated") or []:
            rec = color_acc.setdefault(c["hex"], dict(count=0.0, pages=[], cells={}, hue=c["hue"],
                                                      peak=0.0, peak_page=page_no))
            rec["count"] += c["ratio"]
            rec["pages"].append(page_no)
            if c["ratio"] > rec["peak"]:
                rec["peak"], rec["peak_page"] = c["ratio"], page_no
            for k, v in (c.get("cells") or {}).items():
                rec["cells"]["%s:%d" % (k, page_no)] = v
        for key, acc in (("light_top", light_acc), ("mid_top", mid_acc), ("dark_top", dark_acc)):
            for c in st.get(key) or []:
                rec = acc.setdefault(c["hex"], dict(count=0.0, pages=[], peak=0.0))
                rec["count"] += c["ratio"]
                rec["peak"] = max(rec["peak"], c["ratio"])
                rec["pages"].append(page_no)
    return dict(sampled_pages=[p for p, _ in pages], per_page=per_page, colors=color_acc,
                lights=light_acc, mids=mid_acc, darks=dark_acc)


def _find_pixel_color(pixels: Dict[str, Any], hex6: str, tol: int = 22) -> Optional[Dict[str, Any]]:
    """在实测像素色里找与 hex6 最接近的一个（容差内）。找不到返回 None（**不编造**）。"""
    target = hex_to_rgb(hex6)
    best = None
    best_d = None
    for hx, rec in (pixels.get("colors") or {}).items():
        rgb = hex_to_rgb(hx)
        d = max(abs(rgb[i] - target[i]) for i in range(3))
        if d <= tol and (best_d is None or d < best_d):
            best, best_d = dict(hex=hx, **rec), d
    return best


def _pixel_note(rec: Dict[str, Any], page_count_total: int) -> str:
    """把像素证据写成人话（用于 evidence 的 note 字段，界面可直接展示）。"""
    pages = sorted(set(rec.get("pages") or []))
    cells: Dict[str, List[float]] = {}
    for key, val in (rec.get("cells") or {}).items():
        cell = key.split(":")[0]
        cells.setdefault(cell, []).append(val)
    avg = {k: sum(v) / len(v) for k, v in cells.items()}
    total_cell = sum(avg.values()) or 1.0
    bottom = avg.get("7", 0) + avg.get("8", 0) + avg.get("9", 0)
    top = avg.get("1", 0) + avg.get("2", 0) + avg.get("3", 0)
    where = ""
    if bottom / total_cell >= 0.55:
        where = "主要落在画面下 1/3 的贯通横带"
    elif top / total_cell >= 0.55:
        where = "主要落在画面上 1/3"
    elif len([c for c in avg.values() if c >= 0.2]) >= 3:
        where = "分散在多格（多模块色块）"
    return "出现在第 %s 页（共统计 %d 页），累计占比 %.1f%%%s" % (
        "/".join(str(p) for p in pages[:8]) or "-", page_count_total, rec["count"] * 100.0,
        ("，" + where) if where else "")


# ────────────────────────── 色板合成（全部来自上面的证据） ──────────────────────────

def _lighter(hex6: str, amount: float) -> str:
    r, g, b = hex_to_rgb(hex6)
    return rgb_to_hex((r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount))


def _darker(hex6: str, amount: float) -> str:
    r, g, b = hex_to_rgb(hex6)
    return rgb_to_hex((r * (1.0 - amount), g * (1.0 - amount), b * (1.0 - amount)))


def build_palette(theme: Dict[str, Any], pixels: Dict[str, Any], warnings: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """把证据合成实测色板。返回 (palette, colors_evidence)。

    palette 的每个值都带 source：`theme:<file>#<slot>` / `pixels:<hex>` / `derived:<依据>`。
    **绝不引入 LLM 颜色**；只有 textColor 用到的 #FFFFFF 属字面常量。
    """
    slots: Dict[str, str] = dict(theme.get("slots") or {})
    colors = pixels.get("colors") or {}
    lights = pixels.get("lights") or {}
    mids = pixels.get("mids") or {}
    total_pages = max(1, len(pixels.get("per_page") or {}))
    evidence: List[Dict[str, Any]] = []
    palette: Dict[str, Any] = {}
    sampled = len(pixels.get("sampled_pages") or [])

    def add(role: str, value: str, source: str, note: str = "", ratio: Optional[float] = None,
            pages: Optional[List[int]] = None, cells: Optional[Dict[str, float]] = None) -> None:
        palette[role] = value
        item = dict(role=role, value=value, source=source, note=note)
        if ratio is not None:
            item["pixel_ratio"] = round(ratio, 4)
        if pages:
            item["pages"] = sorted(set(pages))[:12]
        if cells:
            item["cells"] = {k: round(v, 4) for k, v in sorted(cells.items())}
        evidence.append(item)

    def pixel_pair(hex6: str) -> Tuple[Optional[Dict[str, Any]], str]:
        rec = _find_pixel_color(pixels, hex6)
        if not rec:
            return None, ""
        return rec, _pixel_note(rec, sampled)

    # ① 主色：主题 accent1 > 像素里饱和度/占比最高的颜色
    accent = slots.get("accent1") or ""
    if accent:
        rec, note = pixel_pair(accent)
        if rec:
            add("accent", accent, "theme:%s#accent1" % (theme.get("file") or "theme"),
                "主题 accent1；像素复核：" + note, rec["count"], rec["pages"], _avg_cells(rec))
        else:
            add("accent", accent, "theme:%s#accent1" % (theme.get("file") or "theme"),
                "主题 accent1；渲染像素中未大量出现（可能是纯令牌色或只用于局部）")
            warnings.append("主色 %s 来自主题色板，但未在渲染像素中大量出现（像素统计只做复核）" % accent)
    elif colors:
        top = max(colors.items(), key=lambda kv: kv[1]["count"])
        accent = top[0]
        add("accent", accent, "pixels", "像素实测：占比最高的饱和色；" + _pixel_note(top[1], sampled),
            top[1]["count"], top[1]["pages"], _avg_cells(top[1]))
    else:
        accent = "#1E78FA"
        add("accent", accent, "fallback", "既无主题色板也无可用像素统计，取保守默认主色（务必人工确认）")
        warnings.append("没有取得任何颜色证据，主色取保守默认 %s —— 请人工确认" % accent)

    accent_hue = _hsv(accent)[0]

    # ② 点睛色：主题 accent2..accent6 中**色相与主色拉开**且像素占比最高的那个
    cands = []
    for key in ("accent2", "accent3", "accent4", "accent5", "accent6"):
        val = slots.get(key)
        if not val:
            continue
        hue, sat, vv = _hsv(val)
        if sat < 0.25 or _hue_dist(hue, accent_hue) < 25:
            continue
        rec, note = pixel_pair(val)
        cands.append(dict(slot=key, value=val, ratio=(rec["count"] if rec else 0.0), rec=rec, note=note, hue=hue))
    cands.sort(key=lambda c: -c["ratio"])
    accent2 = ""
    picked_hues: List[float] = [accent_hue]
    for cand in cands:
        if any(_hue_dist(cand["hue"], h) < 30 for h in picked_hues):
            continue
        accent2 = cand["value"]
        if cand["rec"]:
            add("accent-2", accent2, "theme:%s#%s" % (theme.get("file") or "theme", cand["slot"]),
                "主题 %s；像素复核：%s" % (cand["slot"], cand["note"]), cand["rec"]["count"],
                cand["rec"]["pages"], _avg_cells(cand["rec"]))
        else:
            add("accent-2", accent2, "theme:%s#%s" % (theme.get("file") or "theme", cand["slot"]),
                "主题 %s（未在渲染像素中大量出现）" % cand["slot"])
            warnings.append("点睛色 %s 只来自主题色板，未在渲染像素中大量出现（请人工确认是否真在用）" % accent2)
        picked_hues.append(cand["hue"])
        break
    if not accent2 and colors:
        # 图片输入 / 主题里没有独立配色的情形：从像素里找第二个色相家族的饱和色
        for hx, rec in sorted(colors.items(), key=lambda kv: -kv[1]["count"]):
            hue = rec.get("hue") or _hsv(hx)[0]
            if _hue_dist(hue, accent_hue) >= 30:
                accent2 = hx
                add("accent-2", accent2, "pixels", "像素实测：与主色相异的第二大饱和色；" + _pixel_note(rec, sampled),
                    rec["count"], rec["pages"], _avg_cells(rec))
                picked_hues.append(hue)
                break

    # ③ 深色变体（给白字兜底用）：同色相、更暗、且像素里真的出现过
    deep = ""
    deep_slot = ""
    for key in ("accent3", "accent4", "accent5", "accent6", "accent2"):
        val = slots.get(key)
        if not val:
            continue
        hue, sat, vv = _hsv(val)
        if _hue_dist(hue, accent_hue) <= 22 and _luma(val) < _luma(accent) and contrast(val, "#FFFFFF") >= 4.5:
            rec, _note = pixel_pair(val)
            if rec and rec["count"] >= 0.002:
                deep, deep_slot = val, key
                add("accent-deep", deep, "theme:%s#%s" % (theme.get("file") or "theme", key),
                    "主题 %s：与主色同色相、更暗，白字对比度 %.2f:1（可承载白字）" % (key, contrast(val, "#FFFFFF")),
                    rec["count"], rec["pages"], _avg_cells(rec))
                break
    if not deep:
        # 没有可用的实测深色 → 用实测主色按比例压暗，明确标注为「派生」
        for amount in (0.15, 0.25, 0.35, 0.45, 0.55):
            cand = _darker(accent, amount)
            if contrast(cand, "#FFFFFF") >= 4.5:
                deep = cand
                add("accent-deep", deep, "derived:darken(%s, %.2f)" % (accent, amount),
                    "证据里没有可承载白字的深色，按实测主色压暗 %.0f%% 派生（白字对比度 %.2f:1）"
                    % (amount * 100, contrast(cand, "#FFFFFF")))
                warnings.append("accent-deep 由实测主色压暗派生（证据色板里没有更深的同色相色）")
                break

    # ③b 页面级大色块：不在主题色板里、但**在某一页占据大面积**的实测色（典型：封面贯通横带）
    #   必须「封面优先」分两轮找 —— 曾按全局 peak 排序只取一个块，结果封面横带（单页占 9.6%）
    #   被章节页渐变亮蓝（单页占 24%）挤掉，accent-cover 永远取不到（真机实测踩到）。
    picked_hex = [v for v in (accent, accent2, deep) if v]

    def _is_new_color(hx: str) -> bool:
        return not any(max(abs(hex_to_rgb(hx)[i] - hex_to_rgb(p)[i]) for i in range(3)) <= 24
                       for p in picked_hex)

    def _biggest_block(only_pages: List[int]) -> Optional[Dict[str, Any]]:
        for hx, rec in sorted((pixels.get("colors") or {}).items(), key=lambda kv: -kv[1].get("peak", 0)):
            if rec.get("peak", 0) < 0.05 or not _is_new_color(hx):
                continue
            if only_pages and not (set(rec.get("pages") or []) & set(only_pages)):
                continue
            return dict(hex=hx, **rec)
        return None

    def _add_block(role: str, rec: Dict[str, Any], why: str) -> None:
        pages = sorted(set(rec["pages"]))
        add(role, rec["hex"], "pixels",
            "像素实测：%s（第 %s 页占该页 %.0f%%）" % (
                why, rec.get("peak_page") or (pages[0] if pages else "-"), rec["peak"] * 100)
            + "；" + _pixel_note(rec, sampled), rec["count"], rec["pages"], _avg_cells(rec))

    sampled_first = sorted(pixels.get("sampled_pages") or [])[:2]        # 封面（+ 次页）
    cover_block = _biggest_block(sampled_first)
    if cover_block:
        _add_block("accent-cover", cover_block, "封面/前两页的大面积色块（封面横带一类）")
        picked_hex.append(cover_block["hex"])                            # 避免同一色再被算成 accent-3
    block = _biggest_block([])
    if block:
        _add_block("accent-3", block, "全篇单页最大面积色")

    # ④ 底材与浅色卡面
    bg = "#FFFFFF"
    light_pick = None
    for hx, rec in sorted(lights.items(), key=lambda kv: -kv[1]["count"]):
        light_pick = dict(hex=hx, **rec)
        break
    if slots.get("lt1") and _luma(slots["lt1"]) > 0.8:
        bg = slots["lt1"]
    if light_pick and light_pick["count"] > 0.15:
        bg = light_pick["hex"]
        add("bg", bg, "pixels", "像素实测：占比最高的浅色底材；" + _pixel_note(light_pick, sampled),
            light_pick["count"], light_pick["pages"])
    elif slots.get("lt1"):
        add("bg", bg, "theme:%s#lt1" % (theme.get("file") or "theme"), "主题 lt1（浅色底材）")
    else:
        add("bg", bg, "fallback", "未测到底材色，保守取 #FFFFFF")
        warnings.append("未测到底材色，bg 取 #FFFFFF（界面与风格包请人工确认）")

    tints: List[Dict[str, Any]] = []
    for hx, rec in sorted(lights.items(), key=lambda kv: -kv[1]["count"]):
        if hx.upper() == bg.lstrip("#").upper() or hx.upper() == bg.upper():
            continue
        hue, sat, vv = _hsv(hx)
        if vv < 0.82 or vv > 0.99 or rec["count"] < 0.01:
            continue
        if not (0.02 <= sat <= 0.28):               # 真正的「浅色卡面」而不是饱和色块
            continue
        if _hue_dist(hue, accent_hue) > 60:
            continue
        tints.append(dict(hex=hx, **rec))
        if len(tints) >= 2:
            break
    if tints:
        add("tint-1", tints[0]["hex"], "pixels", "像素实测浅色卡面；" + _pixel_note(tints[0], sampled),
            tints[0]["count"], tints[0]["pages"])
        second = tints[1]["hex"] if len(tints) > 1 else tints[0]["hex"]
        add("tint-2", second, "pixels" if len(tints) > 1 else "pixels(same-as-tint-1)",
            "像素实测浅色卡面；" + _pixel_note(tints[min(1, len(tints) - 1)], sampled),
            tints[min(1, len(tints) - 1)]["count"], tints[min(1, len(tints) - 1)]["pages"])
        if len(tints) == 1:
            warnings.append("只测到 1 种浅色卡面，tint-2 与 tint-1 同值")
    surface = tints[0]["hex"] if tints else _lighter(bg, 0.04)
    add("surface", surface, "pixels" if tints else "derived:lighten(%s)" % bg,
        "像素实测浅色卡面" if tints else "无独立卡面色，按底材轻微提亮派生")

    # ⑤ 文字色：优先**像素实测**的暗色正文色，其次主题 dk1，最后保守默认
    bg_dark = _luma(bg) < 0.4
    ink = ""
    dark_pick = None
    for hx, rec in sorted((pixels.get("darks") or {}).items(), key=lambda kv: -kv[1]["count"]):
        if _luma(hx) < 0.25 and contrast(hx, bg) >= 4.5:
            dark_pick = dict(hex=hx, **rec)
            break
    theme_ink = slots.get("dk1") or ""
    if dark_pick:
        ink = dark_pick["hex"]
        add("ink", ink, "pixels", "像素实测暗色文字（页面上真的在用）；" + _pixel_note(dark_pick, sampled),
            dark_pick["count"], dark_pick["pages"])
    elif theme_ink and (not bg_dark) and _luma(theme_ink) < 0.35:
        ink = theme_ink
        add("ink", ink, "theme:%s#dk1" % (theme.get("file") or "theme"),
            "主题 dk1（深色文字；像素里没有稳定的暗色众数）")
    if not ink:
        ink = "#FFFFFF" if bg_dark else "#1D1D1A"
        add("ink", ink, "fallback", "未测得文字色，按底材明度取保守默认（%s）" % ink)
        warnings.append("未测得文字色，ink 取保守默认 %s" % ink)
    if contrast(ink, bg) < 4.5:
        cand = "#FFFFFF" if bg_dark else "#1D1D1A"
        warnings.append("实测文字色 %s 在底材 %s 上对比度仅 %.2f:1，令牌改用 %s（实测值仍留在证据里）"
                        % (ink, bg, contrast(ink, bg), cand))
        ink = cand
        add("ink", ink, "adjusted", "为保证 WCAG AA，底材对比度不足，改用 %s" % cand)

    ink_sub = ""
    for hx, rec in sorted(mids.items(), key=lambda kv: -kv[1]["count"]):
        if 0.15 <= _hsv(hx)[2] <= 0.72 and rec["count"] >= 0.005 and contrast(hx, bg) >= 4.5:
            ink_sub = hx
            add("ink-sub", ink_sub, "pixels", "像素实测次要文字色；" + _pixel_note(rec, sampled),
                rec["count"], rec["pages"])
            break
    if not ink_sub and slots.get("dk2") and contrast(slots["dk2"], bg) >= 4.5:
        ink_sub = slots["dk2"]
        add("ink-sub", ink_sub, "theme:%s#dk2" % (theme.get("file") or "theme"),
            "主题 dk2（次要文字；未从像素单独测得）")
        warnings.append("未从像素测得次要文字色，ink-sub 取主题 dk2 = %s" % ink_sub)
    if not ink_sub:
        add("ink-sub", ink, "fallback:ink", "未测得次要文字色，与 ink 同值（正文与标题同色）")
        warnings.append("未测得次要文字色，正文与标题同色（可用 ink）")

    # ⑥ canonical 四色（DESIGN.md 惯例名字，全部指向实测值）
    tertiary = accent2 or accent
    neutral = _lighter(bg, 0.03) if not tints else tints[0]["hex"]
    palette.update(dict(primary=ink, secondary=palette.get("ink-sub", ink), tertiary=tertiary, neutral=neutral))
    return palette, evidence


def _avg_cells(rec: Dict[str, Any]) -> Dict[str, float]:
    """把 `{格号:页:值}` 聚合成 `{格号: 均值}`。"""
    acc: Dict[str, List[float]] = {}
    for key, val in (rec.get("cells") or {}).items():
        acc.setdefault(key.split(":")[0], []).append(val)
    return {k: sum(v) / len(v) for k, v in acc.items()}


# ────────────────────────── 令牌（typography / rounded / spacing / components） ──────────────────────────

def build_typography(struct: Dict[str, Any], theme: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
    """字号来自 pptx 的 rPr sz（pt，×100 存储）；字体来自 fontScheme。图片输入 → 明确降级。"""
    sizes = [s["pt"] / 100.0 for s in (struct.get("sizes_pt") or [])]
    fonts = theme.get("fonts") or {}
    major = fonts.get("majorFont") or ""
    minor = fonts.get("minorFont") or ""
    if not major and not minor:
        names = [f["name"] for f in (struct.get("fonts") or []) if len(f["name"]) > 1]
        major = minor = (names[0] if names else "")
    if not major and not minor:
        major = minor = "PingFang SC"
        warnings.append("没有取得字体证据（图片输入或主题无字体方案），令牌字体取系统默认 PingFang SC")

    def pt_to_rem(pt: float) -> str:
        return "%grem" % round(max(0.75, min(4.0, pt * 1.3333 / 16.0)), 2)

    body_pt = None
    if sizes:
        body_pt = sizes[0]                          # sizes 已按出现次数降序，第一项就是众数字号
    h1_pt = None
    max_pt = struct.get("size_max_pt")
    if isinstance(max_pt, (int, float)) and max_pt / 100.0 >= 20:
        h1_pt = max_pt / 100.0                      # 页/章标题：样本里真的出现过的最大字号
    if h1_pt is None:
        for s in sizes:
            if s >= 20:
                h1_pt = s
                break
    h1_pt = h1_pt or (body_pt * 2.0 if body_pt else 28.0)
    h1_pt = min(h1_pt, 4.0 * 16 / 1.3333)            # 令牌上限 4rem
    body_pt = body_pt or 14.0
    h3_pt = body_pt * 1.15
    h2_pt = (h1_pt + body_pt) / 2.0
    typo = {
        "h1": dict(fontFamily=major or minor, fontSize=pt_to_rem(h1_pt), fontWeight=800, lineHeight=1.18,
                   letterSpacing="-0.01em"),
        "h2": dict(fontFamily=major or minor, fontSize=pt_to_rem(h2_pt), fontWeight=700, lineHeight=1.25),
        "h3": dict(fontFamily=minor or major, fontSize=pt_to_rem(h3_pt), fontWeight=700, lineHeight=1.35),
        "body-md": dict(fontFamily=minor or major, fontSize=pt_to_rem(body_pt), fontWeight=400, lineHeight=1.7),
    }
    if not sizes:
        warnings.append("没有取得字号证据（图片输入），令牌字号按常规比例给默认值")
    return typo


def build_rounded(struct: Dict[str, Any], warnings: List[str]) -> Dict[str, str]:
    """圆角档位 = 实测分布的加权分位数（不是极值，避免被个别形状带偏）。"""
    dist = [(d["px"], d["count"]) for d in (struct.get("corner_radius_px") or []) if d["px"] > 0]
    if dist:
        total = sum(c for _, c in dist)
        ordered = sorted(dist)
        def pct(q: float) -> int:
            target = max(1, int(round(q * total)))
            seen = 0
            for px, cnt in ordered:
                seen += cnt
                if seen >= target:
                    return px
            return ordered[-1][0]
        return dict(sm="%dpx" % pct(0.25), md="%dpx" % pct(0.5), lg="%dpx" % pct(0.9), pill="999px")
    warnings.append("未测得圆角分布（无 roundRect 或图片输入），圆角令牌取保守默认 8/12/20px")
    return dict(sm="8px", md="12px", lg="20px", pill="999px")


def build_spacing(struct: Dict[str, Any]) -> Dict[str, str]:
    margin = struct.get("page_margin_px")
    if not isinstance(margin, int) or margin <= 0:
        margin = 52
    return dict(sm="8px", md="20px", lg="32px", **{"page-margin": "%dpx" % margin})


# ────────────────────────── 视觉定性描述（颜色/字号一律弃用） ──────────────────────────

_HEX_IN_TEXT = re.compile(r"#[0-9A-Fa-f]{6}\b|\b\d+\s*(?:pt|px)\b", re.I)
_DROP_KEYS = ("colors", "color", "palette", "font", "fonts", "fontFamily", "font_size", "fontSize",
              "font_size_pt", "size_pt", "hex", "rgb")


def _sanitize_vision_text(text: Any) -> str:
    """抹掉视觉模型擅自在文字里给的颜色值/字号（铁律 1：颜色与字号一律弃用）。"""
    s = str(text or "").strip()
    return _HEX_IN_TEXT.sub("（颜色/字号以实测为准）", s)[:600]


def _vision_describe(page_no: int, page_path: str) -> Dict[str, Any]:
    """调视觉模型做**定性**描述。未配置/失败 → ok=False（调用方安全降级）。"""
    vp = config.vision_provider(with_keys=True)
    if not vp.get("key"):
        return dict(ok=False, reason="not_configured", message="未配置视觉模型 API Key（设置页「视觉模型」）")
    try:
        with open(page_path, "rb") as f:
            data_url = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
        body = dict(model=vp["default_model"], temperature=0.0, max_tokens=1200,
                    messages=[dict(role="user", content=[
                        dict(type="image_url", image_url=dict(url=data_url)),
                        dict(type="text", text=VISION_STYLE_PROMPT)])])
        with httpx.Client(**providers._client_kwargs(bool(vp.get("needs_proxy")), 180.0)) as c:
            r = c.post(vp["base_url"].rstrip("/") + "/chat/completions",
                       headers={"Authorization": "Bearer %s" % vp["key"], "Content-Type": "application/json"},
                       json=body)
            r.raise_for_status()
            content = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        scene = providers.parse_vision_json(content)
        if not isinstance(scene, dict):
            return dict(ok=False, reason="bad_json", message="视觉模型返回内容无法解析为 JSON", page=page_no)
        keep: Dict[str, Any] = dict(ok=True, page=page_no, model=vp["default_model"], raw_keys=[])
        for key in ("layout", "graphic_language", "hierarchy", "mood"):
            keep[key] = _sanitize_vision_text(scene.get(key))
        for key in ("elements", "donts"):
            vals = scene.get(key)
            keep[key] = [_sanitize_vision_text(v) for v in vals][:6] if isinstance(vals, list) else []
        keep["dropped_fields"] = [k for k in scene if any(d.lower() == str(k).lower() for d in _DROP_KEYS)]
        return keep
    except Exception as exc:                            # noqa: BLE001
        return dict(ok=False, reason="call_failed", page=page_no,
                    message="%s: %s" % (type(exc).__name__, str(exc)[:160]))


# ────────────────────────── 文字合成（LLM 只写文字；失败走模板） ──────────────────────────

def _facts_digest(name_hint: str, palette: Dict[str, Any], evidence: List[Dict[str, Any]],
                  typo: Dict[str, Any], rounded: Dict[str, str], spacing: Dict[str, str],
                  struct: Dict[str, Any], pixels: Dict[str, Any], vision: List[Dict[str, Any]]) -> str:
    lines = ["【实测事实（禁止改动其中任何色值/字号；不确定就少写）】"]
    for e in evidence:
        lines.append("- %s = %s（来源 %s%s）" % (e["role"], e["value"], e["source"],
                                              ("；" + e["note"]) if e.get("note") else ""))
    if struct.get("shapes"):
        lines.append("- 形状统计：%s" % json.dumps(struct["shapes"], ensure_ascii=False))
    if struct.get("gradients") is not None:
        lines.append("- 渐变填充出现 %s 次、投影 %s 次" % (struct.get("gradients"), struct.get("shadows")))
    if struct.get("corner_radius_px"):
        lines.append("- 圆角实测分布：%s" % json.dumps(struct["corner_radius_px"], ensure_ascii=False))
    if struct.get("sizes_pt"):
        lines.append("- 字号实测分布（pt×100）：%s" % json.dumps(struct["sizes_pt"], ensure_ascii=False))
    if struct.get("slides"):
        lines.append("- 共解析 %s 页幻灯片" % struct["slides"])
    if pixels.get("per_page"):
        whites = [p["white_ratio"] for p in pixels["per_page"].values() if "white_ratio" in p]
        if whites:
            lines.append("- 白底占比区间：%.0f%%~%.0f%%" % (min(whites) * 100, max(whites) * 100))
    lines.append("- 令牌层级：标题 %s/%s，正文 %s/%s" % (
        typo["h1"]["fontFamily"], typo["h1"]["fontSize"], typo["body-md"]["fontFamily"],
        typo["body-md"]["fontSize"]))
    lines.append("- 圆角令牌 %s / 页边距 %s" % (json.dumps(rounded, ensure_ascii=False), spacing["page-margin"]))
    for v in vision:
        if v.get("ok"):
            lines.append("- 第 %s 页画面：版式=%s；图形语言=%s；层级留白=%s；气质=%s" % (
                v.get("page"), v.get("layout"), v.get("graphic_language"), v.get("hierarchy"), v.get("mood")))
    return "\n".join(lines)


PROSE_CONTRACT = """只输出严格 JSON（不要 Markdown 围栏、不要解释），字段：
{"name":"中文风格名（6~12 字，带气质词）","category":"分类（如 商务/汇报、科技/现代）",
"tags":["2~4 个中文标签"],"summary":"一句话摘要（≤40 字）",
"overview":"Overview 段落（2~4 句）","colors":"Colors 段落（讲清每个实测色的用法与禁忌）",
"typography":"Typography 段落","layout":"Layout 段落","elevation":"Elevation and Depth 段落",
"shapes":"Shapes 段落","components":"Components 段落",
"dos":["✅ 该做的（3~6 条）"],"donts":["❌ 不该做的（3~6 条）"],
"prompt_md":"给生图模型的画面语言正文（中文，≤900 字，分小节：底材与配色/图形语言/元素密度与留白/光影）",
"en_keywords":"英文关键词一行（逗号分隔）","negative":"负向词一行（逗号分隔）"}"""


def _compose_prose(digest: str, vision: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """LLM 写文字。失败/不可用 → 返回 (None, meta)，由调用方走模板。"""
    system = ("你是 PPT 视觉规范撰写者。**只能使用给定事实**：不得新增、修改或推断任何颜色值/字号/字体；"
              "没有证据就不写。输出严格 JSON。")
    ok, content, meta = providers.call_text(system, digest + "\n\n" + PROSE_CONTRACT, max_tokens=2600)
    if not ok:
        return {}, dict(ok=False, **meta)
    data = providers.parse_vision_json(content)
    if not isinstance(data, dict) or not str(data.get("overview") or "").strip():
        return {}, dict(ok=False, reason="bad_json", **{k: v for k, v in meta.items() if k != "reason"})
    return data, dict(ok=True, **meta)


def _template_prose(palette: Dict[str, Any], evidence: List[Dict[str, Any]], typo: Dict[str, Any],
                    rounded: Dict[str, str], spacing: Dict[str, str], struct: Dict[str, Any],
                    vision: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 不可用时的模板化文字：措辞固定，**数据全部来自实测**。"""
    accent = palette.get("accent", "")
    accent2 = palette.get("accent-2") or ""
    bg = palette.get("bg", "#FFFFFF")
    ink = palette.get("ink", "#1D1D1A")
    deep = palette.get("accent-deep") or ""
    acn, accn = _color_word(accent)
    extra = ("，点睛色 %s" % accent2) if accent2 else ""
    mood = ""
    for v in vision:
        if v.get("ok") and v.get("mood"):
            mood = v["mood"]
            break
    dos = ["✅ 底材 %s + 实测主色 %s 承担结构性色块%s" % (bg, accent, extra),
           "✅ 标题用 %s，正文字号 %s，层级不超过 4 档" % (typo["h1"]["fontSize"], typo["body-md"]["fontSize"]),
           "✅ 圆角按实测档位使用（%s）" % "、".join(sorted(set(rounded.values()) - {"999px"})),
           "✅ 页边距不小于 %s" % spacing["page-margin"]]
    if accent2:
        dos.append("✅ %s 只做点睛（关键数字/编号/图表第二序列/强调线），不要与主色抢面积" % accent2)
    donts = ["❌ 不要引入本次实测之外的颜色",
             "❌ 不要在深色底上写深色字、浅色底上写浅色字（先看对比度）"]
    if accent2:
        donts.append("❌ 不要把 %s 当正文色或大色块底" % accent2)
    donts.append("❌ 不要整页铺满饱和色当内容页底")
    if not struct.get("gradients"):
        donts.append("❌ 原稿没有渐变证据，不要自行加整页渐变")
    if not struct.get("shadows"):
        donts.append("❌ 原稿没有投影证据，不要加重投影/发光")
    return dict(
        name="%s%s汇报风" % (acn if acn != "color" else "", accn),
        category="自动提取/待分类",
        tags=["实测提取", accn],
        summary="由实测提取：%s 底材 + 主色 %s%s" % (bg, accent, extra),
        overview="这是一套从上传样本**实测提取**的风格规范：底材 %s，主色 %s%s。"
                 "令牌与色值均来自主题色板与渲染像素统计，不是目测或模型想象。" % (bg, accent, extra),
        colors="实测色板见 front matter（每个值都带出处）。结构性色块用 %s，深色强调用 %s%s。" % (
            accent, deep or accent, ("，%s 只做点睛" % accent2) if accent2 else ""),
        typography="标题 %s %s，正文 %s %s（字号来自样本实测分布）。" % (
            typo["h1"]["fontFamily"], typo["h1"]["fontSize"], typo["body-md"]["fontFamily"],
            typo["body-md"]["fontSize"]),
        layout="按样本实测：页边距约 %s，卡片间距 %s。%s" % (spacing["page-margin"], spacing["md"], mood),
        elevation=("样本里检测到 %d 处投影。" % struct["shadows"]) if struct.get("shadows")
                  else "样本里**没有**投影证据，视觉层级请靠色块与留白建立。",
        shapes="形状统计：%s。圆角档位 %s。" % (json.dumps(struct.get("shapes") or {}, ensure_ascii=False),
                                          "、".join(sorted(set(rounded.values()) - {"999px"}))),
        components="组件沿用 front matter 定义（页面底/卡片/浅色卡面/标题与正文/强调条）。",
        dos=dos, donts=donts,
        prompt_md="", en_keywords="", negative="",
    )


# ────────────────────────── prompt.md（≤1500 字符硬约束） ──────────────────────────

def build_prompt_md(name: str, palette: Dict[str, Any], prose: Dict[str, Any], evidence: List[Dict[str, Any]],
                    rounded: Dict[str, str], struct: Dict[str, Any]) -> str:
    """拼 prompt.md：中文画面语言 + 中英关键词 + 负向词，全程按 1500 字符预算裁剪。"""
    accent = palette.get("accent", "")
    accent2 = palette.get("accent-2") or ""
    bg = palette.get("bg", "#FFFFFF")
    ink = palette.get("ink", "#1D1D1A")
    ink_sub = palette.get("ink-sub") or ink
    tint = palette.get("tint-1") or palette.get("surface") or bg
    deep = palette.get("accent-deep") or accent
    acn, accn = _color_word(accent)
    vision_bits = [p for p in (prose.get("vision_lines") or []) if p]

    head = "# 画面语言：%s" % (name or "实测提取风格")
    blocks: List[Tuple[int, str]] = []          # (删除优先级，越小越先删)

    color_lines = ["## 底材与配色",
                   "底材 %s（白/浅色为常态），浅色卡面 %s。主色 %s 承担结构性色块（底条、圆点、图表主序列、图标块）。"
                   % (bg, tint, accent)]
    if accent2:
        color_lines.append("点睛色 %s 只落在关键数字、编号、图表第二序列与强调线，占画面 ≤5%%。" % accent2)
    color_lines.append("深色强调块用 %s；标题 %s，正文 %s。" % (deep, ink, ink_sub))
    if vision_bits:
        color_lines.append(vision_bits[0])
    blocks.append((3, "\n".join(color_lines)))

    graphic = ["## 图形语言"]
    if prose.get("graphic_md"):
        graphic.append(str(prose["graphic_md"])[:600])
    else:
        shapes = struct.get("shapes") or {}
        top = "、".join(list(shapes)[:4]) or "矩形/圆角矩形/圆形"
        graphic.append("以 %s 为主：直角矩形做分区，微圆角卡片放内容（圆角档位 %s），圆形做编号与圆点，胶囊做小标签。"
                       % (top, "、".join(sorted(set(rounded.values()) - {"999px"}))))
        graphic.append("细分割线 1pt，强调线 3pt；图标线性扁平统一描边。")
    blocks.append((4, "\n".join(graphic)))

    layout_lines = ["## 元素密度与留白"]
    if prose.get("layout_md"):
        layout_lines.append(str(prose["layout_md"])[:420])
    else:
        layout_lines.append("中低密度：一页 3~4 个模块，同级模块等宽等高，间距 ≥20px，四周留白充足。")
    if vision_bits:
        layout_lines.append(vision_bits[1] if len(vision_bits) > 1 else vision_bits[0])
    blocks.append((5, "\n".join(layout_lines)))

    light_lines = ["## 光影"]
    if struct.get("shadows"):
        light_lines.append("允许克制投影（检测到 %d 处投影）：让卡片从浅底上浮起。" % struct["shadows"])
    else:
        light_lines.append("**不使用投影**（样本里没有投影证据），层级靠色块与留白。")
    if struct.get("gradients"):
        light_lines.append("可用线性渐变（检测到 %d 处渐变填充）做色块与图表。" % struct["gradients"])
    light_lines.append("严禁霓虹发光、玻璃拟态、大面积模糊光斑。")
    blocks.append((6, "\n".join(light_lines)))

    kw = "## 中英关键词\n" + (str(prose.get("en_keywords") or "").strip()
                            or ("clean %s background, %s primary accent%s, bold heavy sans-serif headings, "
                                "flat linear icons, structured business report deck, logical diagram layout, "
                                "generous margins, 2K, 16:9"
                                % (acn, acn, (", %s accent used sparingly" % accn) if accent2 else "")))
    blocks.append((1, kw))
    neg = "## 负向词（必带）\n" + (str(prose.get("negative") or "").strip() or NEGATIVE_WORDS)
    blocks.append((0, neg))

    return _fit_prompt(head, blocks)


def _fit_prompt(head: str, blocks: List[Tuple[int, str]]) -> str:
    """按优先级先删可选块，再硬裁，保证 ≤ PROMPT_LIMIT 字符（render 只取前 1500）。"""
    drops = sorted(set(p for p, _ in blocks))
    kept = list(blocks)
    for prio in drops:
        text = head + "\n\n" + "\n\n".join(b for _, b in kept)
        if len(text) <= PROMPT_LIMIT:
            break
        if prio == 0:                       # 负向词必带，不删
            continue
        kept = [b for b in kept if b[0] != prio]
    text = (head + "\n\n" + "\n\n".join(b for _, b in kept)).strip()
    if len(text) > PROMPT_LIMIT:
        text = text[:PROMPT_LIMIT].rstrip()
    return text


# ────────────────────────── style.md 组装 + 自检 ──────────────────────────

def _color_ref(ref: str) -> str:
    """把令牌引用解析成 colors 字典的键名：`{colors.ink}` / `colors.ink` / `ink` → `ink`。

    坑（已修）：曾写成 `ref.replace("colors.", "")` 而漏剥花括号 → `colors.get("{ink}")` 永远取空，
    于是**所有带 textColor 的组件被静默丢弃**、随后孤立令牌清理又把色板删掉一半。
    """
    return re.sub(r"[{}]", "", str(ref or "")).replace("colors.", "").strip()


def build_tokens(palette: Dict[str, Any], typo: Dict[str, Any], rounded: Dict[str, str],
                 spacing: Dict[str, str], hints: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
    """由代码生成 yaml 令牌；组件只保留**对比度达标**的配対，装饰件不带 textColor。"""
    colors: Dict[str, str] = {}
    order = ("primary", "secondary", "tertiary", "neutral", "bg", "surface", "accent", "accent-2",
             "accent-deep", "accent-cover", "accent-3", "tint-1", "tint-2", "ink", "ink-sub")
    for key in order:
        val = palette.get(key)
        if isinstance(val, str) and re.match(r"^#[0-9A-Fa-f]{6}$", val):
            colors[key] = val.upper()
    if "bg" not in colors:
        colors["bg"] = "#FFFFFF"
    if "ink" not in colors:
        colors["ink"] = "#1D1D1A"

    bg = colors.get("bg", "#FFFFFF")
    ink = colors.get("ink", "#1D1D1A")
    ink_sub = colors.get("ink-sub") or ink
    comps: Dict[str, Dict[str, str]] = {}
    dropped: List[str] = []

    def add(key: str, bg_ref: str, **props: Any) -> None:
        want = dict(props)
        text_ref = want.pop("textColor", "")
        text_hex = ""
        if text_ref:
            text_hex = "#FFFFFF" if text_ref == "white" else colors.get(_color_ref(text_ref), "")
            if not text_hex:
                dropped.append("%s（缺 textColor 取值）" % key)
                return
            base = colors.get(_color_ref(bg_ref), "")
            if not base:
                dropped.append("%s（缺 backgroundColor 取值）" % key)
                return
            if contrast(text_hex, base) < 4.5:
                alt = "#FFFFFF" if contrast("#FFFFFF", base) >= 4.5 else (ink if contrast(ink, base) >= 4.5 else "")
                if not alt:
                    dropped.append("%s（%s 上白字与深字都不达 4.5:1）" % (key, base))
                    warnings.append("组件 %s 因对比度不达标被丢弃：背景 %s 无可用文字色" % (key, base))
                    return
                warnings.append("组件 %s 的文字色由 %s 改为 %s 以满足 WCAG AA（背景 %s）"
                                % (key, text_hex, alt, base))
                text_hex = alt
        entry: Dict[str, str] = dict(backgroundColor=bg_ref)
        if text_hex:
            # 未被对比度修正时保留**引用写法**（`{colors.ink}`）：既与既有风格包一致，
            # 也让下面的孤立令牌清理能认出“这个色确实有组件在用”（曾写字面值导致 ink 被误删）。
            original = colors.get(_color_ref(text_ref), "")
            entry["textColor"] = text_ref if text_hex == original else text_hex
        entry.update(want)
        comps[key] = entry

    add("page-bg", "{colors.bg}")
    add("card", "{colors.surface}",
        textColor="{colors.ink}", rounded="{rounded.md}", padding="20")
    add("title-text", "{colors.bg}", textColor="{colors.primary}" if "primary" in colors else "{colors.ink}",
        typography="{typography.h1}")
    add("body-text", "{colors.bg}", textColor="{colors.secondary}" if "secondary" in colors else "{colors.ink}",
        typography="{typography.body-md}")
    add("deep-block", "{colors.neutral}" if "neutral" in colors else "{colors.bg}",
        textColor="{colors.ink}", rounded="{rounded.sm}", padding="16")
    if "accent" in colors or "accent-bar" in colors:
        accent_color = next((key for key in ("accent", "tertiary", "primary") if key in colors), None)
        if accent_color is not None:
            add("accent-bar", "{colors.%s}" % accent_color, rounded="{rounded.sm}")
    if "tertiary" in colors:
        add("accent-rule", "{colors.tertiary}", height="3px")
    if "accent-2" in colors:
        add("accent-2-bar", "{colors.accent-2}", rounded="{rounded.pill}")
    if "accent-cover" in colors:
        add("cover-band", "{colors.accent-cover}", rounded="{rounded.sm}")
    if "accent-3" in colors:
        add("accent-3-rule", "{colors.accent-3}", height="3px")
    if "accent-deep" in colors:
        add("hero-panel", "{colors.accent-deep}", textColor="white", rounded="{rounded.sm}", padding="32")
        add("num-badge", "{colors.accent-deep}", textColor="white", rounded="{rounded.pill}")
    if "tint-1" in colors:
        add("tint-card", "{colors.tint-1}", textColor="{colors.ink-sub}" if "ink-sub" in colors else "{colors.ink}",
            rounded="{rounded.md}", padding="16")
    if "tint-2" in colors:
        add("tint-card-2", "{colors.tint-2}", textColor="{colors.ink}", rounded="{rounded.md}", padding="16")

    # 孤立令牌清理：没被任何组件引用的颜色令牌要么补引用，要么移除（lint 会报 orphaned-tokens）
    used = set()
    for entry in comps.values():
        for val in entry.values():
            for m in re.findall(r"\{colors\.([a-zA-Z0-9_-]+)\}", str(val)):
                used.add(m)
    for key in list(colors):
        if key not in used:
            colors.pop(key)
            dropped.append("colors.%s（无组件引用，已移除以免 orphaned-tokens）" % key)
    if dropped:
        warnings.append("令牌收敛：" + "；".join(dropped[:8]))

    name = (hints.get("name") or "").strip() or "实测提取风格"
    desc = (hints.get("summary") or "").strip()
    return dict(name=name, description=desc, colors=colors, typography=typo, rounded=rounded,
                spacing=spacing, components=comps)


def _yaml_str(text: str) -> str:
    return json.dumps(str(text or ""), ensure_ascii=False)


def render_style_md(tokens: Dict[str, Any], sections: Dict[str, str]) -> str:
    """手写 front matter（可控、可读）+ 八节 prose（canonical 顺序，重名由调用方保证）。"""
    lines = ["---", "version: alpha", "name: %s" % _yaml_str(tokens["name"]),
             "description: %s" % _yaml_str(tokens.get("description") or ""), "colors:"]
    for key, val in tokens["colors"].items():
        lines.append("  %s: %s" % (key, _yaml_str(val)))
    lines.append("typography:")
    for key, val in tokens["typography"].items():
        lines.append("  %s:" % key)
        for prop, pval in val.items():
            lines.append("    %s: %s" % (prop, _yaml_str(pval) if isinstance(pval, str) else pval))
    lines.append("rounded:")
    for key, val in tokens["rounded"].items():
        lines.append("  %s: %s" % (key, _yaml_str(val)))
    lines.append("spacing:")
    for key, val in tokens["spacing"].items():
        lines.append("  %s: %s" % (key, _yaml_str(val)))
    lines.append("components:")
    for key, val in tokens["components"].items():
        lines.append("  %s:" % key)
        for prop, pval in val.items():
            lines.append("    %s: %s" % (prop, _yaml_str(pval) if isinstance(pval, str) else pval))
    lines.append("---")
    body_order = ("Overview", "Colors", "Typography", "Layout", "Elevation and Depth", "Shapes",
                  "Components", "Do's and Don'ts")
    for key in body_order:
        text = (sections.get(key) or "").strip()
        if not text:
            text = "- （样本未提供这一维度的证据）"
        lines += ["", "## %s" % key, "", text]
    return "\n".join(lines).rstrip() + "\n"


def self_check(style_md: str) -> List[str]:
    """离线自检（对齐 `@google/design.md lint` 的规则）：引用完整性、对比度、组件属性白名单、小节唯一。"""
    problems: List[str] = []
    fm = stylepacks.parse_front_matter(style_md)
    if not fm:
        return ["front matter 解析失败"]
    colors = fm.get("colors") or {}
    comps = fm.get("components") or {}
    refs = set()
    for name, entry in comps.items():
        if not isinstance(entry, dict):
            problems.append("组件 %s 不是对象" % name)
            continue
        for prop, val in entry.items():
            if prop not in ("backgroundColor", "textColor", "typography", "rounded", "padding", "size",
                            "height", "width"):
                problems.append("组件 %s 用了白名单外的属性 %s（lint 会告警）" % (name, prop))
            for m in re.findall(r"\{([a-zA-Z0-9_.-]+)\}", str(val)):
                refs.add(m)
    for key in colors:
        if ("colors.%s" % key) not in refs:
            problems.append("颜色令牌 colors.%s 没有被任何组件引用（orphaned-tokens）" % key)
    for name, entry in (comps or {}).items():
        if not isinstance(entry, dict):
            continue
        t_bg, t_tx = entry.get("backgroundColor"), entry.get("textColor")
        if not (t_bg and t_tx):
            continue
        def resolve(v: str) -> str:
            m = re.match(r"^\{colors\.([a-zA-Z0-9_-]+)\}$", str(v).strip())
            if m:
                return str(colors.get(m.group(1)) or "")
            return str(v)
        ratio = contrast(resolve(t_bg), resolve(t_tx))
        if ratio < 4.5:
            problems.append("组件 %s 对比度仅 %.2f:1（<4.5）" % (name, ratio))
    for token in re.findall(r"\{([a-zA-Z0-9_.-]+)\}", style_md.split("---", 2)[1] if style_md.count("---") >= 2 else ""):
        head = token.split(".")[0]
        if head not in ("colors", "typography", "rounded", "spacing", "components"):
            problems.append("未知令牌引用 {%s}（broken-ref）" % token)
    sections = re.findall(r"^##\s+(.+)$", style_md, re.M)
    if len(sections) != len(set(sections)):
        problems.append("prose 小节重名（duplicate-section）")
    return problems


# ────────────────────────── 页面挑选 ──────────────────────────

def _score_page(st: Dict[str, Any]) -> float:
    sat = sum(c["ratio"] for c in (st.get("saturated") or [])[:4])
    return sat * 2.0 + (1.0 - float(st.get("white_ratio") or 1.0))


def pick_pages(images: List[Tuple[int, str]], per_page: Dict[int, Dict[str, Any]],
               limit_min: int, limit_max: int) -> List[int]:
    """代表页挑选：封面优先，其后按「色彩/信息密度」得分取分散的几页。"""
    total = len(images)
    if total <= limit_min:
        return [p for p, _ in images]
    scored = sorted((p for p, _ in images), key=lambda p: -_score_page(per_page.get(p) or {}))
    picked: List[int] = [images[0][0]]                      # 第 1 页通常是封面
    for page in scored:
        if len(picked) >= limit_max:
            break
        if page in picked:
            continue
        if any(abs(page - q) <= 1 for q in picked) and len(picked) < limit_min:
            continue
        picked.append(page)
    for page, _ in images:                                  # 兜底凑够下限
        if len(picked) >= limit_min:
            break
        if page not in picked:
            picked.append(page)
    return sorted(picked)[:limit_max]


# ────────────────────────── analyze 主流程 ──────────────────────────

def analyze(bid: str, use_vision: bool = True, pages: Optional[List[int]] = None) -> Dict[str, Any]:
    """同步解析核心（调用方用 asyncio.to_thread）。返回可直接给界面的 result。"""
    state = _read_state(bid)
    if not state:
        raise ValueError("上传记录不存在")
    kind = state.get("kind") or "image"
    warnings: List[str] = list(state.get("warnings") or [])
    pptx_path = _pptx_path(state)

    if not page_images(bid):
        ensure_pages(bid)
    images = page_images(bid)
    if not images:
        raise ValueError("没有可用于分析的页面图（PPTX 转换或图片读取可能失败）")

    # ① 证据：主题 XML + 结构（仅 pptx）
    theme: Dict[str, Any] = {}
    struct: Dict[str, Any] = {}
    pdf_fonts: Dict[str, Any] = {}
    if kind == "pptx" and pptx_path:
        theme = _theme_evidence(pptx_path)
        if theme.get("error"):
            warnings.append("主题色板读取失败（%s），本次只靠渲染像素统计" % theme["error"])
        elif not theme.get("slots"):
            warnings.append("PPTX 没有主题色板部件，本次只靠渲染像素统计")
        struct = _structure_evidence(pptx_path)
        if struct.get("error"):
            warnings.append("形状结构统计失败（%s），字号/几何证据缺失" % struct["error"])
    elif kind == "pdf":
        try:
            pdf_fonts = _pdf_fonts(_pdf_path(state))
        except Exception as exc:
            warnings.append("PDF 嵌入字体名提取失败：%s" % str(exc)[:80])
        warnings.append("PDF 输入：没有 OOXML 主题色板与 fontScheme；" +
                        ("字体方案来自 PDF 嵌入字体名（可能不完整）" if pdf_fonts else
                         "未提取到 PDF 嵌入字体名，字体方案退化为通用档位"))
    else:
        warnings.append("图片输入：没有主题色板与形状结构，字号/字体/几何只能定性（不伪造具体值）")

    # ② 证据：像素统计（抽样，避免大文件久等）
    total_pages = len(images)
    step = max(1, total_pages // MAX_STATS_PAGES)
    sample = images[::step][:MAX_STATS_PAGES]
    if len(sample) < total_pages:
        warnings.append("像素统计抽样 %d/%d 页（大文件抽样，色值仍为真实像素值）" % (len(sample), total_pages))
    pixels = _pixel_evidence(sample)

    # ③ 色板合成
    palette, evidence = build_palette(theme, pixels, warnings)
    typo = build_typography(dict(fonts=[dict(name=n) for n in pdf_fonts["names"]]) if pdf_fonts else struct, theme, warnings)
    rounded = build_rounded(struct, warnings)
    spacing = build_spacing(struct)
    acn, accn = _color_word(palette.get("accent", ""))

    # ④ 代表页 / 视觉定性
    reps = pick_pages(images, pixels.get("per_page") or {}, PREVIEW_MIN, PREVIEW_MAX)
    vision_pages = [p for p in (pages or []) if any(p == q for q, _ in images)] or reps[:VISION_MAX_PAGES]
    vision: List[Dict[str, Any]] = []
    if use_vision:
        vp_ok = bool(config.vision_provider(with_keys=True).get("key"))
        if not vp_ok:
            warnings.append("未配置视觉模型 API Key，跳过画面定性描述（其余分析照常）")
        for page_no in vision_pages[:VISION_MAX_PAGES]:
            path = dict(images).get(page_no)
            if not path:
                continue
            res = _vision_describe(page_no, path)
            vision.append(res)
            if not res.get("ok"):
                warnings.append("第 %s 页画面识别未成功：%s" % (page_no, res.get("message") or res.get("reason")))
        if vp_ok and not any(v.get("ok") for v in vision):
            warnings.append("视觉模型全部调用失败，本次没有画面定性描述")
    else:
        warnings.append("本次按请求跳过了视觉模型（use_vision=false）")

    # ⑤ LLM 写文字（失败 → 模板）
    digest = _facts_digest("", palette, evidence, typo, rounded, spacing, struct, pixels, vision)
    prose, llm_meta = _compose_prose(digest, vision)
    llm_ok = bool(llm_meta.get("ok"))
    if not llm_ok:
        prose = _template_prose(palette, evidence, typo, rounded, spacing, struct, vision)
        reason = llm_meta.get("reason") or "call_failed"
        warnings.append("文本模型不可用（%s），prose 用模板化文字 + 实测数据填充（不影响色值与令牌）" % reason)
    else:
        tmpl = _template_prose(palette, evidence, typo, rounded, spacing, struct, vision)
        for key in ("name", "category", "summary", "overview", "colors", "typography", "layout",
                    "elevation", "shapes", "components", "prompt_md", "en_keywords", "negative"):
            if not str(prose.get(key) or "").strip():
                prose[key] = tmpl.get(key, "")
        for key in ("tags", "dos", "donts"):
            if not isinstance(prose.get(key), list) or not prose[key]:
                prose[key] = tmpl.get(key, [])

    # ⑥ 画面语言（给 prompt.md 用）：把视觉定性拼成两行
    vision_lines: List[str] = []
    for v in vision:
        if v.get("ok") and v.get("layout"):
            vision_lines.append("画面（第 %s 页）：版式 %s；图形语言 %s；留白与层级 %s。" % (
                v.get("page"), v.get("layout"), v.get("graphic_language"), v.get("hierarchy")))
            break
    for v in vision:
        if v.get("ok") and v.get("mood"):
            vision_lines.append("气质：%s。" % v["mood"])
            break
    prose["vision_lines"] = vision_lines
    if not prose.get("graphic_md"):
        prose["graphic_md"] = ""
    if not prose.get("layout_md"):
        prose["layout_md"] = ""

    # ⑦ 令牌与两个产物
    name = str(prose.get("name") or "").strip() or ("%s%s汇报风" % (acn, accn))
    hints = dict(name=name, summary=str(prose.get("summary") or "").strip())
    tokens = build_tokens(palette, typo, rounded, spacing, hints, warnings)
    sections = {
        "Overview": str(prose.get("overview") or ""),
        "Colors": str(prose.get("colors") or ""),
        "Typography": str(prose.get("typography") or ""),
        "Layout": str(prose.get("layout") or ""),
        "Elevation and Depth": str(prose.get("elevation") or ""),
        "Shapes": str(prose.get("shapes") or ""),
        "Components": str(prose.get("components") or ""),
        "Do's and Don'ts": "\n".join([str(x) for x in (prose.get("dos") or [])] +
                                    [str(x) for x in (prose.get("donts") or [])]),
    }
    style_md = render_style_md(tokens, sections)
    prompt_md = build_prompt_md(name, palette, prose, evidence, rounded, struct)
    assert len(prompt_md) <= PROMPT_LIMIT, "prompt.md 必须 ≤ %d 字符" % PROMPT_LIMIT

    problems = self_check(style_md)
    if problems:
        warnings.append("style.md 自检发现问题：" + "；".join(problems[:6]))

    suggested_id = _slug_id(acn, accn, bid) if acn != "color" else _slug_id("style", accn, bid)
    category = str(prose.get("category") or "自动提取/待分类").strip()
    tags = [str(t) for t in (prose.get("tags") or []) if str(t).strip()][:4] or ["实测提取"]
    summary = str(prose.get("summary") or "").strip()[:80]

    previews = ["/files/%s/source-pages/p%02d.png" % (_pages_pid(bid), p) for p in reps]
    result = dict(
        palette={k: v for k, v in palette.items() if isinstance(v, str)},
        evidence=dict(colors=evidence, theme=dict(file=theme.get("file", ""), name=theme.get("name", ""),
                                                  slots=theme.get("slots") or {}, fonts=theme.get("fonts") or {}),
                      structure=struct, pixels_summary=dict(
                          sampled=len(sample), total=total_pages,
                          white_ratio=[round((pixels["per_page"].get(p) or {}).get("white_ratio", 0), 3)
                                       for p in sorted(pixels["per_page"])][:24],
                          light_base=palette.get("bg", ""),
                          colors_top=[dict(hex=h, ratio=round(r["count"], 4), pages=sorted(set(r["pages"]))[:8])
                                      for h, r in sorted((pixels.get("colors") or {}).items(),
                                                         key=lambda kv: -kv[1]["count"])[:6]]),
                      vision=vision),
        summary=dict(name=name, category=category, tags=tags, summary=summary,
                     overview=str(prose.get("overview") or ""),
                     llm=dict(ok=llm_ok, **{k: v for k, v in llm_meta.items() if k in
                                            ("provider", "model", "cost_cny", "latency_ms", "reason", "message")}),
                     vision_ok=sum(1 for v in vision if v.get("ok")),
                     palette_source=dict((e["role"], e["source"]) for e in evidence)),
        style_md=style_md, prompt_md=prompt_md,
        suggested=dict(id=suggested_id, name=name, category=category, tags=tags, summary=summary),
        previews=previews, warnings=warnings, self_check=problems,
    )
    if pdf_fonts:
        result["evidence"]["pdf_fonts"] = pdf_fonts
    _write_state(bid, dict(state, kind=kind, status="analyzed", warnings=warnings, error="",
                           result=result, pages=total_pages, previews=previews, analyzed_at=_now()))
    return result


def _slug_id(primary: str, secondary: str, bid: str) -> str:
    """按色相词 + builder 短号生成候选 id（落盘前还与既有包查重）。"""
    tail = re.sub(r"[^0-9a-z]", "", bid.lower())[-4:] or "0000"
    slug = "auto-%s%s-%s" % (re.sub(r"[^a-z]", "", primary)[:10] or "style",
                             re.sub(r"[^a-z]", "", secondary)[:10], tail)
    return slug[:48]


# ────────────────────────── 保存成风格包 ──────────────────────────

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,47}$")


def save(bid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """把 analyze 结果落成 style-packs/styles/<id>/（写盘前的草稿只活在 builder 目录里）。"""
    state = _read_state(bid)
    if not state:
        raise ValueError("上传记录不存在")
    result = state.get("result") or {}
    if state.get("status") != "analyzed" or not result.get("style_md"):
        raise ValueError("还没有可保存的解析结果，请先运行 analyze")
    suggested = result.get("suggested") or {}
    sid = str(payload.get("id") or suggested.get("id") or "").strip().lower()
    if not ID_RE.match(sid):
        raise ValueError("风格包 id 不合法（只允许小写字母/数字/连字符，2~48 位）")
    dest = os.path.join(config.STYLE_DIR, "styles", sid)
    if os.path.exists(dest):
        raise ValueError("风格包 id 已存在：%s" % sid)

    name = str(payload.get("name") or suggested.get("name") or sid).strip()
    category = str(payload.get("category") or suggested.get("category") or "自动提取/待分类").strip()
    summary = str(payload.get("summary") or suggested.get("summary") or "").strip()
    tags_in = payload.get("tags") if isinstance(payload.get("tags"), list) else suggested.get("tags") or []
    tags = [str(t).strip() for t in tags_in if str(t).strip()][:6]
    style_md = str(result.get("style_md") or "")
    prompt_md = str(result.get("prompt_md") or "")
    if len(prompt_md) > PROMPT_LIMIT:
        raise ValueError("prompt.md 超过 %d 字符，拒绝落盘（render 只会取前 1500）" % PROMPT_LIMIT)

    previews_src = []
    for url in result.get("previews") or []:
        rel = url.split("/source-pages/", 1)[-1]
        path = os.path.join(_pages_dir(bid), rel)
        if os.path.isfile(path):
            previews_src.append(path)
    if not previews_src:
        previews_src = [p for _, p in page_images(bid)][:PREVIEW_MIN]

    os.makedirs(os.path.join(dest, "previews"), exist_ok=True)
    try:
        with io.open(os.path.join(dest, "style.md"), "w", encoding="utf-8") as f:
            f.write(style_md)
        with io.open(os.path.join(dest, "prompt.md"), "w", encoding="utf-8") as f:
            f.write(prompt_md)
        for index, path in enumerate(previews_src[:PREVIEW_MAX], 1):
            with Image.open(path) as im:
                im.convert("RGB").save(os.path.join(dest, "previews", "%02d.png" % index), "PNG")
        with io.open(os.path.join(dest, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(dict(name=name, category=category, tags=tags, badge="新", summary=summary),
                      f, ensure_ascii=False, indent=2)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)          # 失败不留半成品包
        raise
    cur = _read_state(bid)
    _write_state(bid, dict(cur, status="saved", saved_id=sid, saved_at=_now()))
    return dict(ok=True, style_pack=stylepacks.get_style_pack(sid))


def delete(bid: str) -> Dict[str, Any]:
    if not _read_state(bid) and not os.path.isdir(_builder_dir(bid)):
        raise ValueError("上传记录不存在")
    shutil.rmtree(_builder_dir(bid), ignore_errors=True)
    return dict(ok=True, builder_id=bid)


# ────────────────────────── 读取与作业 ──────────────────────────

def response(bid: str) -> Optional[Dict[str, Any]]:
    state = _read_state(bid)
    if not state:
        return None
    if _normalize_state(state):
        _write_state(bid, state)
    result = state.get("result") or {}
    return dict(
        builder_id=bid, kind=state.get("kind") or "", status=state.get("status") or "uploaded",
        files=[dict(name=f.get("name"), size=f.get("size")) for f in (state.get("files") or [])],
        pages=page_count(bid) or int(state.get("pages") or 0),
        result=(dict(result, previews=(result.get("previews") or []),
                     warnings=state.get("warnings") or [],
                     suggested=result.get("suggested") or {}) if result.get("style_md") else None),
        previews=result.get("previews") or [],
        saved_id=state.get("saved_id") or "",
        error=state.get("error") or "",
    )


async def run_analyze(bid: str, use_vision: bool = True, pages: Optional[List[int]] = None) -> str:
    """建作业 + 后台跑（复用 pipeline 的 job/SSE，前端进度面板零额外接线）。返回 job_id。"""
    state = _read_state(bid)
    if not state:
        raise ValueError("上传记录不存在")
    jid = pipeline.new_job(bid, "style_analyze", 1)["id"]
    _write_state(bid, dict(state, status="analyzing", error=""))
    asyncio.create_task(_analyze_worker(jid, bid, bool(use_vision), pages))
    return jid


async def _analyze_worker(jid: str, bid: str, use_vision: bool, pages: Optional[List[int]]) -> None:
    stages = [
        ("pages", "正在准备代表页（PPTX 走 LibreOffice → PDF → PyMuPDF）"),
        ("stats", "正在做主题色板与像素统计"),
        ("compose", "正在合成令牌与文字" + ("（含画面识别与文本模型）" if use_vision else "")),
    ]
    try:
        for index, (stage, message) in enumerate(stages):
            pipeline._job_update(jid, message=message)
            await pipeline.emit(jid, dict(type="progress", total=1, done=index, stage=stage,
                                          status="running", message=message))
            if index == 0:
                await asyncio.to_thread(ensure_pages, bid)
                if not page_images(bid):
                    raise ValueError("没有可分析的页面（PPTX 转换或图片读取失败）")
        result = await asyncio.to_thread(analyze, bid, use_vision, pages)
        pipeline._job_update(jid, status="done", done=1, message="解析完成，可在界面预览后保存")
        await pipeline.emit(jid, dict(type="done", done=1, total=1, stage="compose",
                                      previews=result.get("previews") or [],
                                      warnings=result.get("warnings") or []))
    except Exception as exc:                            # noqa: BLE001
        msg = "%s: %s" % (type(exc).__name__, str(exc)[:220])
        cur = _read_state(bid) or dict(builder_id=bid)
        _write_state(bid, dict(cur, status="failed", error=msg, failed_at=_now()))
        pipeline._job_update(jid, status="failed", message=msg)
        await pipeline.emit(jid, dict(type="error", message=msg, done=0, total=1))
