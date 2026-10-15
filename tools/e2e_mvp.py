#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SlideCraft MVP 端到端验收（零 key 路径必须全绿）。

跑法：.venv/bin/python tools/e2e_mvp.py
覆盖：健康 → 设置 → 风格包 → 建项目 → 上传解析 → 大纲 → 页面确认 → 生成（SSE 收进度）
      → 页面列表 → 导出图片版 → 校验 PPTX 结构 → 账本

注：原来 [9] 内置引擎转可编辑 + [10] kind=editable 导出两段已于 2026-09-21 随「本地渲染」
一并下线（「图片转可编辑」现为独立模块 #/editable，只走第三方 skill 精细重建，13 分钟/页，
不适合放在本脚本里跑）。此处只保留图片版这条线。
"""
import io
import json
import os
import sys
import time
import zipfile

import httpx

BASE = os.environ.get("DF_BASE", "http://127.0.0.1:8640")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE = os.path.join(ROOT, "samples", "三创赛汇报.md")
# 导出的 PPTX 落在服务端的数据目录里：跟随 DECKFORGE_DATA（隔离实例），否则用仓库默认 data/
DATA_DIR = os.environ.get("DECKFORGE_DATA") or os.path.join(ROOT, "data")

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✅" if cond else "❌", name, (" — " + detail) if detail else ""))


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=120.0, trust_env=False)   # 本机服务：绕代理、忽略环境变量

    print("\n[1] 健康与能力")
    h = c.get("/api/health").json()
    check("/api/health ok", h.get("ok") is True, "version=%s" % h.get("version"))
    check("零 key 时本地兜底可用", h["providers"]["image"].get("local_render") is True)
    check("两家 provider 已预置", all(k in h["providers"]["image"] for k in
          ("guaihub", "dashscope")))
    print("     网络模式 = %s ｜ 当前选中 = %s" % (h["network"]["mode"], h["providers"]["picked"]))

    print("\n[2] 设置（掩码与热加载）")
    s = c.get("/api/settings").json()
    # 前置条件：本脚本验收的是「零 key 基线」——若已配置 key，生成会走真模型，断言口径不同，须显式提示
    keyed = [p["id"] for p in s["providers"] if p["key_set"]]
    if keyed:
        print("     ⚠️ 检测到已配置 key：%s" % ", ".join(keyed))
        print("     ⚠️ 本脚本是「零 key 基线」验收（期望本地兜底渲染）。请先清空 key 再跑；")
        print("        要验真模型请在界面填好 key 后按页生成，观察账本里的 provider/成本。")
    check("6 家 key 均未配置", all(not p["key_set"] for p in s["providers"]))
    check("key 掩码字段存在", all("key_masked" in p for p in s["providers"]))
    t = c.post("/api/settings/test", json=dict(provider_id="local_render")).json()
    check("本地兜底连通性测试", t.get("ok") is True)

    print("\n[3] 风格包与布局")
    sps = c.get("/api/style-packs").json()["items"]
    check("内置风格包可用", len(sps) >= 3, "%d 套：%s" % (len(sps), ", ".join(x["id"] for x in sps)))
    check("风格包带令牌色", all(x["accent"].startswith("#") and x["bg"].startswith("#") for x in sps))
    layouts = c.get("/api/layouts").json()["items"]
    check("7 个版式", len(layouts) == 7, ", ".join(x["key"] for x in layouts))
    detail = c.get("/api/style-packs/%s" % sps[0]["id"]).json()
    check("风格包详情含 style_md/prompt_md", bool(detail.get("style_md")) and bool(detail.get("prompt_md")))

    print("\n[4] 建项目 + 上传解析")
    pid = c.post("/api/projects", json=dict(title="三创赛汇报", intake_mode="doc")).json()["id"]
    with open(SAMPLE, "rb") as f:
        up = c.post("/api/projects/%s/upload" % pid,
                    files={"file": ("三创赛汇报.md", f, "text/markdown")}).json()
    check("解析出正文", up["char_count"] > 500, "%d 字" % up["char_count"])
    check("建议页数合理", 3 <= up["suggested_pages"] <= 30, "%d 页" % up["suggested_pages"])

    print("\n[5] 内容梳理（无 DeepSeek key → 本地切页降级）")
    ol = c.post("/api/projects/%s/outline" % pid, json=dict(target_pages=10)).json()
    pages = ol["pages"]
    check("产出页清单", 3 <= len(pages) <= 12, "%d 页" % len(pages))
    check("标注了降级路径", (not ol["configured"]) and ol["fellback"] == "local_split", ol.get("hint", "")[:40])
    check("每页有标题与要点", all(p.get("title") and p.get("points") for p in pages))
    check("首末页角色正确", pages[0]["role"] == "cover" and pages[-1]["role"] == "summary")

    print("\n[6] 页面确认（保留前 6 页）")
    keep = [p["page_no"] for p in pages[:6]]
    c.put("/api/projects/%s/pages" % pid,
          json=dict(pages=[dict(page_no=p["page_no"], keep=(p["page_no"] in keep)) for p in pages]))
    check("页面勾选成功", c.get("/api/projects/%s/slides" % pid).status_code == 200)

    print("\n[6.5] 内容确认（③；/generate 的硬前置，未确认会被拒）")
    conf = c.patch("/api/projects/%s" % pid, json=dict(confirm_content=True))
    check("内容确认通过", conf.status_code == 200, conf.text[:60])

    print("\n[7] 生成（SSE 收进度；无 key → 本地兜底渲染）")
    style_id = sps[0]["id"]
    g = c.post("/api/projects/%s/generate" % pid,
               json=dict(style_pack_id=style_id, size="2K", page_nos=keep)).json()
    check("返回 job 与降级提示", bool(g["job_id"]) and g["fellback"] == "local_render", g.get("hint", "")[:44])
    events, t0 = [], time.time()
    with c.stream("GET", "/api/jobs/%s/stream" % g["job_id"], timeout=120.0) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                events.append(ev)
                if ev.get("type") == "progress" and ev.get("status") == "done":
                    print("     · 第 %s/%s 页完成（%s）" % (ev.get("page"), ev.get("total"), ev.get("image_url", "")[-24:]))
                if ev.get("type") in ("done", "error"):
                    break
    check("SSE 收到逐页进度", sum(1 for e in events if e.get("type") == "progress") >= len(keep),
          "%d 条事件，用时 %.1fs" % (len(events), time.time() - t0))
    check("SSE 收到终止事件", any(e.get("type") == "done" for e in events))

    print("\n[8] 页面结果（含每页 provider/尺寸/成本/校验）")
    items = [x for x in c.get("/api/projects/%s/slides" % pid).json()["items"] if x["status"] == "done"]
    check("生成的页均已就绪", len(items) == len(keep), "%d 页" % len(items))
    check("均标记为本地兜底且零成本", all(x["provider"] == "local_render" and x["cost_cny"] == 0 for x in items))
    check("输出尺寸为 2K 16:9", all((x["width"], x["height"]) == (2048, 1152) for x in items),
          str([(x["width"], x["height"]) for x in items[:2]]))
    check("每页带文字校验结论", all(x["verify"].get("text_accuracy") == 1.0 for x in items))
    check("图片可访问", c.get(items[0]["image_url"]).status_code == 200, items[0]["image_url"])

    print("\n[8.5] 逐页核对（导出前的硬前置：未核对会被拒）")
    reviewed = 0
    for it in items:
        r = c.post("/api/projects/%s/slides/%s/review" % (pid, it["slide_id"]),
                   json=dict(image_url=it["image_url"]))
        if r.status_code == 200:
            reviewed += 1
        else:
            print("     · 第 %s 页核对失败：%s %s" % (it.get("page_no"), r.status_code, r.text[:60]))
    check("逐页核对已确认", reviewed == len(items), "%d/%d 页" % (reviewed, len(items)))

    print("\n[9] 导出图片版（并解析 PPTX 结构核对）")
    img = c.get("/api/projects/%s/export" % pid, params=dict(kind="image")).json()
    check("图片版导出成功", img["pages"] == 6 and img["size_bytes"] > 10000,
          "%d 页 / %.1f KB" % (img["pages"], img["size_bytes"] / 1024))
    path = os.path.join(DATA_DIR, "files", img["file"].lstrip("/").replace("files/", "", 1))
    check("图片版文件落盘", os.path.exists(path), os.path.basename(path))
    if os.path.exists(path):
        z = zipfile.ZipFile(path)
        slides = [n for n in z.namelist() if n.startswith("ppt/slides/slide")]
        has_pic = sum(1 for n in z.namelist() if n.startswith("ppt/media/") and not n.endswith("/"))
        print("     · image: %d 页 / %d 张媒体" % (len(slides), has_pic))
        check("图片版页数与媒体数正常", len(slides) == 6 and has_pic == 6)

    if os.path.exists(os.path.join(ROOT, "data", "files", "exports")) is False:
        pass

    print("\n[10] 用量账本（模型可见）")
    u = c.get("/api/usage", params=dict(range="month")).json()
    check("账本有记录", u["total_cny"] >= 0 and len(u["items"]) >= 6, "%d 条" % len(u["items"]))
    check("按供应商汇总含 local_render",
          any(x["provider"] == "local_render" for x in u["by_provider"]),
          str([(x["provider"], x["count"]) for x in u["by_provider"]]))
    check("每条记录带 model/size/latency",
          all(x["model"] is not None and x["size"] and "latency_ms" in x for x in u["items"]))

    print("\n[11] 项目列表")
    pl = c.get("/api/projects").json()["items"]
    check("项目已入库且带页数", any(p["id"] == pid and p["page_count"] >= 6 for p in pl))

    print("\n" + "=" * 68)
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败清单：")
        for f in FAIL:
            print("  -", f)
        return 1
    print("✅ MVP 零 key 全链路验收通过（项目 %s）" % pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
