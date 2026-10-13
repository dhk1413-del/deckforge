---
version: alpha
name: Medical Teal Professional
description: 医疗青蓝专业风：洁净白底 + 青蓝主色 + 绿色点缀，临床/护理/学术气质。
colors:
  primary: "#0E2A33"
  secondary: "#4B6572"
  tertiary: "#0E7490"
  neutral: "#FFFFFF"
  bg: "#FFFFFF"
  surface: "#F2F8F9"
  accent: "#0E7490"
  accent-2: "#10B981"
  accent-2-ink: "#047857"
  ink: "#0E2A33"
  ink-sub: "#4B6572"
typography:
  h1:
    fontFamily: "Source Han Sans SC"
    fontSize: "3rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0em"
  h2:
    fontFamily: "Source Han Sans SC"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.3
  h3:
    fontFamily: "Source Han Sans SC"
    fontSize: "1.2rem"
    fontWeight: 600
    lineHeight: 1.35
  body-md:
    fontFamily: "Source Han Sans SC"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.65
  num:
    fontFamily: "Source Han Sans SC"
    fontSize: "2.25rem"
    fontWeight: 700
rounded:
  sm: "6px"
  md: "12px"
  lg: "20px"
spacing:
  sm: "6px"
  md: "20px"
  lg: "44px"
  page-margin: "56px"
components:
  accent-block:
    backgroundColor: "{colors.accent-2}"
    height: "4px"
  page-bg:
    backgroundColor: "{colors.neutral}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "20"
  step-badge:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
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
  safety-note:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent-2-ink}"
    rounded: "{rounded.sm}"
    padding: "12"
---

## Overview

洁净白底 + 青蓝主色（`#0E7490`）+ 绿色安全点缀（`#10B981`），强调「专业、洁净、规范」。适合临床/护理/医学学术与培训。

## Colors

- **bg（#FFFFFF）**：白底为主；可用极浅青灰（surface）做病程/流程区块。
- **accent（#0E7490）**：主色，用于步骤编号、流程箭头、图表主序列。
- **accent-2（#10B981）**：**仅用于"安全/正确/达标"语义**（绿勾、正常范围），不做装饰。
- **ink / ink-sub**：深青黑标题 + 青灰正文。

## Typography

统一无衬线黑体（术语多、需极高可读性）；层级：h1 > h2 > h3 > body-md；数字用等宽更利于读数。

## Layout

安全边距 56px；流程类页面用编号徽标（step-badge）串联；表格行高充足（便于打印与投屏）。

## Elevation & Depth

卡片不做投影；层次靠浅青灰表面色。

## Shapes

圆角 12px；流程箭头与圆圈编号为标志性元素。

## Components

见 front matter；`safety-note`（安全提示条）用于操作类页面。

## Do's and Don'ts

- ✅ 青蓝主色 + 绿色仅表"安全/达标"
- ✅ 操作步骤用圆圈编号，一步一句
- ❌ 不要使用红色做装饰（红色只能表示"警示"）；**绿色作文字时必须用 `accent-2-ink`（#047857，浅青底 4.9:1），`accent-2` 只用于色块/图标**（CLI 实测原绿色在浅青底仅 2.36:1，不达 AA）
- ❌ 不要放与医学无关的抽象装饰图形
- ❌ 不要在操作类页面出现超过一屏的长段落
