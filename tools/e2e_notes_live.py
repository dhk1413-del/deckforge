# -*- coding: utf-8 -*-
"""PPT 备注模块真机端到端验收（会真的调视觉模型与 DeepSeek，花钱但极少）。

流程：上传 → 解析页清单 → 画面识别 → 写备注 → 导出 → 回读导出文件逐项复核。

用法：
  .venv/bin/python tools/e2e_notes_live.py <文件.pptx> [--vision auto|all|off] [--pages 4,16,33] [--yes]
  不带 --pages 就是全篇（64 页大约 15~25 分钟）。

复核口径（不看接口返回，只回读产物）：
  · 导出的 pptx 页数 = 原文件页数
  · 每页形状数、媒体文件数与原文件一致（版式/图片未被改动）
  · 写过备注的页 notes 非空，且原有备注仍在 AI 备注上方
  · 原文件字节数未变（我们只读它）
"""
import argparse
import json
import os
import sys
import time

import httpx
from pptx import Presentation

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ.get("DECKFORGE_BASE", "http://127.0.0.1:8641")
NOTE_MARKER = "【演讲备注】"


def wait_job(client: httpx.Client, job_id: str, label: str, quiet: bool = False) -> str:
    """订阅 SSE 直到 done/error，返回终态。"""
    t0 = time.time()
    last = ""
    with client.stream("GET", "%s/api/jobs/%s/stream" % (BASE, job_id), timeout=httpx.Timeout(30, read=3600)) as r:
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            t = ev.get("type")
            if t == "progress":
                msg = "%s [%s] P%s %s" % (label, ev.get("stage"), ev.get("page") or "-", ev.get("message") or "")
                if not quiet or ev.get("status") in ("done", "failed"):
                    print("   %6.0fs %s" % (time.time() - t0, msg), flush=True)
                last = msg
            elif t == "done":
                print("   %6.0fs %s 完成：%s" % (time.time() - t0, label, ev.get("message") or ""))
                return "done"
            elif t == "error":
                print("   %6.0fs %s 失败：%s" % (time.time() - t0, label, ev.get("message")))
                return "error"
    return "closed"


def shape_stats(prs) -> dict:
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    per_page, pics = [], 0
    for s in list(prs.slides):
        per_page.append(len(s.shapes))
        for sh in s.shapes:
            try:
                if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    pics += 1
            except Exception:
                pass
    return dict(pages=len(per_page), shapes=per_page, pics=pics)


def run_existing(args) -> int:
    """复用已有任务：补齐识别 + 写全部备注 + 导出复核（验证「中断后可续跑，不重跑已完成页」）。"""
    nid = args.nid
    with httpx.Client(timeout=600, trust_env=False) as c:
        r = c.get("%s/api/notes/%s" % (BASE, nid))
        if r.status_code != 200:
            print("任务不存在：%s" % r.text[:200])
            return 1
        det0 = r.json()
        print("任务 %s：%s（%d 页）" % (nid, det0["title"], det0["pages"]))
        already = det0["notes_done"]
        print("现状：已写备注 %d 页，已识别 %d 页 → 接着跑，已完成的页不会重跑"
              % (already, sum(1 for p in det0["pages_detail"] if p["vision_status"] == "done")))

        print("\n② 补齐画面识别（vision=%s）" % args.vision)
        r = c.post("%s/api/notes/%s/analyze" % (BASE, nid), json={"vision_mode": args.vision})
        if r.status_code != 200:
            print("   启动失败：%s" % r.text[:300])
            return 1
        if wait_job(c, r.json()["job_id"], "识别") == "error":
            return 1

        print("\n③ 写全部备注（only_missing：已完成的页不入队，验证续跑不重复花钱）")
        r = c.post("%s/api/notes/%s/generate" % (BASE, nid), json={"only_missing": True})
        if r.status_code != 200:
            print("   启动失败：%s" % r.text[:300])
            return 1
        if wait_job(c, r.json()["job_id"], "备注") == "error":
            return 1

        return report(c, nid, det0.get("source_path") or "")


