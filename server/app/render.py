# -*- coding: utf-8 -*-
"""Prompt 拼装（base-prompt 六段式）+ 本地兜底渲染器（Pillow，16:9 PNG）。

本地兜底渲染的作用（验收 17）：**零 key 也能跑通整条链路** —— 把结构化内容按风格令牌画成整页图，
provider 记为 local_render、成本 0。它不是"占位图"，而是真的按版式与色板出图。
"""
import glob
import os
import re
import subprocess
import warnings
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from . import stylepacks

# ────────────────────────── 字体 ──────────────────────────
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Light.ttc",
]


def _font_candidates():
    yield from FONT_CANDIDATES
    windows_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    for name in ("msyh.ttc", "msyhbd.ttc", "simsun.ttc", "simhei.ttf"):
        yield os.path.join(windows_fonts, name)
    for command in (
        ["fc-match", "-f", "%{file}\t%{lang}\n", "sans-serif:lang=zh-cn"],
        ["fc-list", ":lang=zh", "-f", "%{file}\n"],
    ):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                path, _, languages = line.partition("\t")
                if command[0] == "fc-list" or any(
                    lang == "zh" or lang.startswith("zh-") for lang in languages.split("|")
                ):
                    yield path
    for root in ("/usr/share/fonts", "/usr/local/share/fonts",
                 os.path.expanduser("~/.local/share/fonts"), os.path.expanduser("~/.fonts")):
        for pattern in ("NotoSansCJK-*.ttc", "NotoSansSC*", "NotoSerifCJK*", "wqy*", "SourceHan*"):
            yield from sorted(glob.glob(os.path.join(root, "**", pattern), recursive=True))


_FONT_PATH: Optional[str] = None
_FONT_RESOLVED = False
_FONT_CACHE: Dict[int, ImageFont.FreeTypeFont] = {}
_FONT_WARNING_EMITTED = False


def _font(size: int) -> ImageFont.FreeTypeFont:
    global _FONT_PATH, _FONT_RESOLVED, _FONT_WARNING_EMITTED
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    if not _FONT_RESOLVED:
        for path in _font_candidates():
            if os.path.isfile(path):
                try:
                    font = ImageFont.truetype(path, size)
                except (OSError, ValueError):
                    continue
                _FONT_PATH = path
                _FONT_CACHE[size] = font
                break
        _FONT_RESOLVED = True
    if size not in _FONT_CACHE:
        if _FONT_PATH is not None:
            _FONT_CACHE[size] = ImageFont.truetype(_FONT_PATH, size)
        else:
            if not _FONT_WARNING_EMITTED:
                _FONT_WARNING_EMITTED = True
                warnings.warn("No usable CJK font found; local rendering may show missing Chinese glyphs.",
                              RuntimeWarning, stacklevel=2)
            _FONT_CACHE[size] = ImageFont.load_default()
    return _FONT_CACHE[size]


# ────────────────────────── Prompt 拼装 ──────────────────────────

NEGATIVE = ("不要水印、不要 logo、不要页码、不要二维码、不要署名、不要乱码；"
            "文字必须清晰可读、不重叠、不出画布、不被裁切；不得改写文字、不得用同音字近形字替换、不得凭空加字；"
            "不要装饰性英文、不要 Lorem ipsum；所有元素留在画布内且四周留足安全边距（≥ 画幅宽 7%），不要贴边或压边。")


