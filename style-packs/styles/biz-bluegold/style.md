---
version: alpha
name: Business Blue & Gold
description: 商务蓝金汇报风：白底深蓝 + 克制金饰，体制内/国企汇报气质。
colors:
  primary: "#0F172A"
  secondary: "#475569"
  tertiary: "#1D4ED8"
  neutral: "#FFFFFF"
  bg: "#FFFFFF"
  surface: "#F6F7F9"
  accent: "#1D4ED8"
  accent-2: "#B58A3C"
  accent-2-ink: "#8A6A2A"
  ink: "#0F172A"
  ink-sub: "#475569"
typography:
  h1:
    fontFamily: "Source Han Serif SC"
    fontSize: "3rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.02em"
  h2:
    fontFamily: "Source Han Serif SC"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.25
  h3:
    fontFamily: "Source Han Sans SC"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  body-md:
    fontFamily: "Source Han Sans SC"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
  num:
    fontFamily: "Source Han Sans SC"
    fontSize: "2.25rem"
    fontWeight: 700
rounded:
  sm: "6px"
  md: "12px"
  lg: "20px"
spacing:
  sm: "8px"
  md: "20px"
  lg: "40px"
  page-margin: "56px"
components:
  accent-rule:
    backgroundColor: "{colors.accent-2}"
    height: "1px"
  page-bg:
    backgroundColor: "{colors.neutral}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "20"
  rule-gold:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.accent-2-ink}"
    rounded: "{rounded.sm}"
    padding: "4"
  title-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    typography: "{typography.h1}"
  body-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-sub}"
    typography: "{typography.body-md}"
  verdict-bar:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "16"
---

## Overview

纯白底 + 深蓝主色（`#1D4ED8`）+ 克制金饰（`#B58A3C`），强调「稳、正式、可信」。适合政务/国央企汇报、述职、评审。

## Colors

- **bg（#FFFFFF）**：纯白底，页面必须干净。
- **accent（#1D4ED8）**：主色，用于标题装饰线、模块底条、图表主序列。
- **accent-2（#B58A3C）**：**点缀金**——只用于分割线、编号、边框等细节，面积占比 <5%，**绝不做大色块**。
- **ink / ink-sub**：标题近黑，正文深灰；正文在 surface 上的对比度需 ≥ 4.5:1。

## Typography

标题用衬线（Source Han Serif SC / 思源宋体）体现正式感；正文用黑体。层级：h1 > h2 > h3 > body-md。

## Layout

安全边距 56px；模块用浅灰表面色（surface）区分；分隔用细金线。

## Elevation & Depth

**不用投影**（正式场合避免花哨）；层次靠表面色与细线区分。

## Shapes

小圆角 8px 或直角；图表柱体用直角。

## Components

见 front matter；`verdict-bar`（深蓝反白结论条）每页最多一条。

## Do's and Don'ts

- ✅ 白底 + 深蓝 + 细金线；标题衬线、正文黑体
- ✅ 每页一个明确结论条
- ❌ 不要用金色做大面积色块或渐变；**金色作为文字时必须用 `accent-2-ink`（#8A6A2A，白底 5.3:1），装饰细线才用 `accent-2`**（CLI 实测原金色在白底仅 3.15:1，不达 AA）
- ❌ 不要用投影、发光、玻璃拟态
- ❌ 不要出现超过 2 种强调色以外的杂色