def report(c: httpx.Client, nid: str, src_hint: str = "") -> int:
    """回读导出产物逐项复核（不看接口返回，只看 pptx 文件本身）。"""
    print("\n④ 页面清单复核")
    det = c.get("%s/api/notes/%s" % (BASE, nid)).json()
    pg = det["pages_detail"]
    done = [p for p in pg if p["note_status"] == "done" and p["note"].strip()]
    failed = [p for p in pg if p["note_status"] == "failed"]
    vis_fail = [p for p in pg if p["vision_status"] == "failed"]
    print("   已写备注 %d/%d 页 ｜ 识别失败 %d 页 ｜ 备注失败页 %s"
          % (len(done), len(pg), len(vis_fail), [p["page_no"] for p in failed] or "无"))
    print("   累计花费 ¥%.4f" % det["cost_cny"])
    lens = [len(p["note"]) for p in done]
    short = [p for p in done if p["low_info"] == 1 and len(p["note"]) <= 60]
    print("   篇幅：平均 %.0f 字，最短 %d、最长 %d；图片页写成一句话的有 %d 页（要求 ≤40 字左右）"
          % (sum(lens) / max(1, len(lens)), min(lens or [0]), max(lens or [0]), len(short)))

    print("\n⑤ 导出并回读复核")
    r = c.post("%s/api/notes/%s/export" % (BASE, nid), json={"keep_original": True})
    if r.status_code != 200:
        print("   导出失败：%s" % r.text[:300])
        return 1
    exp = r.json()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "data", "files", "exports", exp["name"])
    src = src_hint or det.get("source_path", "")
    ok = True
    if not os.path.exists(out):
        print("   产物不存在：%s" % out)
        return 1
    after_prs = Presentation(out)
    after = shape_stats(after_prs)
    after_notes = [s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
                   for s in list(after_prs.slides)]
    print("   产物：%s（%.1f MB，%d 页）" % (os.path.basename(out), os.path.getsize(out) / 1048576, after["pages"]))
    if src and os.path.exists(src):
        src_prs = Presentation(src)
        before = shape_stats(src_prs)
        orig_notes = [s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
                      for s in list(src_prs.slides)]
        before_bytes = os.path.getsize(src)
        for name, cond, d in [
            ("页数一致", after["pages"] == before["pages"], "%s vs %s" % (after["pages"], before["pages"])),
            ("每页形状数一致（版式未被动）", after["shapes"] == before["shapes"],
             "不一致页：%s" % [i + 1 for i, (a, b) in enumerate(zip(after["shapes"], before["shapes"])) if a != b]),
            ("图片总数一致", after["pics"] == before["pics"], "%s vs %s" % (after["pics"], before["pics"])),
            ("原文件未被改动", os.path.getsize(src) == before_bytes, ""),
        ]:
            print("   %s %s%s" % ("✓" if cond else "✗", name, "" if cond else "  —— " + str(d)))
            ok = ok and cond
        lost = [i for i, o in enumerate(orig_notes, 1) if o and o[:15] not in after_notes[i - 1]]
        print("   %s 原有备注全部保留（%d 页）%s" % ("✓" if not lost else "✗",
                                                  sum(1 for o in orig_notes if o), "" if not lost else "丢失：%s" % lost))
        ok = ok and not lost
        kept = sum(1 for i, o in enumerate(orig_notes, 1) if o and NOTE_MARKER in after_notes[i - 1])
        print("   ✓ 原文 + AI 备注并存的页：%d" % kept)
    missing = [p["page_no"] for p in done if p["note"].strip()[:20] not in after_notes[p["page_no"] - 1]]
    print("   %s 每页备注都写进了产物%s" % ("✓" if not missing else "✗", "" if not missing else "  缺：%s" % missing))
    ok = ok and not missing
    print("   ✓ 产物里有备注的页：%d" % sum(1 for t in after_notes if t))

    print("\n⑥ 抽样看备注（人眼判质量）")
    picks = [p for p in pg if p["low_info"] == 1][:2] + [p for p in pg if p["low_info"] == 0 and p["note"].strip()][:2]
    for p in picks:
        print("   ── P%s %s（%d 字）" % (p["page_no"], "图片页" if p["low_info"] else "文字页", len(p["note"])))
        print("      " + p["note"][:280].replace("\n", " "))
    print("\n%s" % ("全部复核通过 ✅" if ok else "复核有未通过项 ❌"))
    print("网页：%s/#/notes/%s" % (BASE, nid))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx", nargs="?", default="")
    ap.add_argument("--vision", default="auto", choices=["auto", "all", "off"])
    ap.add_argument("--pages", default="")
    ap.add_argument("--nid", default="", help="复用已有任务继续跑（验证中断续跑）")
    ap.add_argument("--yes", action="store_true", help="不确认直接跑")
    args = ap.parse_args()

    if args.nid:
        return run_existing(args)
    if not args.pptx:
        print("请给一个 .pptx 路径，或用 --nid 复用已有任务")
        return 2
    src = os.path.abspath(args.pptx)
    if not os.path.exists(src):
        print("文件不存在：%s" % src)
        return 2
    pages = [int(x) for x in args.pages.split(",") if x.strip()] if args.pages else []
    scope = ("这些页：" + ",".join(map(str, pages))) if pages else "全部页"
    print("文件：%s（%.1f MB）" % (os.path.basename(src), os.path.getsize(src) / 1048576))
    print("范围：%s ｜ 画面识别：%s ｜ 服务：%s" % (scope, args.vision, BASE))
    if not args.yes:
        if input("确认开始？（会真实调用模型）[y/N] ").strip().lower() != "y":
            return 0

    before_prs = Presentation(src)
    before = shape_stats(before_prs)
    before_bytes = os.path.getsize(src)
    orig_notes = [s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
                  for s in list(before_prs.slides)]
    del before_prs

    with httpx.Client(timeout=600, trust_env=False) as c:
        print("\n① 上传")
        with open(src, "rb") as f:
            r = c.post("%s/api/notes/upload" % BASE, files={"file": (os.path.basename(src), f,
                       "application/vnd.openxmlformats-officedocument.presentationml.presentation")})
        if r.status_code != 200:
            print("   上传失败 HTTP %s：%s" % (r.status_code, r.text[:300]))
            return 1
        detail = r.json()
        nid = detail["id"]
        print("   任务 %s：%d 页，图片页 %d，已有备注 %d 页" % (nid, detail["pages"], detail["image_pages"], detail["notes_existing"]))
        assert detail["pages"] == before["pages"], "解析页数（%d）与直接读文件（%d）不一致" % (detail["pages"], before["pages"])
        print("   ✓ 页数与直接读文件一致")

        print("\n② 画面识别（vision=%s）" % args.vision)
        body = {"vision_mode": args.vision}
        if pages:
            body["page_nos"] = pages
        r = c.post("%s/api/notes/%s/analyze" % (BASE, nid), json=body)
        if r.status_code != 200:
            print("   启动失败：%s" % r.text[:300])
            return 1
        jid = r.json()["job_id"]
        state = wait_job(c, jid, "识别", quiet=(args.vision != "off"))
        if state == "error":
            return 1

        print("\n③ 写备注")
        body = {}
        if pages:
            body["page_nos"] = pages
        r = c.post("%s/api/notes/%s/generate" % (BASE, nid), json=body)
        if r.status_code != 200:
            print("   启动失败：%s" % r.text[:300])
            return 1
        jid = r.json()["job_id"]
        state = wait_job(c, jid, "备注")
        if state == "error":
            return 1

        print("\n④ 页面清单复核")
        r = c.get("%s/api/notes/%s" % (BASE, nid))
        det = r.json()
        pg = det["pages_detail"]
        done = [p for p in pg if p["note_status"] == "done" and p["note"].strip()]
        failed = [p for p in pg if p["note_status"] == "failed"]
        vis_done = [p for p in pg if p["vision_status"] == "done"]
        vis_fail = [p for p in pg if p["vision_status"] == "failed"]
        print("   已写备注 %d/%d 页 ｜ 识别成功 %d 页、失败 %d 页 ｜ 失败页 %s"
              % (len(done), len(pg), len(vis_done), len(vis_fail), [p["page_no"] for p in failed] or "无"))
        print("   累计花费 ¥%.4f" % det["cost_cny"])
        for p in done[:3] + ([pg[0]] if not done else []):
            print("   ── P%s（%s）%s" % (p["page_no"], "图片页" if p["low_info"] else "文字页", p["note"][:160]))

        print("\n⑤ 导出并回读复核")
        r = c.post("%s/api/notes/%s/export" % (BASE, nid), json={"keep_original": True})
        if r.status_code != 200:
            print("   导出失败：%s" % r.text[:300])
            return 1
        exp = r.json()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = os.path.join(root, "data", "files", "exports", exp["name"])
        if not os.path.exists(out):
            print("   产物不存在：%s" % out)
            return 1
        after_prs = Presentation(out)
        after = shape_stats(after_prs)
        after_notes = [s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
                       for s in list(after_prs.slides)]
        ok = True
        print("   产物：%s（%.1f MB）" % (os.path.basename(out), os.path.getsize(out) / 1048576))
        checks = [
            ("页数一致", after["pages"] == before["pages"], "%d vs %d" % (after["pages"], before["pages"])),
            ("每页形状数一致", after["shapes"] == before["shapes"], "不一致的页：%s" % [
                i + 1 for i, (a, b) in enumerate(zip(after["shapes"], before["shapes"])) if a != b]),
            ("图片总数一致", after["pics"] == before["pics"], "%d vs %d" % (after["pics"], before["pics"])),
            ("原文件未被改动", os.path.getsize(src) == before_bytes, "%d vs %d" % (os.path.getsize(src), before_bytes)),
        ]
        for name, cond, d in checks:
            print("   %s %s%s" % ("✓" if cond else "✗", name, "" if cond else "  —— " + str(d)))
            ok = ok and cond
        written = sum(1 for t in after_notes if t)
        print("   ✓ 有备注的页：%d" % written)
        for p in done:
            t = after_notes[p["page_no"] - 1]
            if p["note"].strip()[:20] not in t:
                print("   ✗ P%s 的备注没写进产物" % p["page_no"]); ok = False
        for i, orig in enumerate(orig_notes, 1):
            if orig and orig[:15] not in after_notes[i - 1]:
                print("   ✗ P%s 原有备注在产物里丢了" % i); ok = False
        kept = sum(1 for i, orig in enumerate(orig_notes, 1) if orig and NOTE_MARKER in after_notes[i - 1])
        print("   ✓ 保留原文并追加 AI 备注的页：%d" % kept)
        print("\n%s" % ("全部复核通过 ✅" if ok else "复核有未通过项 ❌"))
        print("任务 ID：%s（网页：%s/#/notes/%s）" % (nid, BASE, nid))
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
