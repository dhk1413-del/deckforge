---
version: alpha
name: Tech Deep Blue Launch
description: 深蓝光感科技发布风：深空底 + 冷蓝渐变，发布会/技术方案气质。
colors:
  primary: "#E8EEF7"
  secondary: "#8FA3BF"
  tertiary: "#3B82F6"
  neutral: "#0B1220"
  bg: "#0B1220"
  surface: "#111C2E"
  accent: "#3B82F6"
  accent-2: "#22D3EE"
  ink: "#E8EEF7"
  ink-sub: "#8FA3BF"
typography:
  h1:
    fontFamily: "Source Han Sans SC"
    fontSize: "3.5rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  h2:
    fontFamily: "Source Han Sans SC"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0em"
  h3:
    fontFamily: "Source Han Sans SC"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  body-md:
    fontFamily: "Source Han Sans SC"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  num:
    fontFamily: "JetBrains Mono"
    fontSize: "2.5rem"
    fontWeight: 700
rounded:
  sm: "6px"
  md: "12px"
  lg: "20px"
spacing:
  sm: "8px"
  md: "24px"
  lg: "48px"
  page-margin: "64px"
components:
  page-bg:
    backgroundColor: "{colors.neutral}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "24"
  card-head:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent-2}"
    rounded: "{rounded.sm}"
    padding: "8"
  title-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    typography: "{typography.h1}"
  body-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-sub}"
    typography: "{typography.body-md}"
  kpi-number:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent}"
    typography: "{typography.num}"
---

## Overview

深空黑底（`#0B1220`）+ 冷蓝渐变（`#3B82F6 → #22D3EE`），强调「精密、未来、克制」。适合技术发布会、架构方案、研发汇报。

## Colors

- **bg（#0B1220）**：全页底色，必须是深色；不要出现大面积纯白区块。
- **accent（#3B82F6）**：唯一主强调色，用于主按钮、关键数字、图表主序列。
- **accent-2（#22D3EE）**：仅用于次级高亮与图标描边，**用量不超过 accent 的三分之一**。
- **ink / ink-sub**：正文与次要文字；深底上正文不得低于 ink-sub 的亮度过低（对比度 ≥ 4.5:1）。

## Typography

标题与正文统一无衬线黑体（Source Han Sans SC / 思源黑体）；**数字用等宽字形**（JetBrains Mono 类）以突出精密感。三级层级：h1 > h2 > h3 > body-md。

## Layout

页面四边安全边距 64px；卡片间距 24px；强调色块用于模块标题的反白底。

## Elevation & Depth

卡片用浅一档的表面色（surface）而不是投影；渐变条作为背景元素，不承载文字。

## Shapes

圆角 12px；图标线性描边 2px；图表柱体为直角或 4px 微圆角。

## Components

见 front matter；`kpi-number` 只用于每页最多 3 个关键数字。

## Do's and Don'ts

- ✅ 深底 + 冷蓝渐变 + 大面积留白（暗色页面尤其需要留白）
- ✅ 数字等宽、图表只用 accent/accent-2 两色
- ❌ 不要用纯黑（#000）替代 bg
- ❌ 不要在同一页混入暖色（橙/红）作为强调
- ❌ 不要在深底上使用低于 4.5:1 对比度的灰色小字
