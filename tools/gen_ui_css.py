# -*- coding: utf-8 -*-
"""从 tokens.json（DTCG）生成：
  ui-design/app.css             —— CSS 变量 + 基础样式 + 组件类（无框架依赖）
  ui-design/tailwind.theme.css  —— Tailwind v4 @theme 片段
  ui-design/preview.html        —— 组件预览页（自包含，含明暗切换）
并计算暗色的 WCAG 对比度（如实标注）。
"""
import io, json, os
from pathlib import Path

R = str(Path(__file__).resolve().parents[1] / "ui-design")
d = json.load(io.open(os.path.join(R, "tokens.json"), encoding="utf-8"))

def grp(name):   # 跳过 "$type" 等元键
    return {k: v for k, v in d[name].items() if not k.startswith("$")}

colors = {k: v["$value"]["hex"] for k, v in grp("color").items()}
spacing = {k: "%s%s" % (v["$value"]["value"], v["$value"]["unit"]) for k, v in grp("spacing").items()}
rounded = {k: "%s%s" % (v["$value"]["value"], v["$value"]["unit"]) for k, v in grp("rounded").items()}
typo = {}
for k, v in grp("typography").items():
    fs = v["$value"]["fontSize"]
    typo[k] = dict(size="%s%s" % (fs["value"], fs["unit"]), w=v["$value"]["fontWeight"], f=v["$value"]["fontFamily"])

DARK = {
    "surface-band": "#1E2330", "border-strong": "#333A4B",
    "brand-grad-from": "#3C74C9", "brand-grad-to": "#3C74C9", "secondary": "#A3AAB8",
    "neutral": "#12151C", "surface": "#1A1E27", "surface-alt": "#222634", "surface-tag": "#23304A",
    "border": "#2C3241", "divider": "#2C3241", "ink": "#E8EBF2", "ink-sub": "#A3AAB8", "ink-muted": "#8A93A3",
    "primary": "#3C74C9", "accent-strong": "#3C74C9", "accent": "#4C93FF", "accent-tint-ink": "#9CC4FF",
    "success-bg": "#0F2A18", "success-ink": "#4ADE80", "warn-bg": "#2E2210", "warn-ink": "#FBBF24",
    "danger-bg": "#331A1A", "danger-ink": "#F87171",
}

def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
def lum(h):
    h = h.lstrip("#"); r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
    return 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)
def cr(a, b):
    la, lb = lum(a), lum(b); hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

print("=== 暗色对比度（v2）===")
dark_checks = [
    ("文字 on 卡片", DARK["ink"], DARK["surface"]), ("辅助文字 on 卡片", DARK["ink-sub"], DARK["surface"]),
    ("白字 on 主按钮", "#FFFFFF", DARK["primary"]), ("链接蓝 on 卡片", DARK["accent-tint-ink"], DARK["surface"]),
    ("成功字 on 成功底", DARK["success-ink"], DARK["success-bg"]), ("警告字 on 警告底", DARK["warn-ink"], DARK["warn-bg"]),
    ("危险字 on 危险底", DARK["danger-ink"], DARK["danger-bg"]),
]
for name, fg, bg in dark_checks:
    r = cr(fg, bg)
    print("  %-20s %-8s on %-8s %.2f:1 %s" % (name, fg, bg, r, "✅" if r >= 4.5 else "❌ 需调整"))

vars_light = "\n".join("  --color-%s: %s;" % (k, v) for k, v in colors.items())
vars_dark = "\n".join("  --color-%s: %s;" % (k, v) for k, v in DARK.items())
sp_vars = "\n".join("  --spacing-%s: %s;" % (k, v) for k, v in spacing.items())
rd_vars = "\n".join("  --radius-%s: %s;" % (k, v) for k, v in rounded.items())
ty_vars = "\n".join("  --text-%s: %s;\n  --text-%s--weight: %s;\n  --text-%s--font: \"%s\";" % (k, v["size"], k, v["w"], k, v["f"]) for k, v in typo.items())

