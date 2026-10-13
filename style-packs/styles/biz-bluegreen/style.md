---
version: alpha
name: Business Blue-Green Fresh
description: 双蓝绿清新汇报风：白底深蓝主色 + 亮蓝次级 + 黄绿点睛，深色视觉封面，逻辑图汇报气质。
colors:
  primary: "#1D1D1A"
  secondary: "#666666"
  tertiary: "#5FA6F1"
  neutral: "#FFFFFF"
  bg: "#FFFFFF"
  surface: "#F0F7FE"
  accent: "#0A61BC"
  accent-deep: "#07498D"
  accent-light: "#5FA6F1"
  accent-2: "#92C248"
  accent-2-ink: "#5A7A22"
  accent-cover: "#0B0F16"
  tint-blue-2: "#E8F0F8"
  tint-blue-3: "#DCE8F4"
  tint-green: "#F1F7E6"
  ink: "#1D1D1A"
  ink-sub: "#666666"
typography:
  h1:
    fontFamily: "HarmonyOS Sans SC"
    fontSize: "3rem"
    fontWeight: 800
    lineHeight: 1.18
    letterSpacing: "-0.01em"
  h2:
    fontFamily: "HarmonyOS Sans SC"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.25
  h3:
    fontFamily: "HarmonyOS Sans SC"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.35
  body-md:
    fontFamily: "HarmonyOS Sans SC"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
  num:
    fontFamily: "JetBrains Mono"
    fontSize: "2.25rem"
    fontWeight: 700
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
    backgroundColor: "{colors.neutral}"
  hero-panel:
    backgroundColor: "{colors.accent-cover}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "32"
  gradient-panel:
    backgroundColor: "{colors.accent}"
    rounded: "{rounded.sm}"
    padding: "28"
  deep-block:
    backgroundColor: "{colors.accent-deep}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "16"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "20"
  tint-card:
    backgroundColor: "{colors.tint-blue-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16"
  tint-card-2:
    backgroundColor: "{colors.tint-green}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16"
  num-badge:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.pill}"
  num-badge-green:
    backgroundColor: "{colors.accent-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
  icon-chip:
    backgroundColor: "{colors.tint-blue-3}"
    rounded: "{rounded.sm}"
  accent-bar:
    backgroundColor: "{colors.accent-light}"
    rounded: "{rounded.sm}"
  accent-rule:
    backgroundColor: "{colors.accent-2}"
    height: "3px"
  decor-ring:
    backgroundColor: "{colors.accent-light}"
    rounded: "{rounded.pill}"
  pill:
    backgroundColor: "{colors.tint-green}"
    textColor: "{colors.accent-2-ink}"
    rounded: "{rounded.pill}"
    padding: "4"
  title-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    typography: "{typography.h1}"
  body-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink-sub}"
    typography: "{typography.body-md}"
---

## Overview

白底 + **深蓝主色（`#0A61BC`）** + **亮蓝次级（`#5FA6F1`）** + **黄绿点睛（`#92C248`）**，
封面走**深色视觉底**（近黑 `#0B0F16` + 3D 视觉图），内页则保持干净白底。
适合工作汇报、项目进度、成果复盘、逻辑图/结构图类内容；风格比「双蓝橙活力」更**冷静克制**（绿色只作点缀）。

> 规范来源：用户提供的《【经典清新-双蓝绿】工作汇报逻辑图PPT》模板（92 页 / 16:9）实测提取。
> 色值与模板主题色板（theme1 `三色-双蓝绿`）逐位对齐，并经 92 页渲染像素统计 + 3×3 分格复核。

## Colors

- **bg（#FFFFFF）**：内容页画布（实测内容页白底占 60~78%）。
- **accent（#0A61BC）**：主深蓝。模块底条、编号圆点、图表主序列、图标块。
- **accent-deep（#07498D）**：更深的蓝，用于**横带与大色块**（实测模板里 1/3 高度深蓝横带的实际取色）。
- **accent-light（#5FA6F1）**：亮蓝次级色，用于浅色带、图标底、图表浅序列、装饰圆环。
- **accent-2（#92C248）**：**点睛黄绿**。只落关键数字、编号圆点、图表第二序列、强调下划线；一页 ≤3 处。
  实测它出现在 60+ 页但**每页占比仅 2~5%**（个别页到 12~16%）——比橙色版更克制。
