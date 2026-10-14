# -*- coding: utf-8 -*-
"""风格包加载器：读 style-packs/（B+C 混合形态）。

  styles/<id>/style.md   —— DESIGN.md 格式（YAML 令牌 + prose）
  styles/<id>/prompt.md  —— 画面语言（给生图模型）
  layouts/<key>.md       —— 版式槽位
  base-prompt.md         —— 拼装模板
"""
import io
from copy import deepcopy
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import yaml

from .config import STYLE_DIR

# 风格包静态资源（封面/预览图）对外 URL 前缀；main.py 把 STYLE_DIR/styles 挂到这里
ASSET_URL = "/style-assets"

# 「风格构建」运行时新建的包用它携带展示名/分类/标签（优先级高于下面的内置 META）
META_FILE = "meta.json"

# 中文展示名与分类（目录名 → 展示），未知时按目录名兜底
META = {
    "violet-gradient": dict(name="紫蓝渐变风", category="科技/现代", tags=["渐变", "现代", "产品"], badge="新",
                            summary="紫蓝渐变 + 大圆角卡片 + 柔和浅色渐变卡面，现代 AI 产品气质"),
    "tech-deepblue": dict(name="深蓝光感科技发布风", category="科技/深色", tags=["科技", "深色"], badge="热门",
                          summary="深空底 + 冷蓝渐变，发布会/技术方案气质"),
    "biz-bluegold": dict(name="商务蓝金汇报风", category="商务/汇报", tags=["商务", "汇报"], badge="",
                         summary="纯白底 + 深蓝主色 + 克制金饰，政务/国央汇报"),
    "med-teal": dict(name="医疗青蓝专业风", category="医疗/医药", tags=["医疗", "学术"], badge="推荐",
                     summary="洁净白底 + 青蓝主色 + 绿色安全点缀，临床/护理/培训"),
    "biz-blueorange": dict(name="双蓝橙活力汇报风", category="商务/汇报", tags=["汇报", "活力", "双色"], badge="新",
                           summary="白底亮宝蓝 + 深蓝渐变 + 橙色点睛，编号圆点驱动的逻辑图汇报气质"),
    "biz-bluegreen": dict(name="双蓝绿清新汇报风", category="商务/汇报", tags=["汇报", "清新", "双色"], badge="新",
                          summary="白底深蓝 + 亮蓝次级 + 黄绿点睛，深色视觉封面，逻辑图汇报气质"),
}


def _read(path: str) -> str:
    return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def parse_front_matter(md: str) -> Dict[str, Any]:
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def _tokens_flat(fm: Dict[str, Any]) -> Dict[str, Any]:
    """把 style.md 的令牌拍平成前端好用的结构。"""
    colors = fm.get("colors", {}) or {}
    typo = fm.get("typography", {}) or {}
    return dict(colors=colors, typography=typo, rounded=fm.get("rounded", {}), spacing=fm.get("spacing", {}))


def _meta_for(sid: str, fm: Dict[str, Any]) -> Dict[str, Any]:
    """展示元信息：`styles/<id>/meta.json`（「风格构建」运行时新建的包）优先，
    其次是内置 META，最后由调用处回落 style.md 的 front matter。"""
    data: Dict[str, Any] = {}
    path = os.path.join(STYLE_DIR, "styles", sid, META_FILE)
    if os.path.exists(path):
        try:
            with io.open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:                                  # noqa: BLE001
            data = {}
    out = dict(META.get(sid, {}))
    for key in ("name", "category", "tags", "badge", "summary"):
        value = data.get(key)
        if value not in (None, "", []):
            out[key] = value
    return out


_LIST_CACHE = None
_LAYOUT_CACHE = None


def _dir_stamp(path: str):
    try:
        stat = os.stat(path)
        return (path, stat.st_mtime_ns, stat.st_ino)
    except OSError:
        return (path, None, None)


def _preview_files(sid: str) -> tuple[str, List[str]]:
    """本机私有预览优先；覆盖目录无图片时沿用公开示例。"""
    d = os.path.join(STYLE_DIR, "styles", sid)
    for dir_name in ("previews-local", "previews"):
        pv = os.path.join(d, dir_name)
        files = [f for f in sorted(os.listdir(pv)) if f.lower().endswith((".png", ".jpg"))] if os.path.isdir(pv) else []
        if files or dir_name == "previews":
            return dir_name, files


