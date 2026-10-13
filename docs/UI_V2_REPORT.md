# DeckForge UI v2 实施与验收报告

日期：2026-10-08（定时作业，07:0x 完成）。执行方：Codex CLI 负责全部代码改动；Hermes 负责备份、独立复核与实机视觉验收。
结论：**成功** —— v2 已落地并通过全部验收清单（`make lint` ✅、`make verify-fast` 15/15 ✅、8641 实机 6 浅 + 2 暗截图 ✅、暗色与对比度达标 ✅）。

---

## 1. 执行步骤与真实结果

| Step | 内容 | 结果 |
|---|---|---|
| 0 | 备份 `ui-design web/src tools docs` → `.backup/ui-v2-20261008-064019/`（Hermes）＋ `.backup/ui-v2-20261008-064133/`（Codex 读 runbook 后重复执行了一次，指针 `LATEST_UI_V2` 指向后者） | ✅ 两份均为**改动前 v1 快照**（逐文件比对一致），回滚可用 |
| 1 | Codex 额度确认（代理 `127.0.0.1:65532`，`--sandbox read-only`，提示词「回复：pong」） | ✅ 输出 `pong`，退出码 0（耗时约 30s，未触发重试） |
| 2 | `codex exec --sandbox workspace-write -- "$(cat docs/codex-ui-v2-prompt.md)"` | ✅ 退出码 0，tokens 116,773，改动 5 类文件（见 §2） |
| 3 | Hermes 独立复核（令牌 grep / 生成器幂等 / lint / verify-fast / build / 备份 diff） | ✅ 全部通过（见 §3） |
| 4 | 实机视觉验收（curl + 浏览器 8 屏截图） | ✅ 200；8 张截图见 `docs/ui-v2-shots/`；发现 1 处可见偏差已修（见 §5） |
| 4b | 小改（hero 装饰光斑形状）二次交给 Codex | ✅ 退出码 0，仅动 `tools/gen_ui_css.py` 模板 2 行（生成物重出），web/src 未再改动 |
| 5 | 本报告 | ✅ |

未做：`git commit`（仓库无任何 commit，按约定不提交）；未改 `server/**`（`find server -newermt` 为空）。

---

## 2. 改动清单（与 `.backup/ui-v2-20261008-064133` 逐文件 diff 得出，共 20 个文件）

- **设计令牌**：`ui-design/tokens.json`、`ui-design/DESIGN.md`
- **生成产物（由生成器重出，未手改）**：`ui-design/app.css`、`ui-design/tailwind.theme.css`、`ui-design/preview.html`
- **生成器**：`tools/gen_ui_css.py`、`tools/gen_ui_preview.py`（旧硬编码路径 → `Path(__file__).parents[1]/"ui-design"`；模板升 v2）
- **应用层（12）**：`web/src/index.css`、`components/{AppShell,ProviderStatus,ProjectWorkbench,Metric,NotesWorkbench,StylePackCard}.tsx`、`pages/{HomePage,WizardPage,StylesPage,UsagePage,SettingsPage}.tsx`
- **新增**：`docs/UI_V2_REPORT.md`（本文件）、`docs/ui-v2-shots/`（8 张截图）

未改动：`server/**`、`style-packs/**`、`data/**`、`samples/**`、`web/dist/**`（仅由 `npm run build` 生成）、依赖清单（无新增 npm 包）。

---

## 3. 验收命令真实输出（Hermes 亲自跑）

### 3.1 令牌落地
```text
ui-design/tokens.json:14  "hex": "#2068F0"        ui-design/tokens.json:135 "hex": "#64748F"
ui-design/tokens.json:146 "hex": "#1D5FD8"        ui-design/tokens.json:259 "surface-band" → #F7FAFF
ui-design/app.css:32  --color-surface-band: #F7FAFF;   app.css:72 --shadow-card: 0 1px 2px rgba(16,40,90,.04), 0 8px 24px rgba(16,40,90,.05);
ui-design/app.css:81  [dark] --color-surface-band: #1E2330;   app.css:106 [dark] --shadow-card: 0 1px 2px rgba(0,0,0,.40), 0 8px 24px rgba(0,0,0,.35);
ui-design/tailwind.theme.css:26 --color-surface-band: #F7FAFF; :27 border-strong #D6E4F7; :28/29 brand-grad #2E6BF2→#3E92F8; :39 --radius-xl: 20px
ui-design/app.css:120 .num, td.num, .metric-value { font-feature-settings: "tnum"; }   ← 不再切等宽字体
```
与样式稿逐值对齐：`ui-design/preview-v2.html` 的 `radial-gradient(130% 150% at 86% 6%,#D6E8FF…,#FFFFFF)`、`linear-gradient(92deg,#2E6BF2,#3E92F8)`、`0 1px 2px rgba(16,40,90,.04),0 8px 24px rgba(16,40,90,.05)` 与 `app.css` 输出完全一致。