- **accent-cover（#0B0F16）**：**封面视觉底专用**。实测封面是整页深色（近黑）+ 3D 视觉图（球体/光环/星尘），
  标题压在一条黄绿横幅上；**这不是内页的语言**，内页必须回到白底。
- **surface / tint-blue-2 / tint-blue-3（#F0F7FE / #E8F0F8 / #DCE8F4）**：内容页卡面三档；
  `tint-green`（#F1F7E6）仅用于绿色小标签/提示条。
- **ink（#1D1D1A）/ ink-sub（#666666）**：标题近黑、正文中灰。
- ⚠️ **黄绿不可当正文色**：`#92C248` 白底对比度仅 2.1:1，**作文字必须用 `accent-2-ink`（#5A7A22，白底 4.9:1）**；
  `#92C248` 原色只用于**色块/圆点填充**，其上的文字用 `ink`（8.1:1）。浅亮蓝 `#5FA6F1` 上同样只用深色字（6.6:1），别放白字（2.6:1）。

## Typography

标题用 **HarmonyOS Sans SC Black**（字重 800）——与姊妹模板「双蓝橙活力」同一套字体方案；正文常规字重。
数字用等宽（JetBrains Mono）。层级四档：`h1` > `h2` > `h3` > `body-md`。
模板实测字号分布与姊妹版一致（12pt 最多，其后 14/10/11/16pt；20~32pt 只给标题）：**正文密、标题大**。

## Layout

安全边距 52px。内容页白底 + 卡片栅格（2×2 或 3 列），卡片间距 ≥20px、同级等宽等高。
招牌版式与姊妹版相同：「**左侧编号 + 右侧内容**」，或「中心主题圆 + 三栏环绕」。
封面是**视觉型封面**：深色底 + 一张主视觉图 + 黄绿横幅标题，**不要塞要点列表**。

## Elevation & Depth

卡片允许克制投影（`0 6px 18px rgba(10,97,188,.14)`）。封面深色视觉图自带光效（这是模板原样，不视为违规）；
章节渐变面板不投影。内页**禁止**霓虹发光、玻璃拟态、大面积模糊光斑。

## Shapes

与姊妹版同源：直角矩形分区（`rect` 为多数）、微圆角卡片 8~12px、**圆形编号点**（`ellipse`，实心，蓝或绿）、
胶囊标签。分割线 1pt，强调下划线 3pt（绿或蓝）。图标线性扁平 24×24。

## Components

见 front matter：`hero-panel`（**封面深色视觉底**）、`gradient-panel`（章节/过渡整幅深蓝渐变）、
`deep-block`（深蓝强调块）、`card` / `tint-card` / `tint-card-2`（白蓝卡面 + 浅绿卡面）、
`num-badge` / `num-badge-green`（圆形编号，**本风格标志**）、`icon-chip`、`accent-bar`、`decor-ring`、
`accent-rule`（绿色强调短线，3px）、`pill`（浅绿小标签）。

**保底取值（可读性下限）**：`num-badge-green`（绿底）的文字用 `ink`（白字在 `#92C248` 上仅约 2.0:1）；
`gradient-panel`（主蓝渐变）不声明文字色——白字在 `#0A61BC` 上为 6.1:1 可用，但在渐变亮端会掉到 4.5:1 以下，
**故该面板上只放大字号粗体标题**，正文一律落在白底或浅蓝卡面上。

## Do's and Don'ts

- ✅ 白底 + 浅蓝卡面 + 深蓝模块底条；标题重字重、正文中灰
- ✅ **大号编号（01/02/03）做视觉动线**（与姊妹版一致的招牌元素）
- ✅ 封面用深色视觉图 + 黄绿横幅标题；章节页用整幅深蓝渐变
- ✅ 关键数字用黄绿点缀（一页 ≤3 处），配合等宽字体
- ❌ 不要把黄绿用于非关键数据或大面积色块（它在本风格里是"点睛"而非"主色"）
- ❌ 内容页不要用深色底（深色只属于封面）；不要每页铺渐变
- ❌ 不要用 `#92C248` 写白底文字（2.1:1 不达标），改用 `accent-2-ink`
- ❌ 不要在一页里混入第三、第四种强调色（蓝 + 绿就够，亮蓝是蓝的延伸而非新色）
