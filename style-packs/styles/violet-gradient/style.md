---
version: alpha
name: Violet Gradient
description: 紫蓝渐变风：紫蓝渐变底 + 大圆角卡片 + 柔和浅色渐变卡面 + 彩色圆润图标，现代 AI 产品气质。
colors:
  primary: "#1B2030"
  secondary: "#6A7285"
  tertiary: "#4A6CF7"
  neutral: "#F7F8FE"
  bg: "#F7F8FE"
  surface: "#FFFFFF"
  accent: "#4A6CF7"
  accent-2: "#6C5CE7"
  accent-3: "#2FA8FF"
  accent-ink: "#3B46C8"
  ink: "#1B2030"
  ink-sub: "#6A7285"
  tint-lavender: "#F1EEFE"
  tint-blue: "#EAF2FF"
  tint-mint: "#E6F9F2"
  tint-peach: "#FFF1E6"
typography:
  h1:
    fontFamily: "PingFang SC"
    fontSize: "3rem"
    fontWeight: 800
    lineHeight: 1.16
    letterSpacing: "-0.02em"
  h2:
    fontFamily: "PingFang SC"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.22
  h3:
    fontFamily: "PingFang SC"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.3
  body-md:
    fontFamily: "PingFang SC"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
  num:
    fontFamily: "JetBrains Mono"
    fontSize: "2.25rem"
    fontWeight: 700
rounded:
  sm: "8px"
  md: "14px"
  lg: "22px"
  pill: "999px"
spacing:
  sm: "8px"
  md: "20px"
  lg: "32px"
  page-margin: "48px"
components:
  page-bg:
    backgroundColor: "{colors.neutral}"
  hero-panel:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.lg}"
    padding: "32"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "20"
  tint-card:
    backgroundColor: "{colors.tint-blue}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16"
  icon-chip:
    backgroundColor: "{colors.tint-lavender}"
    rounded: "{rounded.md}"
  pill:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.pill}"
    padding: "4"
  title-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    typography: "{typography.h1}"
  body-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-sub}"
    typography: "{typography.body-md}"
---

## Overview

紫蓝渐变（`#6C5CE7` → `#4A6CF7` → `#2FA8FF`，135°）+ 大圆角卡片 + 柔和浅色渐变卡面，现代 AI 产品/发布会气质。
适合产品发布、能力介绍、方案提案、AI/互联网主题汇报；不适合严肃政务述职。

## Colors

- **accent（#4A6CF7）/ accent-2（#6C5CE7）/ accent-3（#2FA8FF）**：主渐变三节点，封面与重点面板用它铺满。
- **bg（#F7F8FE）**：内容页浅底，比纯白更"柔"，衬托白色卡片。
- **tint-*（lavender/blue/mint/peach）**：**卡片卡面**的浅渐变底色，同一页最多用 4 种、按模块轮用，**不做大色块饱和度**。
- **ink（#1B2030）/ ink-sub（#6A7285）**：标题更黑更粗，正文灰蓝，保证 ≥4.5:1 对比度。

## Typography

标题用无衬线黑体（PingFang SC / 思源黑体），**字重更重**（h1 800、h2/h3 700）——这是本风格"现代感"的关键；
正文常规字重。数字用等宽（JetBrains Mono）体现数据感。

## Layout

页面安全边距 48px；内容页用 2×2 或 3 列卡片栅格，卡片间距 ≥20px；
每张卡片 = 彩色圆润图标（44px 圆角方块）+ 加粗标题 + 灰色一句说明 + 可选彩色小标签（pill）。

## Elevation & Depth

**允许极轻的柔和阴影**（`0 10px 30px rgba(24,39,75,.10)`），仅用于卡片与封面浮层；
**禁止**发光、玻璃拟态、霓虹描边、大面积模糊光斑。

## Shapes

大圆角是这个风格的标志：卡片 16–22px、图标方块 13px、小标签用胶囊（999px）。**不要直角卡片。**

## Components

见 front matter：`hero-panel`（封面渐变整屏面板，每册最多 1 个）、`card` / `tint-card`（内容卡片，按 tint 轮用）、
`icon-chip`（彩色圆润图标）、`pill`（小标签，每卡最多 1 个）。

## Do's and Don'ts

- ✅ 封面用整幅紫蓝渐变 + 超大加粗标题 + 一枚 pill 标签
- ✅ 内容页浅底 + 白/浅渐变卡片 + 彩色圆润图标 + 加粗标题
- ✅ 数字突出：等宽字体 + 大字号
- ❌ 不要投影堆叠、发光、玻璃拟态
- ❌ 不要把渐变铺满内容页（内容页只允许**浅色**渐变卡面，深渐变只留给封面/结论条）
- ❌ 不要超过 4 种 tint 卡面出现在同一页；不要用纯黑（用 `#1B2030`）
