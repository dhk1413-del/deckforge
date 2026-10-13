---
version: alpha
name: "冷静蓝白商务汇报"
description: "以纯白底材与单一蓝色强调构成的克制、高留白商务汇报风格。"
colors:
  primary: "#1D1D1A"
  secondary: "#1D1D1A"
  tertiary: "#D9C29A"
  neutral: "#FFFFFF"
  bg: "#FFFFFF"
  surface: "#FFFFFF"
  accent: "#4E75E0"
  accent-2: "#D9C29A"
  accent-deep: "#4263BE"
  ink: "#1D1D1A"
typography:
  h1:
    fontFamily: "DejaVuSans"
    fontSize: "2.33rem"
    fontWeight: 800
    lineHeight: 1.18
    letterSpacing: "-0.01em"
  h2:
    fontFamily: "DejaVuSans"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.25
  h3:
    fontFamily: "DejaVuSans"
    fontSize: "1.34rem"
    fontWeight: 700
    lineHeight: 1.35
  body-md:
    fontFamily: "DejaVuSans"
    fontSize: "1.17rem"
    fontWeight: 400
    lineHeight: 1.7
rounded:
  sm: "8px"
  md: "12px"
  lg: "20px"
  pill: "999px"
spacing:
  sm: "8px"
  md: "20px"
  lg: "32px"
  page-margin: "52px"
components:
  page-bg:
    backgroundColor: "{colors.bg}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "20"
  title-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.primary}"
    typography: "{typography.h1}"
  body-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.secondary}"
    typography: "{typography.body-md}"
  deep-block:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "16"
  accent-bar:
    backgroundColor: "{colors.accent}"
    rounded: "{rounded.sm}"
  accent-rule:
    backgroundColor: "{colors.tertiary}"
    height: "3px"
  accent-2-bar:
    backgroundColor: "{colors.accent-2}"
    rounded: "{rounded.pill}"
  hero-panel:
    backgroundColor: "{colors.accent-deep}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "32"
  num-badge:
    backgroundColor: "{colors.accent-deep}"
    textColor: "#FFFFFF"
    rounded: "{rounded.pill}"
---

## Overview

整体以纯白底材为绝对主导，白底占比高达 92%~97%，画面高度留白、秩序感强。唯一的视觉重心来自占比约 6.5% 的蓝色强调色，集中出现在画面上 1/3，用于标题、关键数据或强调图形。浅金色作为极少量点缀（0.7%，仅见于个别页面），不构成第二主色。整体气质克制、专业、冷静，适合商务汇报与数据陈述场景。

## Colors

accent #4E75E0 是全局唯一主强调色，累计占比 6.5%，八页中均有出现，统一落在画面上 1/3，用于标题强调、关键数字与重点图形；应保持稀缺性，不要大面积平铺。accent-2 #D9C29A 仅在第 5 页出现，占比 0.7%，只能作为极小面积点缀，禁止升级为并列主色。bg #FFFFFF 与 surface #FFFFFF 同为纯白，构成无分层的整体底材，卡片不要靠色差区分。ink 与 ink-sub 同为 #1D1D1A，正文与标题同色，层级只能靠字号与字重区分。需要白字承载时使用 accent-deep #4263BE（由主色压暗 15% 派生，白字对比度 5.59:1），不要自行加深或改变色相。

## Typography

字体统一为 DejaVuSans。标题字号 2.33rem，正文 1.17rem，二者比例约 2:1，层级差异明显。由于 ink 与 ink-sub 同值，正文与标题颜色一致，需依赖字号、字重与留白来建立信息层级，不可引入第三个文字颜色。

## Layout

页边距统一 52px，四周留白充分且一致。白底占比 92%~97%，意味着版面上绝大多数区域为空白，元素密度极低。强调色元素集中布局于画面上 1/3，形成稳定的视觉锚点；下 2/3 以文字或低密度内容承载。

## Elevation and Depth

证据中未测得任何阴影或投影信息，不写入具体阴影参数。surface 与 bg 同为 #FFFFFF，页面不存在靠明度差形成的层级关系，层次只能依赖留白、对齐与强调色建立。

## Shapes

圆角令牌为 sm 8px、md 12px、lg 20px、pill 999px，整体偏中等圆角，可用于卡片、按钮、标签等元素；胶囊形用于标签或按钮时取 999px。

## Components

卡片使用 surface #FFFFFF，与底材同色，因此不能靠色块区分，需依赖留白与圆角轮廓。强调型按钮或标签建议使用 accent-deep #4263BE 配白字，正文按钮谨慎使用 #4E75E0 承载白字。标签类元素优先使用 pill 圆角。

## Do's and Don'ts

✅ 保持纯白底材，白底占比控制在 92%~97% 的高留白区间
✅ 强调色 #4E75E0 只用于关键信息，并统一放在画面上 1/3
✅ 文字统一使用 DejaVuSans，标题 2.33rem、正文 1.17rem
✅ 需要白字底色时使用 accent-deep #4263BE
✅ 页边距统一保持 52px
❌ 不要扩大 accent-2 #D9C29A 的使用面积，它仅 0.7% 且只出现在个别页
❌ 不要引入证据之外的新颜色或新字号
❌ 不要依赖 surface 与 bg 的色差来区分卡片层级
❌ 不要为正文与标题制造第三种文字颜色
❌ 不要用 #4E75E0 大面积铺底承载白字