APP_CSS = f"""/* ============================================================
   SlideCraft UI 令牌 —— 由 tokens.json 与生成器模板导出（勿手改）
   生成来源：W3C DTCG tokens.json；版本：v2
   用法：任何前端直接 <link rel="stylesheet" href="app.css"> 即可拿到令牌与组件类
   ============================================================ */

:root {{
  /* —— 颜色—— */
{vars_light}

  /* —— 间距 / 圆角 —— */
{sp_vars}
{rd_vars}

  /* —— 字体与字号 —— */
  --font-sans: "PingFang SC", "Source Han Sans SC", system-ui, -apple-system, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
{ty_vars}

  /* —— 卡片 / 悬停 / 浮层阴影 —— */
  --shadow-card: 0 1px 2px rgba(16,40,90,.04), 0 8px 24px rgba(16,40,90,.05);
  --shadow-hover: 0 4px 10px rgba(16,40,90,.07), 0 18px 44px rgba(16,40,90,.10);
  --shadow-overlay: 0 1px 2px rgba(30,35,46,.04), 0 8px 24px rgba(30,35,46,.06);
  --color-ledger-divider: #EEF4FE;
  --dur-fast: 140ms;
}}

/* —— 暗色（v2）：令牌级覆盖，组件无需改动 —— */
[data-theme="dark"] {{
{vars_dark}
  --color-ledger-divider: #2C3241;
  --shadow-card: 0 1px 2px rgba(0,0,0,.40), 0 8px 24px rgba(0,0,0,.35);
  --shadow-hover: 0 6px 14px rgba(0,0,0,.45), 0 18px 44px rgba(0,0,0,.50);
  --shadow-overlay: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.5);
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--color-neutral); color: var(--color-ink);
  font-family: var(--font-sans); font-size: var(--text-body-md); line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}}

/* ============ 组件类（与 DESIGN.md 的 25 个组件一一对应） ============ */
/* 数字继承正文字体，仅启用表格数字 */
.num, td.num, .metric-value {{ font-feature-settings: "tnum"; }}

/* 卡片 */
.card {{
  background: var(--color-surface); color: var(--color-ink);
  border: 1px solid var(--color-border); border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-card);
}}
.card-title {{ font-size: var(--text-h2); font-weight: var(--text-h2--weight); margin: 0 0 var(--spacing-sm); }}
.card-desc {{ color: var(--color-secondary); margin: 0 0 var(--spacing-md); }}

/* 按钮 */
.btn {{
  display: inline-flex; align-items: center; gap: var(--spacing-xs);
  height: 40px; padding: 0 var(--spacing-md); border-radius: var(--radius-md);
  font-family: inherit; font-size: var(--text-body-md); cursor: pointer;
  border: 1px solid transparent; transition: background var(--dur-fast), border-color var(--dur-fast), transform var(--dur-fast);
}}
.btn:focus-visible {{ outline: 2px solid var(--color-accent); outline-offset: 2px; }}
.btn:active {{ transform: scale(.99); }}
.btn-primary {{ background: linear-gradient(92deg, var(--color-brand-grad-from), var(--color-brand-grad-to)); color: #fff; box-shadow: 0 6px 16px rgba(32,104,240,.28); }}
.btn-primary:hover {{ filter: brightness(.96); }}
.btn-secondary {{ background: var(--color-surface); color: var(--color-ink); border-color: var(--color-border-strong); }}
.btn-secondary:hover {{ background: var(--color-surface-alt); }}
.btn-ghost {{ background: transparent; color: var(--color-accent-strong); }}
.btn-ghost:hover {{ background: var(--color-surface-tag); }}
.btn[disabled], .btn.is-disabled {{ opacity: .5; cursor: not-allowed; }}

/* 标签 / 角标 */
.tag {{
  display: inline-block; padding: 2px var(--spacing-sm); border-radius: var(--radius-sm);
  background: var(--color-surface-tag); color: var(--color-accent-tint-ink); font-size: var(--text-body-sm);
}}
.badge {{
  display: inline-block; padding: 2px var(--spacing-sm); border-radius: var(--radius-sm); color: #fff;
  background: linear-gradient(90deg, var(--color-badge-from), var(--color-badge-to)); font-size: var(--text-caption);
}}

/* 输入 */
.input {{
  height: 40px; width: 100%; padding: 0 var(--spacing-md); border-radius: var(--radius-md);
  border: 1px solid var(--color-border-strong); background: var(--color-surface); color: var(--color-ink);
  font-family: inherit; font-size: var(--text-body-md);
}}
.input::placeholder {{ color: var(--color-ink-muted); }}
.input:focus {{ outline: none; border-color: var(--color-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 18%, transparent); }}
.input.is-error {{ border-color: var(--color-danger-ink); }}

/* 区块 / 链接 / 指标 */
.panel-alt {{ background: var(--color-surface-alt); border-radius: var(--radius-md); padding: var(--spacing-md); }}
.link {{ color: var(--color-accent-strong); text-decoration: none; cursor: pointer; }}
.link:hover {{ text-decoration: underline; }}
.metric {{ display: flex; flex-direction: column; gap: 2px; }}
.metric-label {{ color: var(--color-ink-sub); font-size: var(--text-caption); }}
.metric-value {{ font-size: 1.25rem; font-weight: 600; }}

/* 进度条 */
.progress {{ height: 8px; border-radius: 999px; background: var(--color-surface-alt); overflow: hidden; }}
.progress > i {{ display: block; height: 100%; border-radius: 999px; background: linear-gradient(92deg, var(--color-accent), var(--color-tertiary)); }}
.progress.is-decor > i {{ background: linear-gradient(92deg, var(--color-accent), var(--color-tertiary)); }}

/* 步骤条 */
.steps {{ display: flex; gap: var(--spacing-sm); flex-wrap: wrap; align-items: center; }}
.step {{
  display: inline-flex; align-items: center; gap: 6px; padding: 6px var(--spacing-sm);
  border-radius: 999px; font-size: var(--text-body-sm);
}}
.step.done {{ background: var(--color-surface-tag); color: var(--color-accent-tint-ink); }}
.step.active {{ background: linear-gradient(92deg, var(--color-brand-grad-from), var(--color-brand-grad-to)); color: #fff; }}
.step.pending {{ background: var(--color-surface-alt); color: var(--color-ink-sub); }}
.step.error {{ background: var(--color-danger-bg); color: var(--color-danger-ink); }}
.step-sep {{ color: var(--color-border); }}

/* 状态胶囊 */
.status {{ display: inline-block; padding: 2px var(--spacing-sm); border-radius: 999px; font-size: var(--text-caption); }}
.status-success {{ background: var(--color-success-bg); color: var(--color-success-ink); }}
.status-warn {{ background: var(--color-warn-bg); color: var(--color-warn-ink); }}
.status-danger {{ background: var(--color-danger-bg); color: var(--color-danger-ink); }}
.status-info {{ background: var(--color-surface-tag); color: var(--color-accent-tint-ink); }}

/* 缩略图网格（业务组件） */
.thumb-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(168px, 1fr)); gap: var(--spacing-md); }}
.thumb {{
  position: relative; aspect-ratio: 16/9; border-radius: var(--radius-md); border: 1px solid var(--color-border);
  background: var(--color-surface-alt); display: flex; align-items: center; justify-content: center;
  color: var(--color-ink-muted); font-size: var(--text-caption); cursor: pointer; overflow: hidden;
}}
.thumb.selected {{ border: 2px solid var(--color-accent); background: color-mix(in srgb, var(--color-accent) 10%, var(--color-surface)); }}
.thumb .corner {{ position: absolute; top: 6px; left: 6px; }}
.thumb .pageno {{ position: absolute; bottom: 6px; right: 8px; color: var(--color-ink-sub); }}

/* 表格（账本） */
table.ledger {{ width: 100%; border-collapse: separate; border-spacing: 0; border: 1px solid var(--color-border); box-shadow: var(--shadow-card); background: var(--color-surface); border-radius: var(--radius-lg); overflow: hidden; }}
table.ledger th {{ background: var(--color-surface-alt); color: var(--color-ink-sub); font-weight: 500; text-align: left; padding: var(--spacing-sm) var(--spacing-md); font-size: var(--text-body-sm); }}
table.ledger td {{ padding: var(--spacing-sm) var(--spacing-md); border-top: 1px solid var(--color-ledger-divider); }}

.divider {{ height: 1px; background: var(--color-divider); border: 0; }}

/* 空态 / 错误态 / Toast */
.empty {{ text-align: center; padding: var(--spacing-xl); color: var(--color-ink-sub); }}
.error-box {{ background: var(--color-danger-bg); color: var(--color-danger-ink); border-radius: var(--radius-md); padding: var(--spacing-md); }}
.toast {{
  display: inline-flex; align-items: center; gap: var(--spacing-sm); background: var(--color-surface);
  border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-sm) var(--spacing-md);
  box-shadow: var(--shadow-overlay);
}}
/* v2：分组色带与两类胶囊 */
.band {{ background: var(--color-surface-band); border: 1px solid var(--color-divider); border-radius: var(--radius-xl); padding: 24px; }}
.card-interactive, .thumb {{ box-shadow: var(--shadow-card); transition: transform var(--dur-fast), box-shadow var(--dur-fast); }}
.card-interactive:hover, .thumb:not(.cursor-not-allowed):hover {{ transform: translateY(-2px); box-shadow: var(--shadow-hover); }}
.tabs {{ display: inline-flex; flex-wrap: wrap; gap: 6px; padding: 4px; border-radius: 999px; background: var(--color-surface-alt); border: 1px solid var(--color-border); }}
.tabs > button {{ border-radius: 999px; color: var(--color-ink-sub); background: transparent; border-color: transparent; }}
.tabs > button[aria-selected="true"], .tabs > button[aria-pressed="true"], .tabs > button.is-active {{ background: var(--color-surface); color: var(--color-accent-tint-ink); box-shadow: var(--shadow-card); }}
.chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.chips > button, button.chip {{ border: 1px solid transparent; border-radius: 999px; background: var(--color-surface-tag); color: var(--color-accent-tint-ink); padding: 6px 14px; font: inherit; cursor: pointer; }}
.chips > button[aria-pressed="true"], .chips > button.is-active, button.chip[aria-pressed="true"] {{ background: linear-gradient(92deg, var(--color-brand-grad-from), var(--color-brand-grad-to)); color: #fff; box-shadow: 0 6px 16px rgba(32,104,240,.28); }}
/* 首页 hero 模块已移除（用户要求），相关 .hero* 规则一并删除 */
/* 生成方式：竖向轨道（左侧导轨），替代原「tabs + 重复的 quick 卡片」两套按钮 */
.mode-rail {{ display: flex; flex-direction: column; gap: 8px; padding: 8px; border-radius: var(--radius-xl); background: var(--color-surface-alt); border: 1px solid var(--color-border); align-self: start; }}
.mode-rail > button {{ display: flex; flex-direction: column; align-items: center; gap: 7px; padding: 14px 8px; border: 1px solid transparent; border-radius: var(--radius-md); background: transparent; color: var(--color-ink-sub); font: inherit; font-weight: 600; cursor: pointer; transition: background var(--dur-fast), color var(--dur-fast), box-shadow var(--dur-fast); }}
.mode-rail > button:hover {{ color: var(--color-ink); }}
.mode-rail > button[aria-selected="true"] {{ background: var(--color-surface); color: var(--color-accent-tint-ink); box-shadow: var(--shadow-card); }}
.mode-rail-icon {{ display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: var(--radius-md); background: var(--color-surface-tag); color: var(--color-accent-tint-ink); }}
.mode-rail > button[aria-selected="true"] .mode-rail-icon {{ background: linear-gradient(92deg, var(--color-brand-grad-from), var(--color-brand-grad-to)); color: #fff; }}
.provider-trigger {{ border-radius: 999px; background: var(--color-surface-band); border-color: var(--color-border); height: auto; min-height: 32px; flex-wrap: wrap; padding: 4px 12px; }}
.provider-trigger .status {{ display: inline-flex; align-items: center; gap: 6px; background: transparent; }}
.provider-trigger .status::before {{ content: ""; width: 6px; height: 6px; flex: none; border-radius: 50%; background: currentColor; }}
.brand-mark {{ background: linear-gradient(92deg, var(--color-brand-grad-from), var(--color-brand-grad-to)); box-shadow: 0 4px 12px rgba(32,104,240,.28); }}
.metric-value {{ font-size: 26px; }}
[data-theme="dark"] .mode-rail {{ background: var(--color-surface-alt); border-color: var(--color-border-strong); }}
@media (max-width: 640px) {{ .mode-rail {{ flex-direction: row; }} .mode-rail > button {{ flex: 1 1 0; }} .band {{ padding: 16px; }} }}
button.chip:focus-visible {{ outline: 2px solid var(--color-accent); outline-offset: 2px; }}
button.chip:disabled {{ opacity: .5; cursor: not-allowed; }}
@media (prefers-reduced-motion: reduce) {{ .card-interactive:hover, .thumb:hover {{ transform: none; }} }}

"""