def assemble_prompt(style: Dict[str, Any], layout_key: str, content: Dict[str, Any], size: str = "2K") -> str:
    """按 base-prompt.md 的六段式顺序拼装：任务 → 版面 → 视觉 → 令牌 → 必须上屏文字 → 硬约束 → 输出。"""
    tokens = style.get("tokens", {}) or {}
    colors = tokens.get("colors", {}) or {}
    layout = stylepacks.layout_body(layout_key) or stylepacks.layout_body("cards_4")
    visual = (style.get("prompt_md") or "").strip()[:1500]
    px = {"1K": "1024×576", "2K": "2048×1152", "3K": "3072×1728", "4K": "4096×2304"}.get(size.upper(), "2048×1152")

    def q(text: str) -> str:
        return "「%s」" % (text or "").strip()

    lines = [
        "【任务】生成一张 16:9 的整页 PPT 幻灯片图片，只生成这一页，不要多页拼图或缩略图阵列。",
        "",
        "【版面结构】按下列槽位摆放内容，严格保持层级与相对位置：",
        _brief(layout, 900),
        "",
        "【视觉风格】",
        visual or "干净、克制、专业。",
        "",
        "【配色与字体层级】（来自风格包令牌，务必服从）",
        "- 背景 %s；卡片/色块 %s；正文 %s；次要文字 %s；强调色 %s；次强调 %s" % (
            colors.get("bg", colors.get("neutral", "#FFFFFF")), colors.get("surface", "#FFFFFF"),
            colors.get("ink", "#1E232E"), colors.get("ink-sub", colors.get("secondary", "#666666")),
            colors.get("accent", colors.get("primary", "#1E78FA")),
            colors.get("accent-2", colors.get("tertiary", "#26ABFE"))),
        "- 标题层级由大到小 3~4 级；正文统一字号；数字可用等宽字形",
        "",
        "【版心与比例】（宁松勿挤，精致优先）",
        "- 四周安全留白 ≥ 画幅宽的 7%（2K 画幅约 144px）；任何文字、图形、卡片都不得贴边或压边",
        "- 标题字号约画幅高的 6%~8%，正文约 2.2%~2.8%，数字与正文同档；层级清晰、留白充分",
        "- 元素尺寸克制、细节精致：细线、小图标、克制投影；不要超大字号、不要大色块铺满、不要元素拥挤",
        "",
        "【必须上屏的文字（逐字复制，不得改写、增删、翻译）】",
    ]
    if content.get("title"):
        lines.append("1) 标题：%s" % q(content["title"]))
    if content.get("subtitle"):
        lines.append("2) 副标题：%s" % q(content["subtitle"]))
    for i, p in enumerate(content.get("points") or [], 1):
        lines.append("%d) 要点：%s" % (i + 2, q(p)))
    if content.get("must_keep"):
        lines.append("数字与专有名词必须原样保留：%s" % "、".join(q(str(x)) for x in content["must_keep"]))
    lines += ["", "【硬约束】", NEGATIVE, "数字、百分比、单位、年份、来源与合计必须逐字保留；待统计与缺失值不得推断为 0。不要绘制数据坐标轴或图表，用原文文字呈现数据；图表由代码单独渲染。", "", "【输出】16:9，%s" % px]
    return "\n".join(lines)


def _brief(md: str, limit: int) -> str:
    keep = []
    for line in md.split("\n"):
        s = line.strip()
        if s.startswith("#") or s.startswith("- **用途**") or s.startswith("- **栅格**") or re.match(r"^\d+\.", s):
            keep.append(s)
    return "\n".join(keep)[:limit]


# ────────────────────────── 本地兜底渲染 ──────────────────────────

def _hex(c: str, default: str = "#FFFFFF") -> Tuple[int, int, int]:
    c = (c or default).lstrip("#")
    if len(c) != 6:
        c = default.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))          # type: ignore[return-value]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    out: List[str] = []
    line = ""
    for ch in str(text):
        if ch == "\n":
            out.append(line); line = ""; continue
        if draw.textlength(line + ch, font=font) <= max_w:
            line += ch
        else:
            out.append(line); line = ch
    if line:
        out.append(line)
    return out