### 3.2 生成器幂等（先 css 后 preview，连跑两次）
```text
ui-design/app.css: OK
ui-design/tailwind.theme.css: OK
ui-design/preview.html: OK
IDEMPOTENT_EXIT=0
=== 暗色对比度（v2）===
  文字 on 卡片  #E8EBF2 on #1A1E27 13.98:1 ✅    白字 on 主按钮 #FFFFFF on #3C74C9 4.63:1 ✅
  链接蓝 on 卡片 #9CC4FF on #1A1E27 9.34:1 ✅    成功/警告/危险字 8.83 / 9.30 / 5.82:1 ✅
✅ app.css (14677 字节) / tailwind.theme.css (1610 字节)  ✅ preview.html (34313 字节)
```

### 3.3 静态体检 + 规范验收
```text
$ make lint          → .venv/bin/python -m compileall -q server tools && npm --prefix web run typecheck   （tsc 零错误）LINT_EXIT=0
$ make verify-fast   → .venv/bin/python tools/verify_all.py
  ✅ test_beautify_v2 13 ✅ test_page_import 21 ✅ test_source_pages 12 ✅ test_db_update 8
  ✅ test_editppt_engine 47 ✅ test_editppt_validation_race 6 ✅ test_vision_layout 15 ✅ test_native_status 12
  ✅ test_native_render 23 ✅ test_vision_parse 22 ✅ test_dashscope_image 12 ✅ test_image_retry 22
  ✅ test_slide_notes 29 ✅ test_style_builder 68/68 ✅ web build ✓ built in 851ms
  15 项检查：15 通过 / 0 失败        VERIFY_FAST_FINAL_EXIT=0        （小改后重跑，同样 15/15）
$ npm --prefix web run build → ✓ 63 modules transformed，dist/assets/index-Biu8TZv1.css 34.12 kB + index-C5HZnlUo.js 389.88 kB
```

### 3.4 线上可达
```text
curl --noproxy '*' -o /dev/null -w '%{http_code}' http://127.0.0.1:8641/            → 200
curl --noproxy '*' http://127.0.0.1:8641/api/health → {"ok":true,...,"network":{"mode":"http_proxy",...}}
服务返回的 index.html 引用 index-Biu8TZv1.css（= 修复后构建产物）→ web/dist 已生效，无需重启后端
```

### 3.5 与备份差异
```text
diff -rq .backup/ui-v2-20261008-064133/ui-design ui-design  → 5 个文件 differ（tokens/DESIGN/app.css/tailwind.theme.css/preview.html）
diff -rq .backup/ui-v2-20261008-064133/web/src  web/src     → 12 个文件 differ（无新增文件）
diff -rq .backup/ui-v2-20261008-064019/tools    tools        → gen_ui_css.py / gen_ui_preview.py（+ __pycache__）
```

---

## 4. 实机视觉验收（`docs/ui-v2-shots/`，1440×900）

| 截图 | 对照结论 |
|---|---|
| `01-home-light.png` / `07-home-dark.png` | hero 成带（实测高 282px）、右上圆形装饰光斑、右上真实供应商状态；4 张快捷卡 `margin-top:-30px` 压住 hero 下沿、`shadow-card` 柔和投影 ✅ |
| `02-wizard-light.png` | 卡片投影 + 色带（`.band` 内嵌拖拽区）+ 步骤胶囊 ✅ |
| `03-projects-light.png` | 账本表：表头 `#EFF4FD`、外框 `border` + `radius lg` + `shadow-card`，状态为胶囊 ✅ |
| `04-styles-light.png` / `08-styles-dark.png` | 筛选 `chips`（选中态蓝色渐变 + 白字，实测 `linear-gradient(92deg,#2E6BF2,#3E92F8)`；暗色 `#3C74C9`）、风格卡带投影、可点卡 hover 上抬 ✅ |
| `05-usage-light.png` | 指标卡 + 色带分组 + 账本表；数字为无衬线（非等宽）✅ |
| `06-settings-light.png` | 供应商卡 + 两类胶囊（tabs/chips）+ 输入框 `border-strong` ✅ |

