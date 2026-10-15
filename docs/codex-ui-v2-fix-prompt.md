# UI v2 三处修正（给 Codex CLI 的提示词）

> 用法：`cd /path/to/slidecraft && codex exec --skip-git-repo-check --sandbox workspace-write -C /path/to/slidecraft -- "$(cat docs/codex-ui-v2-fix-prompt.md)"`

---PROMPT---

你在 `/path/to/slidecraft`（SlideCraft，React 19 + TS + Vite + Tailwind v4，设计令牌在 `ui-design/`，令牌的生成器在 `tools/`）。UI v2 已上线，用户实机复核后提了三条，**只做这三条，不要顺手改别的**。

## 修正 1：首页 hero 的装饰图形压到了内容（要重新排布）
现状：`tools/gen_ui_css.py` 模板生成的 `.hero::after` 是一个 330×330 的圆形光斑（`right:-70px; top:-90px`），而 `.hero-content` 没有任何宽度约束 → 右上角的状态行与右下角的「快捷入口」卡（`.quick{margin-top:-30px}`，压在 hero 下沿）都压在这块装饰上。

要求：
- `.hero-content` 加宽度约束，任何视口下正文列都不许进入右侧装饰区：
  ```css
  .hero-content { position: relative; z-index: 3; max-width: 720px; }
  @media (min-width: 1200px) { .hero-content { max-width: min(720px, calc(100% - 400px)); } }
  ```
  （**必须**带这个媒体查询：小屏下 `calc(100% - 400px)` 会算成负数，不能无条件套用。）
- 装饰光斑收进「右上角留白区」，且不与 hero 下沿（快捷卡压住的那 30px）重叠：
  ```css
  .hero::after { content: ""; position: absolute; pointer-events: none; right: -140px; top: -170px; width: 420px; height: 420px; border-radius: 50%; background: radial-gradient(circle at 34% 66%, rgba(59,141,247,.26), rgba(40,160,248,.05) 60%, transparent 72%); }
  ```
- `.hero` 内边距改为 `padding: 40px 44px 56px;`（原来 60px 的下内边距是为右上状态行留的，见修正 2）。
- 窄屏（`@media (max-width: 900px)`）把光斑透明度降到 `.5`，避免小屏上压住文字。

## 修正 2：右上角「运行状态」出现了两处，只保留一处
- 现有两处：`web/src/components/AppShell.tsx` 顶栏里的 `<ProviderStatus />`（保留），以及 `web/src/pages/HomePage.tsx` 里 hero 内部的 `<div className="hero-status"><ProviderStatus /></div>`（**删除**）。
- 删掉 `HomePage.tsx` 里因此不再使用的 `ProviderStatus` 导入（`ProviderHealth` 由 AppShell 提供，首页若还有别的用途才保留导入，否则一并清掉）。`tsc` 不能留未使用的导入。
- 删掉生成器模板里的 `.hero-status` 规则以及媒体查询中 `.hero-status` 那一段（`ui-design/app.css` 是生成产物，**只改模板再重出**，不要手改 app.css）。
- 顶栏那一个的形态、文案、行为保持不变（用户这轮没要求改它的样子）。

## 修正 3：运行状态浮层缺少「点空白处 / Esc 自动收起」
现状：`web/src/components/ProviderStatus.tsx` 只有点击触发器开合（`aria-expanded={open}`），点页面空白处不会关。
要求（React 19 + TS，函数组件）：
- 用 `useRef<HTMLDivElement>` 包住触发器 + 浮层（现有外层已是 `<div className="relative">`，把 ref 挂上去）。
- `useEffect`（依赖 `open`，`open === false` 时直接 return）里挂两个监听：
  - `document.addEventListener('pointerdown', handler)`：`event.target` 不在 ref 容器内（`!ref.current?.contains(target as Node)`）→ `setOpen(false)`；
  - `document.addEventListener('keydown', handler)`：`event.key === 'Escape'` → `setOpen(false)`；
  - 清理函数里 `removeEventListener` 两个监听，不要泄漏。
- 关闭后 `aria-expanded` 自然回落为 `false`；不要改浮层里的内容与按钮。
- 顺手检查 `web/src` 里**其它**手写浮层（下拉/弹窗）是否有同样问题；有就按同样规格补上，没有就说明「无其它浮层」——不要为了凑数去改无关组件。

## 铁律
1. 只改上面点名的文件；`server/**` 一律不动；不新增 npm 依赖。
2. 行为零改动：请求、状态机、SSE、路由、文案、`aria-*` 一律保持（除修正 3 明确新增的关闭行为）。
3. `ui-design/app.css`、`ui-design/tailwind.theme.css`、`ui-design/preview.html` 都是**生成产物**：改 `tools/gen_ui_css.py` 模板后，用
   `.venv/bin/python tools/gen_ui_css.py && .venv/bin/python tools/gen_ui_preview.py`
   重出，不要手改。
4. 不要 `git commit` / `git stash`（仓库无任何 commit）。

## 自检（必须真跑）
```bash
cd /path/to/slidecraft
.venv/bin/python tools/gen_ui_css.py && .venv/bin/python tools/gen_ui_preview.py
npm --prefix web run typecheck && npm --prefix web run build
make lint
```
任一项失败就修到通过；确实改不动就在结尾如实说明真实报错。

## 结束
用**中文**回复一份简报（≤12 行）：改了哪些文件、每条修正怎么落的（引到具体 CSS 规则/函数名）、自检命令的真实结果、有没有没做的事。