def local_render(content: Dict[str, Any], style: Dict[str, Any], out_path: str,
                 size: str = "2K", page_no: int = 1, total: int = 1,
                 layout_key: str = "cards_4", project_title: str = "") -> Tuple[int, int]:
    """把结构化内容按风格令牌与版式画成整页 PNG。返回 (w, h)。"""
    W, H = {"1K": (1024, 576), "2K": (2048, 1152), "3K": (3072, 1728), "4K": (4096, 2304)}.get(
        size.upper(), (2048, 1152))
    tokens = (style.get("tokens") or {}).get("colors", {}) or {}
    bg = _hex(tokens.get("bg", tokens.get("neutral", "#FFFFFF")))
    surface = _hex(tokens.get("surface", "#F6F7F9"))
    accent = _hex(tokens.get("accent", tokens.get("primary", "#1E78FA")))
    accent2 = _hex(tokens.get("accent-2", tokens.get("tertiary", "#26ABFE")))
    ink = _hex(tokens.get("ink", "#1E232E"))
    ink_sub = _hex(tokens.get("ink-sub", tokens.get("secondary", "#666666")))

    s = W / 2048.0                                   # 以 2K 为基准的缩放系数
    def px(v: float) -> int:
        return max(1, int(v * s))

    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    margin = px(120)
    title_f = _font(px(74))
    h2_f = _font(px(48))
    body_f = _font(px(38))
    small_f = _font(px(28))
    num_f = _font(px(96))

    title = (content.get("title") or project_title or "").strip()
    points = [str(x) for x in (content.get("points") or []) if str(x).strip()]
    subtitle = (content.get("subtitle") or "").strip()

    # 顶部强调条
    d.rectangle([0, 0, W, px(10)], fill=accent)

    if layout_key == "cover":
        d.rectangle([margin, px(360), margin + px(8), px(300 + 260)], fill=accent)
        y = px(300)
        for ln in _wrap(d, title, title_f, W - 2 * margin)[:3]:
            d.text((margin + px(36), y), ln, font=title_f, fill=ink); y += px(96)
        if subtitle:
            y += px(24)
            for ln in _wrap(d, subtitle, h2_f, int(W * 0.7))[:3]:
                d.text((margin + px(36), y), ln, font=h2_f, fill=ink_sub); y += px(64)
        d.text((margin, H - px(150)), (content.get("meta") or ""), font=small_f, fill=ink_sub)
    elif layout_key == "section":
        idx = content.get("index") or str(page_no).zfill(2)
        d.text((margin, px(330)), str(idx), font=num_f, fill=accent)
        yy = px(500)
        for ln in _wrap(d, title, title_f, W - 2 * margin)[:2]:
            d.text((margin, yy), ln, font=title_f, fill=ink); yy += px(96)
    else:
        # 通用页：标题 + 要点（卡片 / 双栏 / 图表 / 时间线 / 总结 的差异化排版）
        y = margin
        for ln in _wrap(d, title, title_f, W - 2 * margin)[:2]:
            d.text((margin, y), ln, font=title_f, fill=ink); y += px(92)
        y += px(20)
        d.rectangle([margin, y, margin + px(120), y + px(6)], fill=accent)
        y += px(50)

        area_top = y
        area_h = H - area_top - px(110)
        if layout_key == "cards_4" and points:
            n = min(4, len(points))
            gap = px(28)
            cw = (W - 2 * margin - gap * (n - 1)) // n
            for i in range(n):
                x0 = margin + i * (cw + gap)
                d.rounded_rectangle([x0, area_top, x0 + cw, area_top + area_h], radius=px(20), fill=surface)
                d.rounded_rectangle([x0, area_top, x0 + cw, area_top + px(10)], radius=px(5), fill=accent if i % 2 == 0 else accent2)
                ty = area_top + px(40)
                for ln in _wrap(d, points[i], body_f, cw - px(48))[:10]:
                    d.text((x0 + px(24), ty), ln, font=body_f, fill=ink); ty += px(56)
        elif layout_key == "comparison_2col" and len(points) >= 2:
            half = (len(points) + 1) // 2
            cols = [points[:half], points[half:]]
            gap = px(40)
            cw = (W - 2 * margin - gap) // 2
            for ci, items in enumerate(cols):
                x0 = margin + ci * (cw + gap)
                d.rounded_rectangle([x0, area_top, x0 + cw, area_top + area_h], radius=px(20), fill=surface)
                d.rectangle([x0, area_top, x0 + cw, area_top + px(12)], fill=accent if ci == 0 else accent2)
                ty = area_top + px(50)
                for it in items:
                    for ln in _wrap(d, "· " + it, body_f, cw - px(56))[:4]:
                        d.text((x0 + px(28), ty), ln, font=body_f, fill=ink); ty += px(54)
                    ty += px(10)
        elif layout_key == "data_chart" and points:
            left_w = int(W * 0.42)
            ty = area_top
            for it in points[:6]:
                for ln in _wrap(d, "· " + it, body_f, left_w - margin - px(20))[:3]:
                    d.text((margin, ty), ln, font=body_f, fill=ink); ty += px(52)
                ty += px(8)
            # 数据图表由唯一原生渲染器绘制。转换不可用时只呈现原文，绝不把缺失值转成 0。
            d.text((margin + left_w, area_top), "数据来源：本页要点原文", font=small_f, fill=ink_sub)
            d.text((margin + left_w, area_top + px(52)), "图表未绘制，请核对原文", font=small_f, fill=ink_sub)
        elif layout_key == "timeline" and points:
            n = min(5, len(points))
            axis_y = area_top + px(80)
            d.rectangle([margin + px(20), axis_y, W - margin - px(20), axis_y + px(6)], fill=accent2)
            seg = (W - 2 * margin - px(40)) // max(1, n - 1) if n > 1 else 0
            for i in range(n):
                x0 = margin + px(20) + i * seg
                d.ellipse([x0 - px(16), axis_y - px(13), x0 + px(16), axis_y + px(19)], fill=accent)
                ty = axis_y + px(50)
                for ln in _wrap(d, points[i], body_f, int(seg * 0.92) if seg else px(400))[:6]:
                    d.text((x0 - px(10), ty), ln, font=body_f, fill=ink); ty += px(54)
        else:                                        # summary / 未知版式
            ty = area_top
            for i, it in enumerate(points[:4] or [title]):
                d.text((margin, ty), "%02d" % (i + 1), font=h2_f, fill=accent)
                for ln in _wrap(d, it, h2_f, W - 2 * margin - px(140))[:3]:
                    d.text((margin + px(140), ty), ln, font=h2_f, fill=ink); ty += px(66)
                ty += px(24)

    # 页脚：项目名 + 页码（等宽观感）
    d.text((margin, H - px(80)), (project_title or "")[:40], font=small_f, fill=ink_sub)
    d.text((W - margin - px(90), H - px(80)), "%d / %d" % (page_no, total), font=small_f, fill=ink_sub)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")
    return W, H
