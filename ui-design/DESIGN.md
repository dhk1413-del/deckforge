---
version: alpha
name: SlideCraft UI
description: 浅色为主的企业级蓝调工作台：近白蓝灰底 + 白卡 + 蓝主色，克制、干净、可长时间盯屏。
colors:
  # —— 四个核心语义色（DESIGN.md 规范要求）——
  primary: "#2068F0"            # 主色深档：按钮填充 / 白底蓝字（白字对比 5.0:1）
  secondary: "#5A6B87"          # 次要文字
  tertiary: "#28A0F8"           # 次强调（仅图形：进度条/插画，不承载白字）
  neutral: "#F1F6FD"            # 页面底色
  # —— 底与面 ——
  surface: "#FFFFFF"            # 卡片/面板底
  surface-alt: "#EFF4FD"        # 次级区块底（表头/进度槽/空态）
  surface-tag: "#EAF3FF"        # 标签胶囊底
  border: "#E3EBF9"             # 描边色（蓝调浅灰）
  divider: "#EBF2FE"            # 分隔线
  # —— 文字 ——
  ink: "#101828"                # 主文字
  ink-sub: "#5A6B87"            # 辅助文字
  ink-muted: "#64748F"          # 占位/禁用（压深至 AA：白底 4.60:1）
  accent-tint-ink: "#1D5FD8"   # 浅蓝底上的蓝字（4.60:1 达标）
  # —— 主色三档 ——
  accent: "#3B8DF7"             # 品牌主色：图标/描边/选中框（图形元素 3:1 即可）
  accent-strong: "#2068F0"      # 按钮填充/白底蓝字
  # —— 状态（浅底 + 深字，统一胶囊写法）——
  success-bg: "#E8FFEA"
  success-ink: "#00831F"
  warn-bg: "#FFF7E8"
  warn-ink: "#B05600"
  danger-bg: "#FFECE8"
  danger-ink: "#C63333"
  # —— 角标渐变 ——
  badge-from: "#C64676"  # 渐变起端（承白字，4.63:1 达标）
  badge-to: "#BE54DE"           # 渐变止端（仅装饰底色）
  surface-band: "#F7FAFF"
  border-strong: "#D6E4F7"
  brand-grad-from: "#2E6BF2"
  brand-grad-to: "#3E92F8"
typography:
  h1:
    fontFamily: PingFang SC
    fontSize: 1.75rem
    fontWeight: 600
    lineHeight: 1.35
  h2:
    fontFamily: PingFang SC
    fontSize: 1.25rem
    fontWeight: 600
    lineHeight: 1.4
  h3:
    fontFamily: PingFang SC
    fontSize: 1rem
    fontWeight: 600
    lineHeight: 1.5
  body-md:
    fontFamily: PingFang SC
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.65
  body-sm:
    fontFamily: PingFang SC
    fontSize: 0.8125rem
    fontWeight: 400
    lineHeight: 1.6
  caption:
    fontFamily: PingFang SC
    fontSize: 0.75rem
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: 8px
  md: 12px
  lg: 16px
  xl: 20px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  page-margin: 24px
components:
  page-bg:
    backgroundColor: "{colors.neutral}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: 24
  card-outline:
    backgroundColor: "{colors.border}"
    height: 1px
  card-title:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.h2}"
  card-desc:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
    typography: "{typography.body-md}"
  helper-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-sub}"
    typography: "{typography.body-sm}"
  placeholder-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.body-md}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: 10
    height: 40px
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 10
    height: 40px
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent-strong}"
    rounded: "{rounded.sm}"
    padding: 8
  tag:
    backgroundColor: "{colors.surface-tag}"
    textColor: "{colors.accent-tint-ink}"
    rounded: "{rounded.sm}"
    padding: 4
  badge:
    backgroundColor: "{colors.badge-from}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: 4
  badge-gradient-end:
    backgroundColor: "{colors.badge-to}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 10
    height: 40px
  focus-ring:
    backgroundColor: "{colors.accent}"
    height: 2px
  panel-alt:
    backgroundColor: "{colors.surface-alt}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 16
  link-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent-strong}"
    typography: "{typography.body-md}"
  metric-number:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
  progress-bar:
    backgroundColor: "{colors.tertiary}"
    rounded: "{rounded.sm}"
    height: 8px
  step-active:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: 6
  step-done:
    backgroundColor: "{colors.surface-tag}"
    textColor: "{colors.accent-tint-ink}"
    rounded: "{rounded.sm}"
    padding: 6
  step-pending:
    backgroundColor: "{colors.surface-alt}"
    textColor: "{colors.ink-sub}"
    rounded: "{rounded.sm}"
    padding: 6
  status-success:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success-ink}"
    rounded: "{rounded.sm}"
    padding: 2
  status-warn:
    backgroundColor: "{colors.warn-bg}"
    textColor: "{colors.warn-ink}"
    rounded: "{rounded.sm}"
    padding: 2
  status-danger:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger-ink}"
    rounded: "{rounded.sm}"
    padding: 2
  divider-line:
    backgroundColor: "{colors.divider}"
    height: 1px
