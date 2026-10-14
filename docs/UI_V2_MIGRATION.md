# DeckForge UI v2 迁移 Runbook（蓝色云平台风）

> 由 Hermes 于 2026-10-08 02:5x 起草，供 **2026-10-08 06:40 的定时作业**执行。
> 视觉稿：`ui-design/preview-v2.html`（6 屏高保真样式稿，含「改造前」实机截图对照）。
> 本文件只描述「怎么做」，不预置任何已完成的改动。

---

## 0. 用户已确认的决策（不可自行更改）

| # | 决策 | 落地含义 |
|---|---|---|
| 1 | **走「hero + 快捷入口条」大留白营销式** | 首页顶部加渐变 hero 带 + 4 张快捷入口卡（上移压住 hero 下沿）；其余页面保持工作台版式，只换配色与卡片质感 |
| 2 | **保留 `[data-theme="dark"]`** | 暗色令牌块必须同步更新到 v2 并实测可读（对比度达标）；不得删掉暗色 |
| 3 | **深色页脚 与 数字等宽 都不保留** | ❌ 不新增深色页脚（页脚仍用现有浅色小字行）；❌ `.num` 不再切换到 JetBrains Mono，只保留 `font-feature-settings:"tnum"` 做表格对齐 |

参考图取色（逐像素采样，已写入本 runbook 的新值列）：主蓝 `#2068F0`、亮青蓝 `#28A0F8`、区块底 `#F1F6FD`、深墨 `#101828`。

---

## 1. 落地范围

| 层 | 文件 | 动作 |
|---|---|---|
| 设计令牌 | `ui-design/tokens.json` | 改色值 + 增补新令牌 |
| 规范文档 | `ui-design/DESIGN.md` | 更新取值表与「Do/Don't」（阴影从「默认无阴影」改为「卡片带柔和投影」） |
| 生成器 | `tools/gen_ui_css.py`、`tools/gen_ui_preview.py` | 修死路径 + 模板升到 v2，然后**重新生成**下面两个产物 |
| 生成产物 | `ui-design/app.css`、`ui-design/tailwind.theme.css`、`ui-design/preview.html` | 由生成器重写（勿手改） |
| 应用层 | `web/src/**`（React 19 + TS + Tailwind v4） | 按 v2 规则改造样式，**不改行为、不改文案、不改后端** |
| 产物 | `docs/UI_V2_REPORT.md` | 作业结束时写验收报告 |

**不动**：`server/**`（后端）、`style-packs/**`、`data/**`、`web/dist/**`（由 `npm run build` 生成）。

---

## 2. 取值表（照抄，已过 WCAG 计算）

### 2.1 颜色（light）

| token | v1 | **v2（新值）** | 依据 |
|---|---|---|---|
| primary | `#1A63F9` | **`#2068F0`** | 白字 4.88:1 ✅ |
| accent-strong | `#1A63F9` | **`#2068F0`** | 同上（按钮填充/白底蓝字） |
| accent | `#1E78FA` | **`#3B8DF7`** | 图形元素（图标/选中框），3:1 即可 |
| tertiary | `#26ABFE` | **`#28A0F8`** | 渐变端 / 装饰进度条 |
| brand-grad-from | — | **`#2E6BF2`**（新增） | 主按钮渐变起端 |
| brand-grad-to | — | **`#3E92F8`**（新增） | 主按钮渐变止端 |
| neutral | `#F5F6FC` | **`#F1F6FD`** | 页面底 |
| surface | `#FFFFFF` | `#FFFFFF` | 不变 |
| surface-alt | `#EFF4FD` | `#EFF4FD` | 不变（次级区块底/表头） |
| surface-band | — | **`#F7FAFF`**（新增） | 区块色带底 |
| surface-tag | `#E6F1FF` | **`#EAF3FF`** | 标签胶囊底 |
| border | `#DFE5FB` | **`#E3EBF9`** | 卡片描边 |
| border-strong | — | **`#D6E4F7`**（新增） | 输入框/次级按钮描边 |
| divider | `#E8EEFF` | **`#EBF2FE`** | 分隔线 |
| ink | `#1E232E` | **`#101828`** | 主文字 |
| ink-sub | `#666666` | **`#5A6B87`** | 白底 5.40:1 ✅ / 页面底 4.97:1 ✅ |
| ink-muted | `#73757C` | **`#64748F`** | 白底占位符 4.73:1 ✅（`#8698B5` 只有 2.93:1，禁用） |
| accent-tint-ink | `#1960F2` | **`#1D5FD8`** | on `#EAF3FF` 5.10:1 ✅ |
| success/warn/danger | — | 不变 | |
| badge-from/to | — | 不变 | 角标仍点到为止，每屏 ≤1 |