计算样式实测（浏览器内 `getComputedStyle`）：`.hero::after` `border-radius:50%`、`.hero` `overflow:hidden`、`.quick` `margin-top:-30px`、卡片阴影 `rgba(16,40,90,.04) 0 1px 2px, rgba(16,40,90,.05) 0 8px 24px`、页面底 `rgb(241,246,253)`、暗色 body `rgb(18,21,28)` / 文字 `rgb(232,235,242)`。

---

## 5. 与 v1 的差异，以及三决策的落实

1. **首页**：新增渐变 hero 带（标题 22–29px + 副标 + 主次按钮 + 右上状态）+ 4 张快捷入口卡（上移压住 hero 下沿），切 `topic/editable/reskin` 与 `/styles`，复用原 mode 逻辑，**无新功能、无假数字**（只用 `/api/health` 已有字段，经 `ProviderHealth` context 与顶栏共用一次请求）。✅ 决策①
2. **配色**：主蓝 `#1A63F9→#2068F0`、accent `#1E78FA→#3B8DF7`、tertiary `#26ABFE→#28A0F8`、页底 `#F5F6FC→#F1F6FD`、ink `#1E232E→#101828`、占位符 `#73757C→#64748F`；新增 `surface-band/border-strong/brand-grad-from/to`、`shadow-card/shadow-hover`、`radius-xl`。
3. **卡片/色带/按钮/胶囊/进度条/表格/侧栏顶栏**：按 runbook §3 的 10 条规则改造（卡片投影 + 可点卡 hover 上抬 2px；区块用 `surface-band` 分层；主按钮与 chip 选中态蓝色渐变 + 蓝投影；进度条 `accent→tertiary` 渐变；侧栏 228px + 品牌渐变方块 + 选中项浅蓝胶囊；顶栏 60px + 状态胶囊）。
4. **暗色**：`[data-theme="dark"]` 保留并补齐新令牌（`surface-band #1E2330`、`border-strong #333A4B`、渐变两端与主按钮 `#3C74C9`、暗色阴影），实测截图可读、对比度 4.63:1 以上。✅ 决策②
5. **未保留**：无深色页脚（页脚仍是浅色小字行 `text-caption text-ink-muted`）；`.num` 只保留 `font-feature-settings:"tnum"`，不再切 JetBrains Mono；代码块仍可用 `--font-mono` 令牌。✅ 决策③
6. 行为零改动：请求/状态机/SSE/路由/文案/`aria-*`/键盘可用性/错误提示均未动（只改 `className` 与结构）。

---

## 6. 遗留问题、偏差与未采纳项（如实记录）

1. **hero 装饰光斑形状**：首轮实现为 240×180 圆角矩形盒子，浅色页面上能看到直角边界，与样式稿不一致（截图留档见对话记录）。已交 Codex 二次小改为样式稿的 330×330 圆形外溢（`.hero{overflow:hidden}` + `::after{border-radius:50%}`），`01/07` 两张截图已重拍确认。
2. **首页状态胶囊与顶栏状态胶囊重复**：runbook §3.1（hero 右上状态）与 §3.9（顶栏状态胶囊）同时要求，实现按两条都做了；两者共用同一次 `/api/health` 请求与 20s 轮询，无重复请求、无假数据。视觉上有冗余感，如需只留一处请指示。
3. **快捷入口卡**：未照抄样式稿的副标题与「本月生成 9 / 生图 27 / ¥0.0000」示例数字（铁律「不伪造数据」+ runbook §3.1「不要放假的统计数字」），且 3 张模式卡共用一个 `IconSparkles` 图标（样式稿用不同 emoji 图标）——属取舍，未改。
4. **样式稿 vs 决定的冲突**：`ui-design/preview-v2.html` 的说明文字里列了「深色页脚」，与用户决策③冲突，按决策③未采纳（样式稿未改，避免额外改动）。
5. **过期注释**：`web/src/lib/format.ts:1` 注释仍写「数字一律等宽（class="num"）」，与新规则不符；仅注释，无功能影响，未改（不在 Codex 改动范围内）。
6. **Codex 自检的两处假阴性**（非代码问题，记录以免误读）：① Codex 在自己进程内跑 `make verify-fast/verify` 时 `test_source_pages` 挂住（退出码 130/124）——它同时并行跑多条命令、CPU 争用所致；Hermes 在干净负载下重跑该用例 12/12 通过、`verify-fast` 15/15 通过。② Codex 用 `curl http://127.0.0.1:8641/` 得到 `000`，是因为它把 `http_proxy=127.0.0.1:65532` 带进了本地请求；加 `--noproxy '*'` 后为 200。
7. **备份目录多了一份**：Codex 读到 runbook §4 Step 0 后重复执行了备份，产生 `.backup/ui-v2-20261008-064133` 并覆盖 `.backup/LATEST_UI_V2`。两份都是改动前 v1 快照（Hermes 已逐文件比对一致），回滚指针指向的 064133 **有效**，可放心使用。
8. **截图工具偶发不稳定**：浏览器渲染进程在连续截图后曾崩溃/超时，重启浏览器后 8 张截图全部重拍成功；`01/07` 是修复后版本，其余 6 张是小改前的版本（该小改只影响 `.hero`，不影响这 6 页）。
9. 未做的验收项：`make verify`（含线上只读冒烟）未跑——runbook 的验收门是 `verify-fast`，且该命令会写库/调网络；如需可另跑。