---

## Overview

浅色为主的「蓝色云平台风」：页面底 `#F1F6FD`、白卡、单一品牌蓝；hero、柔和投影与区块色带形成层次。首页采用 hero + 快捷入口条，其余页面保持工作台布局。页脚保持浅色小字。

## Colors

以 front matter 与 tokens.json 为取值表。主蓝 `#2068F0`、图形蓝 `#3B8DF7`、青蓝 `#28A0F8`；渐变端 `#2E6BF2` / `#3E92F8`。色带 `#F7FAFF`、输入描边 `#D6E4F7`、卡片描边 `#E3EBF9`。主文字 `#101828`、辅助文字 `#5A6B87`、占位符 `#64748F`、浅蓝底文字 `#1D5FD8`。状态与角标色保持原值。

暗色保留 neutral `#12151C`、surface `#1A1E27`、surface-alt `#222634`、surface-tag `#23304A`、border/divider `#2C3241`、ink `#E8EBF2`、ink-sub `#A3AAB8`、accent `#4C93FF`、primary/accent-strong `#3C74C9`、accent-tint-ink `#9CC4FF`。新增 surface-band `#1E2330`、border-strong `#333A4B`；暗色渐变两端均用 `#3C74C9`，维持白字对比度。

## Typography

中文采用 PingFang SC，回落思源黑体与系统字体，正文 14px。数字继承正文字体，`.num` 只保留 `font-feature-settings:"tnum"`；日志/代码可使用 `--font-mono`。

## Layout

间距阶 4/8/16/24/32，页面边距 24px；侧栏 228px，顶栏 60px。成组内容用 surface-band、xl 圆角与 20/24px 内边距分层。

## Elevation & Depth

卡片带柔和投影：`0 1px 2px rgba(16,40,90,.04), 0 8px 24px rgba(16,40,90,.05)`。
可点击卡片 hover 上移 2px，投影为 `0 4px 10px rgba(16,40,90,.07), 0 18px 44px rgba(16,40,90,.10)`；展示卡不抬起。
暗色 card：`0 1px 2px rgba(0,0,0,.40), 0 8px 24px rgba(0,0,0,.35)`；hover：`0 6px 14px rgba(0,0,0,.45), 0 18px 44px rgba(0,0,0,.50)`。overlay 保持原值。

## Shapes

圆角 sm 8px、md 12px、lg 16px、xl 20px；状态与步骤用胶囊。

## Components

主按钮用品牌渐变与蓝色投影；次级按钮白底加 border-strong。tabs 用 surface-alt 底与白底选中态，chips 用 surface-tag 底与品牌渐变选中态。进度条 8px、全圆角，accent → tertiary 渐变。账本表头 surface-alt + ink-sub，行分隔 `#EEF4FE`，外框 border + lg + shadow-card。

## Do's and Don'ts

- ✅ 白卡、蓝底、单一蓝主色；卡片柔和投影与色带分层。
- ✅ 浅蓝底蓝字用 accent-tint-ink；状态用浅底深字；保留所有 aria、键盘与错误提示。
- ✅ 暗色主按钮保持 #3C74C9（白字 4.63:1），数字继承正文字体。
- ❌ 不新增深色页脚，不切换等宽数字，不引入第二品牌色、纯黑文字或中性灰描边。
- ❌ 不用 #8698B5 作占位符，不把 #4C93FF 作暗色白字按钮底。
- ❌ 不满屏渐变，渐变限 hero、主按钮、进度条、角标。