### 2.2 阴影 / 圆角（新增）

```
--shadow-card : 0 1px 2px rgba(16,40,90,.04), 0 8px 24px rgba(16,40,90,.05)   ← 卡片常态
--shadow-hover: 0 4px 10px rgba(16,40,90,.07), 0 18px 44px rgba(16,40,90,.10) ← 悬停抬起
--shadow-overlay: 不变（仅 Modal/Drawer/Dropdown）
radius: sm 6→8, md 10→12, lg 16(不变), xl 20(新增)
```
Tailwind v4 的 `@theme` 里同时导出这些键，这样 `shadow-card` / `shadow-hover` / `rounded-xl` 类可直接用。

### 2.3 暗色（决策 2：保留并同步）

- 保留现有 `[data-theme="dark"]` 取值：`neutral #12151C`、`surface #1A1E27`、`surface-alt #222634`、`surface-tag #23304A`、`border/divider #2C3241`、`ink #E8EBF2`、`ink-sub #A3AAB8`、`accent #4C93FF`、`primary/accent-strong #3C74C9`（白字 4.63:1 ✅，**不要**改成 `#4C93FF`，那个只有 3.03:1）、`accent-tint-ink #9CC4FF`、状态色不变。
- 新增令牌的暗色补值：`surface-band #1E2330`、`border-strong #333A4B`、`--shadow-card 0 1px 2px rgba(0,0,0,.40), 0 8px 24px rgba(0,0,0,.35)`、`--shadow-hover 0 6px 14px rgba(0,0,0,.45), 0 18px 44px rgba(0,0,0,.50)`。

### 2.4 字号

删除 `typography.num`（等宽数字，决策 3）；`.num` 只保留 `font-feature-settings:"tnum"`，字体继承 `--font-sans`。
`--font-mono` 保留（日志/代码块仍可能用到），但**不再**用于正文数字。

---

## 3. 应用层样式规则（`web/src`，与 preview-v2.html 一致）

1. **首页 hero 带**：圆角 `xl`，背景 `radial-gradient(130% 150% at 86% 6%, #D6E8FF 0%, #E6F1FF 34%, #F3F9FF 62%, #FFFFFF 100%)`，1px `#DBE8FB` 描边，右上装饰光斑（径向渐变伪元素）。
   - 标题「开始一次整套 PPT 生成」（22–29px），副标「文档导入 · 图片转可编辑 · PPT 美化，三条路径共用一个工作台；零 key 也能用本地兜底渲染跑通全流程。」
   - 主按钮「＋ 立即开始生成」→ 聚焦/滚动到下方生成方式卡；次按钮「查看项目文件」→ `navigate('/projects')`。
   - 右上角状态数据：**只用 `/api/health` 已有字段**（如已配置 key 数、本地兜底可用、代理模式），复用现有 `ProviderStatus` 的取数逻辑；**不要**新造接口，**不要**放假的统计数字。
2. **快捷入口条**：4 张卡，`margin-top:-30px` 压在 hero 下沿，`grid-4`；分别切到 `#/?mode=topic|editable|reskin` 与 `navigate('/styles')`（复用现有 mode 逻辑，不新增功能）。
3. **卡片**：白底 + 1px `var(--color-border)` + `radius: lg` + `shadow-card`；**可点击**卡片 hover 上移 2px 且换 `shadow-hover`；纯展示卡不抬起。
4. **区块色带**：把成组内容包进 `background: var(--color-surface-band)`、1px `#E8F1FD` 描边、`radius: xl`、内边距 20/24 的容器，替代层层嵌套的白卡。
5. **按钮**：主按钮 = `linear-gradient(92deg, brand-grad-from, brand-grad-to)` + 蓝色投影 `0 6px 16px rgba(32,104,240,.28)`；次级 = 白底 + `border-strong`；文本按钮 = 蓝字无底。
6. **胶囊**：`tabs` 组（`surface-alt` 底 + 内嵌白底选中态）/ `chips` 组（`surface-tag` 底 + `accent-tint-ink` 字，选中填充主渐变 + 白字）。所有已有的 tab/筛选控件统一成这两类。
7. **进度条**：8px 高，圆角全满，填充 `linear-gradient(92deg, accent, tertiary)`。
8. **表格**：表头 `surface-alt` + `ink-sub`；行分隔 `#EEF4FE`；外框 1px `border` + `radius lg` + `shadow-card`。
9. **侧栏 / 顶栏**：侧栏白底、品牌方块用主渐变、选中项 `surface-tag` 胶囊；顶栏 60px、白底、底部 1px `border`、右侧状态胶囊（绿点=已配置 / 橙点=需代理）。
10. **禁止**：❌ 深色页脚；❌ 等宽数字；❌ 第二个品牌色；❌ 纯黑文字；❌ 用中性灰当描边；❌ 满屏渐变（渐变只用于 hero / 主按钮 / 进度条 / 角标）。

