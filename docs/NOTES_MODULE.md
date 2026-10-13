# PPT 备注模块（`#/notes`）

给一份**已经做好的** PPT 自动写演讲者备注，写回备注栏后导出。

- 后端：`server/app/slide_notes.py`（全部逻辑）、`server/app/main.py`（`/api/notes/*` 路由）
- 前端：`web/src/pages/NotesPage.tsx`（上传 + 列表）、`web/src/components/NotesWorkbench.tsx`（工作台）
- 表：`notes_jobs` / `notes_pages`（`server/app/db.py` SCHEMA）
- 验收：`tools/test_slide_notes.py`（离线零成本，29 项）、`tools/e2e_notes_live.py`（真机端到端，会调模型）

## 三条铁律

1. **备注内容只能来自页面自身** —— `text_source`（文本框/表格）∪ `vision`（该页渲染图的识别结果）。
   两者皆空 → **不生成**，标 `note_status=failed` 并写明原因。绝不许模型用自己的常识把页面补圆。
   实测教训：只给 4 个字的标题时，claude 会编出三大类具体内容（幻觉），DeepSeek 反而会拒答（空正文）——
   拒答是对的，幻觉是致命的。所以「信息不足」必须由**视觉识别**解决，不能靠换个更强的模型。
2. **只写备注栏**：页数、形状数、字体、母版、图片一律不动。导出前用 python-pptx 回读复核。
3. **防备注错页**：渲染出的 PDF 页数必须等于 pptx 页数，不等就中止；导出前再校验一次源文件页数。

## 流程

```
① 上传（免费）
   POST /api/notes/upload  → 存 data/files/notes/{nid}/source.pptx
   parse_pptx(): 文本框+表格文字、图片数、该页已有备注、low_info(文字<30字)
   → 秒回「N 页，其中 M 页是图片页」

② 画面识别（花钱、慢）
   render_deck(): LibreOffice --headless → PDF → PyMuPDF → 每页 PNG(1600px)
                 缓存到 data/files/notes/{nid}/pNNN.png，二次运行不重渲染
   recognize_page(): 视觉模型识别 → {title, text_on_page[], visual, data[]}
   并发 3；vision_mode = auto(默认，只做图片页) / all / off

③ 写备注
   build_content()：合并 text_box + text_in_image（去重）+ visual + data  ← 内容真源
   write_note(): DeepSeek，**预算 8000 → 空正文则抬到 16000 重试一次**
   并发 4；only_missing=true 时只补未完成的页（续跑）

④ 复核 / 手改 / 重写
   PATCH /pages/{no} {note}                 人工改（note_edited=1）
   POST  /pages/{no}/regenerate {instruction}  写一句提示词让 AI 重写这一页

⑤ 导出
   export_with_notes(): 打开原文件副本，逐页写 notes_slide，另存
   note_original 非空 → 原文 + "【演讲备注】" + AI 备注（keep_original=false 可覆盖）
```

## 踩过的坑（都已在代码里修掉，别改回去）

| 坑 | 现象 / 处理 |
|---|---|
| `prs.slides[:n]` 切片 | `AttributeError: 'list' object has no attribute 'rId'`（切片走进 `__getitem__`）→ 必须 `list(prs.slides)` |
| `shape.shape_type` | 真实文件里有无法识别的形状 → 抛 `NotImplementedError`，整个解析崩掉 → 必须 try/except 包住 |
| LibreOffice 已经在跑 | 与 GUI 实例共用 user profile 时 headless 转换**静默失败** → 每次用独立 profile：`-env:UserInstallation=file://<tmpdir>` |
| 大文件转换 | 96MB / 64 页实测 28 秒；超时给到 900 秒 |
| 思考型模型空正文 | `deepseek-v4-pro` 的 `reasoning_tokens` 能吃掉全部预算（实测 1488/1593）→ `max_tokens` 必须在 8000 以上，且**空正文要当失败**，不能静默存空备注 |
| 视觉模型也吃预算 | 同上，4000 不够时自动放大到 12000 重试（沿用 `providers` 里既有的做法） |
| 渲染→PDF 页序 | 转换前后页数必须比对，不一致就中止（备注错页比失败更糟） |
| 大 PPT 上传 | 96MB 单文件；`data/files/notes/{nid}/` 会长期占用空间，删任务不会删文件 |
| `only_missing` 语义 | 不带页号调用时默认**全部重写**（真金白银），前端首次生成要传 `only_missing=true` |

## 模型选择（2026-09 实测）

- **文本：`deepseek-v4-pro`（官方直连）**。同题对比 4 个模型：
  `deepseek-v4-pro` 语言自然克制、贴合页面；`deepseek-flash` 啰嗦重复且空正文率高；
  中转站的 `claude-sonnet-4-6` 质感最好但**信息不足时会补编**（违反铁律 1）；
  `gemini-3-pro` 满篇套话、无实信息。模型名在设置页可改，不必动代码。
- **视觉：阿里百炼 Qwen-VL**（设置页「视觉模型」）。实测把纯图页里的文字全读了出来
  （连插画页的书名、`座位预约 369 次` 这类数值都能读）。注意：慢，复杂页可到 110 秒/页。

## 成本（64 页真实文件实测口径）

| 项 | 单价来源 | 64 页约 |
|---|---|---|
| 画面识别（45 个图片页） | 百炼 Qwen-VL，按 token 估算 | < 0.5 元 |
| 写备注（64 页） | DeepSeek，按 token | < 0.3 元 |
| 渲染 | 本机 LibreOffice | 0 元 |

耗时：渲染 30 秒 + 识别 5~15 分钟 + 写备注 4~8 分钟（3/4 并发）。

## 改这个模块后必须跑

```bash
.venv/bin/python tools/test_slide_notes.py        # 29 项离线回归（不花钱）
.venv/bin/python tools/e2e_notes_live.py <某.pptx> --pages 4,16 --yes   # 真机小样本
cd web && npm run build && cd .. && bash server/start-lan.sh            # 前端改了必须重新构建
```
