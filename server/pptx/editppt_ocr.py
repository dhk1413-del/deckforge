#!/usr/bin/env python3
"""离线 OCR 适配器：给 image-to-editable-ppt 的 text_hints.json 补文本。

跑在 editppt 的 venv 里（有 numpy / Pillow / onnxruntime）：
    <editppt-venv>/bin/python3 editppt_ocr.py <page_dir> --skill-root <skill_dir>

做什么：
  1. skill 的 `editppt page hints` 只测墨迹几何，不给文字；本脚本用 RapidOCR 读 source.png；
  2. 把 OCR 文本按「框」合并进标准 `text_hints.json` 的 lines[].text（几何/字号仍用 skill 的墨迹测量）；
  3. OCR 检到但墨迹没检到的行，按 OCR 框补一条，并用 skill 的 measure_crop 估字高；
  4. 已有文本（PaddleOCR hints 或真源）时直接跳过，不覆盖。

RapidOCR 未安装时 exit 2 + JSON reason，由上层回退/报错。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def fail(message: str, code: int = 2) -> int:
    print(json.dumps({"ok": False, "reason": message}, ensure_ascii=False))
    return code


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {} if default is None else default


def normalize_box(points) -> list:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    left, top = min(xs), min(ys)
    return [round(left), round(top), round(max(xs) - left), round(max(ys) - top)]


def iou(a: list, b: list) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def center(box: list) -> tuple:
    return box[0] + box[2] / 2.0, box[1] + box[3] / 2.0


def contains_center(outer: list, inner_center: tuple) -> bool:
    cx, cy = inner_center
    pad_x, pad_y = outer[2] * 0.15, outer[3] * 0.15
    return (outer[0] - pad_x) <= cx <= (outer[0] + outer[2] + pad_x) and \
           (outer[1] - pad_y) <= cy <= (outer[1] + outer[3] + pad_y)


def load_ocr():
    """返回 (recognize(image_path) -> list[dict(text, box, score)], backend, 错误原因)。"""
    try:
        from rapidocr_onnxruntime import RapidOCR  # 旧包名

        engine = RapidOCR()

        def recognize(path: str):
            result, _elapse = engine(path)
            lines = []
            for item in result or []:
                try:
                    box, text, score = item[0], item[1], item[2]
                except (IndexError, TypeError):
                    continue
                if not str(text).strip():
                    continue
                lines.append(dict(text=str(text).strip(), box=normalize_box(box), score=float(score or 0)))
            return lines

        return recognize, "rapidocr_onnxruntime", ""
    except Exception as exc:                                   # noqa: BLE001
        first_error = "%s: %s" % (type(exc).__name__, exc)
    try:
        from rapidocr import RapidOCR  # 新包名

        engine = RapidOCR()

        def recognize(path: str):
            result = engine(path)
            texts = getattr(result, "txts", None)
            boxes = getattr(result, "boxes", None)
            scores = getattr(result, "scores", None)
            if texts is None:
                return []
            lines = []
            for index, text in enumerate(texts):
                if not str(text).strip():
                    continue
                box = boxes[index] if boxes is not None else None
                if box is None:
                    continue
                lines.append(dict(text=str(text).strip(), box=normalize_box(box),
                                  score=float(scores[index] if scores is not None else 0)))
            return lines

        return recognize, "rapidocr", ""
    except Exception as exc:                                   # noqa: BLE001
        return None, "", "未安装 RapidOCR（%s；%s: %s）" % (
            "pip install rapidocr_onnxruntime", type(exc).__name__, exc)


def join_text(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    cjk = any("\u4e00" <= ch <= "\u9fff" for ch in right)
    return left + ("" if cjk else " ") + right


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill image-to-editable-ppt text_hints.json with offline OCR.")
    parser.add_argument("page_dir")
    parser.add_argument("--skill-root", required=True)
    parser.add_argument("--source", default="source.png")
    parser.add_argument("--min-score", type=float, default=0.5)
    args = parser.parse_args()

    page_dir = Path(args.page_dir).expanduser().resolve()
    source_path = page_dir / args.source
    if not source_path.is_file():
        return fail("缺少源图：%s" % source_path, 1)
    hints_path = page_dir / "text_hints.json"
    hints = load_json(hints_path, {})
    lines = hints.get("lines") or []
    if any((line.get("text") or "").strip() for line in lines):
        print(json.dumps({"ok": True, "skipped": True, "lines": len(lines),
                          "reason": "已有文字提示（PaddleOCR/真源），不覆盖"}, ensure_ascii=False))
        return 0

    recognize, backend, reason = load_ocr()
    if recognize is None:
        return fail(reason)
    try:
        ocr_lines = [line for line in recognize(str(source_path)) if line["score"] >= args.min_score]
    except Exception as exc:                                   # noqa: BLE001
        return fail("RapidOCR 识别失败：%s: %s" % (type(exc).__name__, exc), 1)
    if not ocr_lines:
        return fail("RapidOCR 没有识别到文字（可能是纯图形页）", 1)

    runtime = Path(args.skill_root).expanduser().resolve() / "cli" / "editppt" / "runtime"
    sys.path.insert(0, str(runtime))
    try:
        from page_text_metrics import load_gray, measure_crop
        from text_hints import attach_font_sizes, draw_overlay
    except Exception as exc:                                   # noqa: BLE001
        return fail("无法导入 skill 的提示工具：%s: %s" % (type(exc).__name__, exc), 1)

    request = load_json(page_dir / "page_request.json", {})
    source = hints.get("source") or {}
    if not source.get("width_px") or not source.get("height_px"):
        source = dict(width_px=0, height_px=0)
    gray = load_gray(source_path)
    source["width_px"], source["height_px"] = gray.shape[1], gray.shape[0]
    manifest_like = {"source": source}
    for key in ("slide", "content_box"):
        if request.get(key):
            manifest_like[key] = request[key]
    if "slide" not in manifest_like:
        manifest_like["slide"] = {"width": 13.333, "height": 7.5}

    matched = 0
    added = 0
    unused = list(ocr_lines)
    for hint in lines:
        box = hint.get("box_px") or []
        if len(box) != 4 or (hint.get("text") or "").strip():
            continue
        best = None
        best_score = 0.0
        for ocr in unused:
            score = iou(box, ocr["box"])
            if score > best_score:
                best, best_score = ocr, score
        if best is None or best_score < 0.2:
            candidates = [ocr for ocr in unused if contains_center(ocr["box"], center(box))]
            if candidates:
                best = max(candidates, key=lambda ocr: ocr["score"])
            else:
                continue
        hint["text"] = best["text"]
        matched += 1
        unused.remove(best)

    for ocr in unused:
        left, top, width, height = ocr["box"]
        if width < 4 or height < 4:
            continue
        pad_x, pad_y = max(2, int(width * 0.02)), max(1, int(height * 0.05))
        box = [max(0, left - pad_x), max(0, top - pad_y),
               min(gray.shape[1], left + width + pad_x) - max(0, left - pad_x),
               min(gray.shape[0], top + height + pad_y) - max(0, top - pad_y)]
        glyph = max(6.0, height * 0.72)
        try:
            measured = measure_crop(gray[max(0, box[1]):box[1] + box[3], max(0, box[0]):box[0] + box[2]],
                                    clean_border=False)
            if measured.get("ok"):
                glyph = float(measured["glyph_height_px"])
        except Exception:                                      # noqa: BLE001
            pass
        lines.append(dict(text=ocr["text"], box_px=box, glyph_height_px=round(glyph, 1), line_count=1))
        added += 1

    lines.sort(key=lambda line: (line.get("box_px", [0, 0])[1], line.get("box_px", [0, 0])[0]))
    for index, line in enumerate(lines, 1):
        line["id"] = "L%02d" % index
    attach_font_sizes(lines, manifest_like)
    for line in lines:
        if "font_pt_if_cjk" in line:
            line["font_pt"] = line["font_pt_if_cjk"] if any("\u4e00" <= ch <= "\u9fff" for ch in line.get("text", "")) \
                else line["font_pt_if_latin"]

    payload = dict(
        schema_version=1,
        backend=backend,
        source={"width_px": source["width_px"], "height_px": source["height_px"]},
        lines=lines,
        note=("OCR 文本提示（离线 RapidOCR）：lines[].text 为识别结果，可能有识别错误；"
              "box_px/font_pt 来自本地墨迹测量。文字请结合源图核对，不得编造。"),
    )
    hints_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        draw_overlay(Image.open(source_path), lines, page_dir / "text_hints.png")
    except Exception:                                          # noqa: BLE001 —— overlay 只是辅助
        pass
    print(json.dumps({"ok": True, "backend": backend, "lines": len(lines),
                      "matched": matched, "added": added}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    # draw_overlay 需要 PIL.Image
    from PIL import Image
    raise SystemExit(main())