**行为不变**：所有请求、状态机、SSE、文案、`aria-*`、键盘可用性、错误提示一律不动；只改 `className` 与 `ui-design` 产物。

---

## 4. 执行步骤

### Step 0 — 备份（必须先做）
```bash
cd /path/to/deckforge
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p .backup/ui-v2-$TS
cp -a ui-design web/src tools docs .backup/ui-v2-$TS/
echo $TS > .backup/LATEST_UI_V2
```

### Step 1 — 确认 Codex 额度已恢复（6:35 重置）
```bash
export https_proxy=http://127.0.0.1:65532 http_proxy=http://127.0.0.1:65532 all_proxy=socks5://127.0.0.1:65532
export no_proxy=127.0.0.1,localhost,::1
timeout 180 codex exec --skip-git-repo-check --sandbox read-only -C /path/to/deckforge -- "回复：pong"
```
- 输出 `pong` → 继续。
- 报额度/限流错误 → 等 10 分钟重试，最多 3 次；仍失败就**如实汇报并停止**（不要自己顶上去改 `web/src`，用户要求代码改动走 Codex）。

### Step 2 — 交给 Codex 做全部文件改动
```bash
cd /path/to/deckforge
codex exec --skip-git-repo-check --sandbox workspace-write -C /path/to/deckforge \
  -- "$(cat docs/codex-ui-v2-prompt.md)"
```
放到后台跑（单次数分钟到十几分钟），完成后回到本 runbook。

### Step 3 — 独立复核（Hermes 自己做，不外包）
```bash
cd /path/to/deckforge
# 3.1 令牌确实落地
grep -nE "2068F0|1D5FD8|64748F|F7FAFF|surface-band|shadow-card" ui-design/tokens.json ui-design/app.css | head -40
# 3.2 生成器可复跑（幂等）
.venv/bin/python tools/gen_ui_css.py && .venv/bin/python tools/gen_ui_preview.py
# 3.3 静态体检 + 规范验收
make lint && make verify-fast
# 3.4 前端构建（verify-fast 内已含 npm run build，再单独确认一次产物）
npm --prefix web run build && ls -la web/dist/assets | head
# 3.5 与备份做差异对照（仓库无 commit，用备份 diff）
diff -ru .backup/ui-v2-$(cat .backup/LATEST_UI_V2)/ui-design ui-design | head -200
```
### Step 4 — 实机视觉验收
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8641/     # 期望 200
```
- 用浏览器打开 `http://127.0.0.1:8641/`，逐页截图：`#/`、`#/wizard`、`#/projects`、`#/styles`、`#/usage`、`#/settings`，另加 `#/` 与 `#/styles` 的**暗色**（控制台执行 `document.documentElement.dataset.theme='dark'`）。
- 截图存 `docs/ui-v2-shots/`，与 `ui-design/preview-v2.html` 逐屏对照：hero 是否成带、卡片是否有投影、色带是否分层、按钮/进度条是否渐变、暗色是否可读。
- 任何一页明显走形 → 修（小改）或回滚（大问题），**不要**把「差不多」当成功。

### Step 5 — 写报告
写 `docs/UI_V2_REPORT.md`：改了什么（文件清单）、验收命令的真实输出、截图路径、与 v1 的视觉差异、遗留问题与未采纳项（深色页脚/等宽数字已按决策 3 移除）。最终回复用**中文**给用户一段汇报（结论 + 证据 + 遗留风险）。

---

## 8. 预览稿复核后的三条修正（2026-10-08 03:2x，用户反馈）

用户在确认预览稿时又提了三点，**实现时必须满足**（`ui-design/preview-v2.html` 已按此改好，可直接对照）：