def _pack_summary(sid: str, style_md: str) -> Dict[str, Any]:

    fm = parse_front_matter(style_md)
    colors = fm.get("colors", {}) or {}
    meta = _meta_for(sid, fm)
    preview_dir, previews = _preview_files(sid)
    cover = "cover.png" if "cover.png" in previews else (previews[0] if previews else "")
    return dict(
        id=sid,
        name=meta.get("name") or fm.get("name") or sid,
        category=meta.get("category", "未分类"),
        tags=meta.get("tags", []),
        badge=meta.get("badge", ""),
        summary=meta.get("summary") or (fm.get("description") or "")[:60],
        accent=colors.get("accent") or colors.get("tertiary") or "#1E78FA",
        bg=colors.get("bg") or colors.get("neutral") or "#FFFFFF",
        ink=colors.get("ink", "#1E232E"),
        layouts=available_layouts(),
        cover=("%s/%s/%s/%s" % (ASSET_URL, sid, preview_dir, quote(cover))) if cover else "",
        previews=["%s/%s/%s/%s" % (ASSET_URL, sid, preview_dir, quote(f)) for f in previews],
        preview_count=len(previews),
        source_type="system",
        version="1",
    )



def list_style_packs() -> List[Dict[str, Any]]:
    global _LIST_CACHE
    styles_dir = os.path.join(STYLE_DIR, "styles")
    style_ids = sorted(entry.name for entry in os.scandir(styles_dir) if entry.is_dir()) if os.path.isdir(styles_dir) else []
    pack_stamps = tuple(
        tuple(_dir_stamp(os.path.join(styles_dir, sid, subdir)) for subdir in ("", "previews", "previews-local"))
        for sid in style_ids
    )
    stamp = (_dir_stamp(styles_dir), _dir_stamp(os.path.join(STYLE_DIR, "layouts")), pack_stamps)
    if _LIST_CACHE is not None and _LIST_CACHE[0] == stamp:
        return deepcopy(_LIST_CACHE[1])
    out = []
    for sid in style_ids:
        d = os.path.join(styles_dir, sid)
        out.append(_pack_summary(sid, _read(os.path.join(d, "style.md"))))
    _LIST_CACHE = (stamp, out)
    return deepcopy(out)


def get_style_pack(sid: str) -> Optional[Dict[str, Any]]:
    # A style id is one directory name, never a path into a sibling directory.
    if not sid or sid in (".", "..") or os.path.basename(sid) != sid:
        return None
    d = os.path.join(STYLE_DIR, "styles", sid)
    if not os.path.isdir(d):
        return None
    style_md = _read(os.path.join(d, "style.md"))
    sp = _pack_summary(sid, style_md)
    sp["style_md"] = style_md
    sp["prompt_md"] = _read(os.path.join(d, "prompt.md"))
    sp["tokens"] = _tokens_flat(parse_front_matter(style_md))
    return sp


def available_layouts() -> List[str]:
    global _LAYOUT_CACHE
    ld = os.path.join(STYLE_DIR, "layouts")
    stamp = (_dir_stamp(ld), _dir_stamp(os.path.join(STYLE_DIR, "styles")))
    if _LAYOUT_CACHE is None or _LAYOUT_CACHE[0] != stamp:
        layouts = sorted(f[:-3] for f in os.listdir(ld) if f.endswith(".md")) if os.path.isdir(ld) else []
        _LAYOUT_CACHE = (stamp, layouts)
    return list(_LAYOUT_CACHE[1])


LAYOUT_TITLES = {
    "cover": "封面", "section": "章节过渡", "cards_4": "并列要点/卡片栅格",
    "comparison_2col": "左右对比", "data_chart": "数据/图表页", "timeline": "流程/时间线", "summary": "总结/结语",
}


def list_layouts() -> List[Dict[str, Any]]:
    out = []
    for key in available_layouts():
        body = _read(os.path.join(STYLE_DIR, "layouts", "%s.md" % key))
        slots = re.findall(r"^\s*\d+\.\s*`([a-zA-Z_0-9\[\]]+)`", body, re.M)
        best = ""
        m = re.search(r"-\s*\*\*用途\*\*：(.*)", body)
        if m:
            best = m.group(1).strip()
        out.append(dict(key=key, title=LAYOUT_TITLES.get(key, key), best_for=best, slots=slots,
                        body=body))
    return out


def layout_body(key: str) -> str:
    return _read(os.path.join(STYLE_DIR, "layouts", "%s.md" % key))
