# 风格构建（Style Builder）—— 上传模板/参考图 → 自动解析出设计规范

> 目标：在**风格库**与**生成向导的风格选择**里各放一个入口「+ 风格构建」。
> 点开后上传 `.pptx` / `.pdf` 模板或风格参考图（可多张），系统自动解析出配色、字体层级、版式与画面语言，
> **生成一套新的风格包**并写入仓库 `style-packs/`，随后立刻可在风格库里选用、在生成时绑定。

## 1. 用户流程（4 步）

1. **上传**：拖入 `.pptx`（一份，推荐）、`.pdf`（一份）或图片 `.png/.jpg/.jpeg/.webp`（可多张）；
   截图后也可以直接在页面上按 `⌘V` / `Ctrl+V` 粘贴图片上传（纯文本粘贴不受影响）。
2. **解析**：点「开始解析」→ 进度面板显示阶段：提取主题色 → 像素统计 → 视觉理解 → 撰写规范 → 落盘预览。
3. **预览**：色板（每个色值标注**出处**）、风格摘要、令牌概要、代表页缩略图；可编辑「标识 id / 中文名 / 分类 / 标签 / 摘要」。
4. **保存**：写入 `style-packs/styles/<id>/`，风格库立即可见（`GET /api/style-packs` 返回新包）。

## 2. 证据分层（本功能的核心纪律）

| 证据来源 | 能给出什么 | **不能**给出什么 |
|---|---|---|
| pptx `ppt/theme/theme1.xml` 的 `<a:clrScheme>` / `<a:fontScheme>` | 权威色板（accent1..6、dk1/lt1）、标题/正文字体方案 | 实际用色占比 |
| 渲染页像素统计（HSV 分桶 + 3×3 分格） | 真实底色/卡面色/强调色占比、色块**落在哪几格**、逐页点睛色分布 | 字体、语义 |
| PDF（PyMuPDF） | 高清页渲染、像素统计、嵌入字体名（可能不完整） | OOXML 主题色板与 fontScheme |
| pptx 结构统计（`prstGeom`/`sz`/`latin`） | 几何与圆角分布、字号与字体频次、渐变/投影有无 | 视觉气质 |
| 视觉模型（Qwen-VL，看代表页） | **定性**描述：版式结构、图形语言、层级留白、气质、负向用法 | ❌ 色值、❌ 字号（实测偏差大，一律弃用） |
| LLM（DeepSeek） | 把上述证据写成 style.md 的 prose 与 prompt.md 的正文 | ❌ 不得生成/编造色值 |

**铁律**：YAML 令牌由代码从证据生成；LLM 只写文字。任何一步缺证据就少写一条，**不编**。

## 3. 产物

```
style-packs/styles/<id>/
├── style.md      # DESIGN.md 格式：YAML 令牌 + prose 八节
├── prompt.md     # 画面语言，**≤1500 字符**（render.assemble_prompt 会截断到 1500）
├── previews/*.png# 代表页（3~6 张，来自上传文件本身，不自造）
└── meta.json     # {name, category, tags, badge, summary} —— 覆盖 stylepacks.py 的硬编码 META
```

- `meta.json` 让**运行时新建**的风格包也有中文展示名/分类/标签（`META` 仍作为内置包的兜底）。
- 生成的 `style.md` 必须能过 `npx -y @google/design.md lint`：**0 error / 0 warning**
  （对比度不达标就换取值；无用令牌接进 components 或删掉）。
- `prompt.md` ≤1500 字符是硬断言（超了会静默截掉末尾「负向词」，水印/乱码风险回升）。

## 4. API 契约

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/style-builder/upload` | multipart（字段 `files`，兼容单个 `file`）→ `{builder_id, kind, files, pages}` |
| POST | `/api/style-builder/{bid}/analyze` | `{use_vision?:bool, pages?:int[]}` → `{job_id, progress_url}`（异步，走既有 job + SSE） |
| GET | `/api/style-builder/{bid}` | 状态与结果：`{status, files, result?:{palette, evidence, summary, style_md, prompt_md, suggested:{id,name,category,tags,summary}, previews[], warnings[]}, error?}` |
| POST | `/api/style-builder/{bid}/save` | `{id,name,category,tags,summary}` → `{ok, style_pack}`（落盘后 `GET /api/style-packs` 立即可见） |
| DELETE | `/api/style-builder/{bid}` | 放弃/清理 |

进度复用 `GET /api/jobs/{job_id}/stream`（前端 `useJobStream`），不另造一套。

## 5. 关键决策与取舍（默认口径）

| # | 决策 | 取值 | 理由 |
|---|---|---|---|
| D1 | 解析引擎 | **产品内自动解析** = 代码化提取 + 视觉模型 + DeepSeek 撰写 | 「点击就能用」要求零人工；确定性提取可离线回归。**Hermes CLI 深度审校留作可选通道**（慢、耗额度，不进热路径） |
| D2 | 入库时机 | **先预览、后保存**（save 才写仓库） | 避免解析抖动产生垃圾风格包 |
| D3 | 落库位置 | 仓库 `style-packs/styles/<id>/`（git 可版本化） | 与既有内置包同构，换皮/生图链路零改动即可用 |
| D4 | 图片输入的能力边界 | 仅有像素证据 → **给得出配色与画面语言，给不出主题色板与字体方案** | 如实写进 `warnings`，不假装等价于 pptx |
| D5 | 新包 id | 自动按「域 + 双色」生成（如 `biz-blueorange`），用户可改；只允许小写字母数字与连字符 | 与既有命名惯例一致 |

## 6. 边界与未实现（如实标注）

- PDF 输入拿不到 OOXML 主题色板与 fontScheme；字体方案尽力来自嵌入字体名（可能不完整），提取不到时退化为通用档位，并如实写入 `warnings`。
- 图片输入拿不到字体方案 → `style.md` 的 typography 用**同类风格的通用档位**并标 `warnings`。
- 视觉模型/文本模型任一未配置 → 解析仍可完成（降级为实测数据 + 模板化文字），`warnings` 说明缺什么。
- 逐页 90+ 的大模板只抽样统计（代表页渲染 + 全页低分辨率像素统计），不做全页逐张视觉识别。
- 不做「自动替换已有风格包」——同名 id 一律拒绝并提示改名。