1. **hero 装饰图形不得压到按钮/文字** —— 光斑与装饰插画只能待在右侧留白区；正文列宽度必须写死为「容器宽 - 420px」这类约束（预览稿用 `max-width:min(720px,calc(100% - 420px))`），保证任意宽度下正文列与右侧装饰之间至少留 380px 空隙；所有装饰元素加 `pointer-events:none`。
2. **右上角「运行状态」只能有一处** —— 全站只保留顶栏那一个入口（首页 hero 里**不要**再放任何数据/状态块；预览稿里 hero 右侧原本那块 9/27/¥0.0000 已删除，改成纯装饰插画）。除顶栏外任何位置不得重复展示状态类信息。
3. **状态浮层点空白处自动收起** —— 现有 `web/src/components/ProviderStatus.tsx` 只有「点触发器开合」，**缺**外部点击与 Esc 关闭，本次必须补上：
   - `document` 上挂 `pointerdown`（或 `click`）监听，目标不在浮层/触发器内 → 关闭；
   - `keydown` 监听 `Escape` → 关闭；
   - 关闭后 `aria-expanded` 置回 false；悬浮层加 `role="dialog"` 或保持 `aria-expanded` 语义，键盘可达；
   - 组件卸载时解绑监听（`useEffect` 清理），不要泄漏。

> 同理：`web/src` 里若还有别的手写浮层（下拉/弹窗），一并检查是否支持「点外部关闭 + Esc 关闭」；不支持的同规格补齐。

---

## 5. 回滚

```bash
cd /path/to/deckforge
B=.backup/ui-v2-$(cat .backup/LATEST_UI_V2)
rm -rf ui-design web/src tools docs
cp -a $B/ui-design $B/web/src $B/tools $B/docs .
npm --prefix web run build   # 复原 web/dist
```
回滚后必须在报告里说明**为什么回滚**，不许把失败包装成成功。

---

## 6. 已知坑（照抄，别重新踩）

1. **`tools/gen_ui_css.py` / `tools/gen_ui_preview.py` 里硬编码了旧路径** `~/Desktop/02_同步文件夹/hermes/智能PPT生成工作台/ui-design`（项目已迁到 `/path/to/deckforge`）→ 改成基于 `__file__` 的项目相对路径，否则生成器写不进去。
2. `gen_ui_css.py` 会把上下文写到 `/tmp/pm/ui_ctx.json`，`gen_ui_preview.py` 依赖它 → 先确保 `/tmp/pm` 存在，并保持「先 css 后 preview」的顺序。
3. `server/app/main.py` 的 `app.mount("/", StaticFiles(web/dist))` **必须在所有 API 端点之后**；本次不改后端，但如果手滑动了 `main.py`，务必检查这一条（踩过：美化 v2 端点曾因此全 404）。
4. 仓库**没有任何 commit**（`git log` 报无提交），不要 `git commit`、不要 `git stash`；差异对照一律用 `.backup/` 里的副本。
5. `web/dist` 是构建产物，改完 `web/src` 必须重新 `npm run build`，否则 8641 上看到的还是旧界面。
6. 境外调用（Codex）必须走本机代理 `127.0.0.1:65532`；国内接口（deepseek 等）直连，所以代理只 export 给 Codex 那一步用。
7. `.venv/bin/python` 的 shebang 是绝对路径，项目迁移后已修好；用 `.venv/bin/python`，不要用系统 `python3`（那是 Hermes 自己的 3.14 运行时）。

---

## 7. 验收清单（全 ✅ 才算完成）

- [ ] `ui-design/tokens.json` / `DESIGN.md` 已是 v2 取值，且 `app.css`、`tailwind.theme.css`、`preview.html` 由生成器重出（不是手改）
- [ ] 首页有 hero 带 + 4 张快捷入口卡，且入口点击进入对应既有模式（无新功能、无假数据）
- [ ] 卡片有柔和投影、可点击卡 hover 上抬；区块用 `surface-band` 分层
- [ ] 主按钮/进度条为蓝→青渐变；所有 tab/筛选为胶囊两类形态
- [ ] 无深色页脚、无等宽数字（决策 3）
- [ ] `[data-theme="dark"]` 存在且新增令牌有暗色补值，暗色截图可读
- [ ] `make lint` ✅、`make verify-fast` ✅（18 套离线回归 + 前端构建全绿）
- [ ] `http://127.0.0.1:8641/` 返回 200，6 页浅色 + 2 页暗色截图已存 `docs/ui-v2-shots/`
- [ ] `docs/UI_V2_REPORT.md` 已写，含真实命令输出与遗留问题
- [ ] 未改动 `server/**`、未做 git commit、`.backup/` 备份仍在