TAILWIND_CSS = f"""/* Tailwind v4 —— 在入口 CSS 里 @import 本文件即可获得全部令牌（ui-design/tailwind.theme.css） */
@theme {{
  /* 页面确认：参考布局中的橙色步骤与选页强调。 */
{chr(10).join("  --color-%s: %s;" % (k, v) for k, v in colors.items())}
{chr(10).join("  --spacing-%s: %s;" % (k, v) for k, v in spacing.items())}
{chr(10).join("  --radius-%s: %s;" % (k, v) for k, v in rounded.items())}
  --shadow-card: 0 1px 2px rgba(16,40,90,.04), 0 8px 24px rgba(16,40,90,.05);
  --shadow-hover: 0 4px 10px rgba(16,40,90,.07), 0 18px 44px rgba(16,40,90,.10);
  --font-sans: "PingFang SC", "Source Han Sans SC", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
{chr(10).join("  --text-%s: %s;" % (k, v["size"]) for k, v in typo.items())}
}}
"""

io.open(os.path.join(R, "app.css"), "w", encoding="utf-8").write(APP_CSS)
io.open(os.path.join(R, "tailwind.theme.css"), "w", encoding="utf-8").write(TAILWIND_CSS)
print("\n✅ app.css (%d 字节) / tailwind.theme.css (%d 字节)" % (len(APP_CSS.encode()), len(TAILWIND_CSS.encode())))

# 记录给预览页用
Path("/tmp/pm").mkdir(parents=True, exist_ok=True)
io.open("/tmp/pm/ui_ctx.json", "w", encoding="utf-8").write(json.dumps(
    {"colors": colors, "spacing": spacing, "rounded": rounded, "typo": typo, "dark": DARK}, ensure_ascii=False))
