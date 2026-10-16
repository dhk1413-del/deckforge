# 变更记录

本文件记录 SlideCraft 的版本变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

版本号**唯一真源**是仓库根的 [`VERSION`](VERSION) 文件：发版只改这一处，`web/package.json` 由
`tools/check_version_sync.py` 在门禁里强制对齐，`server/app/main.py` 直接读该文件（`/api/health` 可查）。
发版流程见 [AGENTS.md](AGENTS.md#发版流程)。

## [0.1.0] - 2026-10-16

首个公开版本。

### 新增

- **四条主线**：文档生成（Markdown / TXT / DOCX / PDF / PPTX → 整套 PPT）、PPT 美化、图片转可编辑、讲稿备注。
- **两种导出**：图片版 PPTX（整页图铺底）与原生可编辑 PPTX（文本/形状/图表都是 PowerPoint 原生对象）。
- **零密钥可跑**：没有任何 API key 时，大纲走本地规则切页、出图走本地兜底渲染，成本 0，流程与导出都能走通。
- **风格库与风格构建**：上传模板/参考图 → 证据分层 → 令牌合成，落盘后即在风格库可见。
- **文档生成 6 步流程** + 章节式「编辑大纲」编辑器（DeepSeek 产出章节）。
- **我的项目页**：项目类别（PPT生成 / PPT美化 / 图片转可编辑 / 备注生成），封面可点进入项目。
- **零依赖单文件版** `slidecraft-standalone.html`：双击离线可用，数据存在浏览器里。

### 变更

- 项目显示名统一为 **SlideCraft**（原 DeckForge）。为保留既有项目与草稿，`DECKFORGE_*` 环境变量、
  `deckforge.db`、`deckforge.pid` 与浏览器存储键**刻意保持原名**，老数据无需迁移或清空。
- 仓库地址为 <https://github.com/dhk1413-del/slidecraft>（旧地址 301 跳转）。
- 上传上限 30MB → 60MB，并把上限收敛成一处常量。
- 版本号收敛为仓库根 `VERSION` 单一真源（此前 `main.py` 与 `package.json` 各写一份，容易漏改）。

### 修复

- 修复删除项目报错、删除弹窗被压成竖排（Tailwind `max-w-md` 解析问题）、步骤条窄屏折行。
- 修复前端 HTML 被浏览器缓存（改完仍看到旧界面）。
- 修复首次启动时依赖尚未装完就误报「启动失败」。
- 勾选「保留原图」的页面，原 PPT 里的图片按坐标原样贴回（不删不换）。

### 安全

- 新增密钥门禁：`tools/check_no_secrets.py`（路径 + 密钥形态 + 本机真实 key 真值三层）+ `pre-commit` /
  `pre-push` 钩子，模型 API key **绝不入库、绝不上传**；`.gitignore` 同步加固。
- 仓库历史与 GitHub 远端经全量扫描确认不含任何密钥。

### 许可证

- 以 **AGPL-3.0** 发布（`LICENSE`）。注意：依赖 PyMuPDF 本身是 AGPL-3.0 / 商业双授权，选 MIT 也无法规避
  其义务；详见 [README「许可证」](README.md#许可证)。

### 已知问题

- 内部回归 `server/tests/test_m5.py::test_interruption_is_terminal_and_reentrant` 目前失败
  （`resume_step` 期望 5、实际 6）。该失败在打本标签之前就已存在（干净检出可复现），尚未修复；
  其余 16 项离线检查与前端构建均通过。
