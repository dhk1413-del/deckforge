# ui-design/ —— DeckForge **应用界面**设计规范（浅色为主）

> ⚠️ 与 `style-packs/` 区分：**本目录 = 我们自己的界面**；`style-packs/` = **生成的 PPT 页面**的视觉规范。两者同为 Google DESIGN.md 令牌格式，但用途不同，不要混用。

## 文件

| 文件 | 内容 |
|---|---|
| `DESIGN.md` | **真源**：令牌（颜色/字体/圆角/间距/25 个组件）+ 八个规范章节 |
| `components.md` | 组件**状态矩阵**与交互反馈（步骤条、缩略图网格、转可编辑、成本揭示、空/错态） |
| `app.css` | **可直接引用**：CSS 变量（明 + 暗）+ 基础样式 + 组件类，无框架依赖 |
| `tailwind.theme.css` | Tailwind v4 `@theme` 片段（`@import` 即用） |
| `preview.html` | **自包含预览页**（23 色卡 / 25 组件 / 明暗切换），单文件双击即看 |
| `tokens.json` | W3C DTCG 令牌（CLI 导出，供代码与工具消费） |
| `tailwind.theme.json` | Tailwind 主题 JSON（CLI 导出） |

## 命令（与 style-packs 同一套 CLI）

```bash
CACHE=/tmp/npm-cache-deckforge
npx --cache $CACHE -y @google/design.md lint  ui-design/DESIGN.md          # 结构 + 引用 + WCAG
npx --cache $CACHE -y @google/design.md diff  ui-design/DESIGN.md new.md  # 改版回归
npx --cache $CACHE -y @google/design.md export --format dtcg     ui-design/DESIGN.md > ui-design/tokens.json
npx --cache $CACHE -y @google/design.md export --format tailwind ui-design/DESIGN.md > ui-design/tailwind.theme.json
```

> 环境坑：本机 `~/.npm` 有历史 root 属主文件，`npx` 直接跑会 `EACCES` → 加 `--cache /tmp/npm-cache-deckforge`，**不要 sudo**。

## 来源与依据

- 浅色为主 + 配色：**用户 2026-09-17 指定参考图**，色值由 `PIL` 逐像素取样（页面底 `#F5F6FC` 占比 33%、主色 `#1E78FA`、标题 `#1E232E`、次要灰 `#666666`、角标渐变 `#F25590→#BE54DE`）。
- 交互与信息架构：spec §4 信息架构 + §3.2 工作台（6 步流程、页级状态、可编辑/图片直通标注）。
- 方法：Google DESIGN.md 规范（同一 CLI 校验），与 `style-packs/` 保持一致的方法论。

## 重新生成（改完 DESIGN.md 后）

```bash
CACHE=/tmp/npm-cache-deckforge
npx --cache $CACHE -y @google/design.md lint ui-design/DESIGN.md          # 必须 0 errors
npx --cache $CACHE -y @google/design.md export --format dtcg     ui-design/DESIGN.md > ui-design/tokens.json
npx --cache $CACHE -y @google/design.md export --format tailwind ui-design/DESIGN.md > ui-design/tailwind.theme.json
python3 tools/gen_ui_css.py       # tokens.json → app.css / tailwind.theme.css
python3 tools/gen_ui_preview.py   # → preview.html（自包含）
```

## 预览页查看方式

直接双击 `ui-design/preview.html`（无需服务器、无外部依赖）。截图核对可用 `~/.hermes-browser/cdp.js goto file://… ; shot --full`。
