# UI v2 改造任务（给 Codex CLI 的完整提示词）

> 用法（在项目根执行，提示词前必须有 `--`）：
> ```bash
> cd /path/to/deckforge
> codex exec --skip-git-repo-check --sandbox workspace-write -C /path/to/deckforge \
>   -- "$(cat docs/codex-ui-v2-prompt.md)"
> ```
> 下面 `---PROMPT---` 之后的内容就是提示词正文。

---PROMPT---

你是资深前端工程师。项目根：`/path/to/deckforge`（DeckForge —— 自托管「AI 生成整套 PPT」工作台，前端 React 19 + TypeScript + Vite + Tailwind v4，样式令牌集中在 `ui-design/`）。

## 本次任务
把整套前端 UI 从 v1 升级到 **v2「蓝色云平台风」**，参照用户已确认的样式稿 `ui-design/preview-v2.html`。

**第一步必做**：完整阅读这两个文件，它们就是本次实现的唯一真相，不要凭印象发挥：
1. `docs/UI_V2_MIGRATION.md` —— 取值表（每个色值都抄好了）、样式规则 10 条、禁用项、已知坑。
2. `ui-design/preview-v2.html` —— 6 屏高保真样式稿（首页 hero + 快捷入口条 / 生成向导 / 风格选择 / 项目工作台 / Token 用量 / 系统设置）与「改造前」实机截图对照。

## 改动范围（只改这些）
- `ui-design/tokens.json`：按 runbook §2 更新色值、新增 `surface-band` `border-strong` `brand-grad-from` `brand-grad-to`，`rounded` 增 `xl:20`，删除 `typography.num`。
- `ui-design/DESIGN.md`：同步取值表与 Do/Don't（「默认无阴影」改为「卡片带柔和投影」，删除等宽数字要求）。
- `tools/gen_ui_css.py`、`tools/gen_ui_preview.py`：
  - 把硬编码的旧路径 `~/Desktop/02_同步文件夹/hermes/智能PPT生成工作台/ui-design` 改成基于 `__file__` 的项目相对路径（脚本在 `tools/` 下）；
  - 生成模板升到 v2：导出 `--color-surface-band`、`--color-border-strong`、`--color-brand-grad-from/to`、`--radius-xl`、`--shadow-card`、`--shadow-hover`（含暗色补值），`.num` 不再切换等宽字体；
  - 位置参数用法不变，保持幂等（连着跑两次结果一致）。
- 生成产物 `ui-design/app.css`、`ui-design/tailwind.theme.css`、`ui-design/preview.html`：**必须由生成器重出，不要手改**（先跑 `gen_ui_css.py` 再跑 `gen_ui_preview.py`；前者会写 `/tmp/pm/ui_ctx.json`，注意先建好 `/tmp/pm`）。
- `web/src/**`：按 runbook §3 的 10 条规则改造样式。重点：
  - 首页 `pages/HomePage.tsx`：顶部加渐变 hero 带（标题/副标/主次按钮/右上状态）+ 4 张快捷入口卡（`margin-top:-30px` 压住 hero 下沿，分别切 `#/?mode=topic|editable|reskin` 与 `/styles`，复用现有 mode 逻辑）。
  - `components/AppShell.tsx`：侧栏与顶栏按 v2 重做（品牌渐变方块、选中项浅蓝胶囊、顶栏 60px + 状态胶囊）。
  - 其余页面与组件（向导、项目工作台、风格选择、用量、设置、备注、各面板/卡片/表格/缩略图/进度/步骤条/Toast/空态）：统一换成 v2 的卡片投影、色带分层、渐变主按钮、两类胶囊、渐变进度条、账本表样式。
  - 状态数据只能用**已有接口**（如 `/api/health`）已有的字段，不要新增后端接口，不要显示任何假数字。

## 用户复核预览稿时的三条硬性修正（务必落实）
1. **hero 装饰不得压内容**：光斑/插画只放右侧留白区，正文列用 `max-width:min(720px,calc(100% - 420px))` 这类约束，任何宽度下与右侧装饰保持 ≥380px 空隙；装饰元素一律 `pointer-events:none`。
2. **右上角状态只有一处**：只有顶栏一个「运行状态」入口；首页 hero 内**不要**放任何数据或状态块（样式稿里那块 9/27/¥0.0000 已删）。
3. **状态浮层必须能自动收起**：`web/src/components/ProviderStatus.tsx` 目前只有点击触发器开合，缺「点外部关闭 + Esc 关闭」——本次补上（`useEffect` 里挂 `pointerdown`/`keydown`，目标不在浮层与触发器内则关闭，关闭后 `aria-expanded=false`，卸载时解绑）。其它手写浮层同样检查。

## 铁律（违反即返工）
1. **不改后端**：`server/**` 一律不动。
2. **不改行为**：请求、状态机、SSE 流、路由、文案、`aria-*`、键盘可用性、错误提示全部保持一致；只改 `className` / 结构与令牌产物。
3. **不加依赖**：不得新增 npm 包、不得换 UI 库。
4. **决策 3**：❌ 不新增深色页脚（页脚保持现有浅色小字行）；❌ 数字不再等宽（`.num` 只保留 `font-feature-settings:"tnum"`）。
5. **决策 2**：`[data-theme="dark"]` 必须保留，并为新增令牌补齐暗色值；暗色主按钮保持 `#3C74C9`（白字 4.63:1），不要改成 `#4C93FF`（只有 3.03:1）。
6. **对比度底线**：runbook §2 的色值已经过 WCAG 计算，**照抄，不要自创**（例如占位符必须 `#64748F`，`#8698B5` 不达标）。
7. 不要 `git commit`、不要 `git stash`（仓库没有任何 commit）。
8. 不要动 `web/dist`（由构建生成）、不要动 `data/`、`samples/`、`style-packs/`。

## 自检（必须真的跑，不许声称通过）
```bash
cd /path/to/deckforge
.venv/bin/python tools/gen_ui_css.py && .venv/bin/python tools/gen_ui_preview.py   # 幂等、无报错
npm --prefix web run typecheck                                                    # tsc 零错误
npm --prefix web run build                                                        # 构建成功
make lint                                                                         # 后端 compileall + 前端 tsc
```
若某项失败：自己修到通过再结束；确实改不动就在结尾如实说明「哪一条没过、真实报错是什么」。

## 结束条件
- `web/src`、`ui-design/*`、`tools/gen_ui_*.py` 已按 v2 落地并全部自检通过；
- 最终回复用**中文**给一份简报：改了哪些文件（分组列出）、自检命令的真实结果、你拿不准或没做的部分（例如某个页面样式与样式稿不完全一致的取舍）。
- 不要在回复里贴大段代码 diff，改了什么说明清楚即可。