---

## 7. 回滚方式

```bash
cd /workspace/智能ppt生成工作台
B=.backup/ui-v2-$(cat .backup/LATEST_UI_V2)      # → .backup/ui-v2-20261008-064133（v1 快照）
rm -rf ui-design web/src tools docs
cp -a $B/ui-design $B/web/src $B/tools $B/docs .
npm --prefix web run build                        # 复原 web/dist（8641 直接读磁盘，无需重启后端）
```
注意：`docs/` 会被替换为 v1 版本，`docs/UI_V2_REPORT.md` 与 `docs/ui-v2-shots/`（本次新增）会被移出——如需保留请先 `cp -a docs/ui-v2-shots docs/UI_V2_REPORT.md /tmp/`。

---

## 7. 追加修正（2026-10-08 17:45–18:0x，用户实机复核后）

用户上线复核提了三条，均已在**真机**修复并验证（非预览稿）。执行：Codex CLI（提示词 `docs/codex-ui-v2-fix-prompt.md`）改代码，Hermes 独立复核；备份 `.backup/ui-v2fix-<时间戳>/`（含 docs/tools/ui-design）与 `.backup/ui-v2fix-post-<时间戳>/`（含 web/src/tools/ui-design）。

| # | 问题 | 修复 | 证据 |
|---|---|---|---|
| 1 | 首页按钮/内容压在 hero 装饰图形上 | `.hero-content` 加 `max-width:720px` + `@media (min-width:1200px){max-width:min(720px,calc(100% - 400px))}`；`.hero::after` 收到右上角留白区（`right:-140px;top:-170px;420×420;pointer-events:none`）；`.hero` 内边距 `40px 44px 56px`；窄屏降低装饰不透明度 | `ui-design/app.css:237-240`（生成产物，改的是 `tools/gen_ui_css.py` 模板） |
| 2 | 右上角「运行状态」出现两处 | 删除 `HomePage.tsx` hero 内的 `<ProviderStatus/>`（及其导入）与 `.hero-status` 规则；只保留顶栏那一处 | 终态 `grep -c hero-status` = 0/0；实机 `document.querySelectorAll('.provider-trigger').length === 1`、`.hero-status === 0` |
| 3 | 状态浮层点空白处不收起 | `ProviderStatus.tsx` 加 `containerRef` + `useEffect`（`pointerdown` 落在容器外 → 关闭；`Escape` → 关闭；卸载解绑） | 实机鼠标/CDP 实测：点开 `aria-expanded=true`+浮层可见 → 点页面空白 `false`+隐藏 → 再点开 → 按 Esc `false`+隐藏 |

验收（Hermes 亲自跑）：`make lint` 退出码 0；`npm --prefix web run build` ✓ 63 modules / `index-k7PudWLe.js` 393.57 kB；`.venv/bin/python tools/verify_all.py` **15 项检查：15 通过 / 0 失败**；服务 8641 实机截图确认 hero 装饰不再压内容、右上角只剩一处状态入口。

### 遗留与风险（如实记录）
1. **并行 Codex 冲突风险**：本轮期间另有一路 agent 的 Codex 在同一仓库改「PPT美化」交互（17:46–17:53）。两路改动经确认已共存（`web/src/api.ts`、`HomePage.tsx` 同时含 `beautify/origin` 与本轮修正），lint/verify 全绿；但**同一仓库并行跑多个 Codex 有互相覆盖文件的真实风险，后续必须串行**。
2. `verify_all.py` 的 web 构建已被另一路改为输出到临时目录（不再覆盖 `web/dist`）→ 现在 `make verify-fast` 不会刷新线上产物；**改完前端必须单独 `npm --prefix web run build`**，否则 8641 看到的还是旧界面（本轮已手动重建）。
3. 顶栏状态入口目前仍是「三枚状态胶囊 + ▼」的形态（本轮只删重复、未改形态）；`ui-design/preview-v2.html` 里是更简洁的「一枚胶囊 + 浮层」，若对齐样式稿需另行改造。
