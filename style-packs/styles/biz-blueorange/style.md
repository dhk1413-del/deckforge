---
version: alpha
name: Business Blue-Orange Vitality
description: 双蓝橙活力汇报风：白底亮宝蓝主色 + 深蓝渐变 + 橙色点睛，编号圆点驱动的逻辑图汇报气质。
colors:
  primary: "#1D1D1A"
  secondary: "#666666"
  tertiary: "#0162D7"
  neutral: "#FFFFFF"
  bg: "#FFFFFF"
  surface: "#F5F8FF"
  accent: "#3B75FE"
  accent-2: "#FFA615"
  accent-2-ink: "#9C5B00"
  accent-deep: "#0162D7"
  accent-cover: "#0046EA"
  accent-light: "#8FB4FE"
  tint-blue: "#EEF3FE"
  tint-blue-2: "#E0E9FB"
  tint-blue-3: "#D6E2FB"
  tint-amber: "#FFF5E6"
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
    backgroundColor: "{colors.tint-blue}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16"
  tint-card-2:
    backgroundColor: "{colors.tint-blue-3}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16"
  num-badge:
    backgroundColor: "{colors.accent-deep}"
    textColor: "#FFFFFF"
    rounded: "{rounded.pill}"
  num-badge-amber:
    backgroundColor: "{colors.accent-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
  decor-ring:
    backgroundColor: "{colors.accent-light}"
    rounded: "{rounded.pill}"
  icon-chip:
    backgroundColor: "{colors.tint-blue-2}"
    rounded: "{rounded.sm}"
  accent-rule:
    backgroundColor: "{colors.accent-2}"
    height: "3px"
  accent-bar:
    backgroundColor: "{colors.accent}"
    rounded: "{rounded.sm}"
  pill:
    backgroundColor: "{colors.tint-amber}"
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

白底 + **亮宝蓝主色（`#3B75FE`）** + **深蓝（`#0162D7` / 封面 `#0046EA`）** + **橙色点睛（`#FFA615`）**。
「双蓝」负责正式与层次，「一橙」负责活力与重点——橙色只落**关键数字、编号圆点、图表第二序列**，面积 <5%。
适合工作汇报、年度述职、业绩复盘、项目进度、逻辑图/结构图类内容；不适合严肃红头文件与文艺类提案。

> 规范来源：用户提供的《【经典活力-双蓝橙】工作汇报逻辑图PPT》模板（90 页 / 16:9）实测提取。
> 色值不是目测：`#3B75FE` / `#0162D7` / `#FFA615` 与模板主题色板（theme1 `三色-橙+双蓝`）逐位吻合，
> 并经 90 页渲染像素统计复核（白底占 56~88%、浅蓝卡面 20~25%、橙 2~5%、封面底部深蓝横带 `#0046EA` 为该页最大面积色）。

## Colors

- **bg（#FFFFFF）**：内容页画布，保持干净；**白底是这套风格的底**，不要整页铺深色。
- **accent（#3B75FE）**：主亮蓝。模块底条、编号圆点、图表主序列、标题装饰线、图标块都用它。
- **accent-deep（#0162D7）**：深蓝。用于色块/图表柱渐变的暗端，以及内容页里的深蓝强调块。
- **accent-cover（#0046EA）**：**封面专用**——实测封面是**白底 + 画面下 1/3 一条贯通的深蓝横带**
  （该页最大面积色，占左下格 54%），橙色小标签压在其上；**封面不是整幅深蓝底**。
- **章节 / 过渡页用整幅亮宝蓝渐变**（`#3B75FE → #6995FE`，左上到右下），可叠一块白色内容区；
  深蓝不是章节页的主色。**内容页禁止整幅铺色**（白底 + 浅蓝卡面才是常态）。
- **accent-2（#FFA615）**：点睛橙。**只给关键数字、编号圆点（01/02/03）、图表第二序列、强调下划线**，一页 ≤3 处。
- **tint-blue / tint-blue-2 / tint-blue-3（#EEF3FE / #E0E9FB / #D6E2FB）**：卡片与分区底色，同级模块按深浅轮用，
  **不做饱和大色块**；橙色浅底仅 `tint-amber`（#FFF5E6），用于风险/提示类小标签。
- **accent-light（#8FB4FE）**：浅蓝装饰色，只用于装饰圆环 / 浅色分割线（`decor-ring`），不承载文字。
- **ink（#1D1D1A）/ ink-sub（#666666）**：标题近黑、正文中灰；正文对比度需 ≥4.5:1。
- ⚠️ **橙色不可直接当正文色，也不可直接配白字**：`#FFA615` 白底对比度约 1.9:1，其上加白字同样只有 1.96:1。
  **橙色块上的文字用 `ink`（#1D1D1A，8.6:1）；橙色作文字用 `accent-2-ink`（#9C5B00，白底 5.4:1 / 浅橙底 5.0:1）**；
  `#FFA615` 原色只允许出现在**色块填充、圆点填充、图表柱**等非文字场景（**与模板原稿相同**：原稿橙圆点上为白字，
  本规范为保证可读性改为深色字，这是唯一的主动偏离）。

## Typography

标题用 **HarmonyOS Sans SC Black**（≈800/900 字重）——**重字重是"活力"的关键**，不要用细体标题；
正文 HarmonyOS Sans SC 常规字重。数字用等宽（JetBrains Mono）体现数据感，关键数字可加大到 `num` 级。
层级四档：`h1`（页/章标题）> `h2`（模块标题）> `h3`（卡片标题）> `body-md`（要点）。
模板实测字号分布（96 页共 3400+ textual run）：12pt 最多，其后 14 / 10 / 11 / 16pt，20/24/28/32pt 仅用于标题——
即**正文密、标题大**：正文用 1rem 档，页标题用 `h1`，不要为了"留白好看"把小标题放大到正文两倍以上。

## Layout

安全边距 52px（模板页边距约占画布宽 5~8%）。
内容页以**卡片栅格**组织：2×2 或 3 列，卡片间距 ≥20px，同级卡片**等宽等高**。
本风格的招牌版式是「**左侧编号 + 右侧内容**」——模块序号（01/02/03）用圆形或胶囊色块独立成列，
右侧放模块标题与要点；也常用"中心主题 + 四周环绕"的放射式逻辑图（中心圆＋三栏）。
每页 3~4 个模块为宜（中低密度），超过 4 个请拆页。

## Elevation & Depth

**允许明确但克制的卡片投影**（`0 6px 18px rgba(0,70,234,.14)`），用于让卡片从浅蓝底上"浮"起来——
这是与「商务蓝金汇报风」（完全无投影）最大的区别。封面深蓝横带与章节渐变面板不投影，只允许叠一层浅蓝装饰几何（圆环/斜切，透明度 ≤30%）。
**禁止**霓虹发光、玻璃拟态、大面积模糊光斑。

## Shapes

混合几何，三种各司其职：
1. **直角矩形**做分区与底条（模板中 `rect` 占几何体多数）——分区不要用大圆角；
2. **微圆角卡片** 8~12px（模板 `roundRect` 圆角实测集中在 8~12px 档）；
3. **圆形**做编号与圆点（`ellipse` 745 处）：编号圆点直径约等于两行正文高，实心填充蓝或橙；
4. **胶囊**（`roundRect adj=50000`）做标签与小序号块。
分割线 **1pt**；强调下划线 / 覆盖条 **3pt**（橙或蓝）。图标用**线性扁平** 24×24，不用拟物 3D。

## Components

见 front matter：`hero-panel`（**封面底部深蓝横带**，约画面高 1/3，每册 1 个）、`gradient-panel`（章节/过渡页整幅亮宝蓝渐变面板）、
`card` / `tint-card` / `tint-card-2`（内容卡片，三档浅蓝底按层级轮用）、`num-badge` / `num-badge-amber`（圆形编号，**本风格标志**）、
`icon-chip`（线性图标底块）、`decor-ring`（浅蓝装饰圆环）、`accent-bar`（模块标题左侧亮蓝竖条）、`deep-block`（深蓝强调块，内容页局部重点）、`accent-rule`（橙色强调短线，3px）、`pill`（浅橙小标签，每卡最多 1 个）。

**两处保底取值（不是审美偏好，是可读性下限）**：
`num-badge` 的底色用 `accent-deep`（#0162D7）而不是 `accent`（#3B75FE）——白字在 #3B75FE 上仅 4.07:1 不达 AA，
在 #0162D7 上为 5.6:1；`num-badge-amber` 的文字用 `ink` 而不是白字（白字在橙底仅 1.96:1）。
若编号块不承载文字（纯色点装饰），可自由使用 `accent` / `accent-2` 原色。

**章节页亮蓝渐变面板（`gradient-panel`）上的文字只允许大字号粗体标题**（≥24pt / 字重 800）：
白字在 #3B75FE 上为 4.07:1，满足 WCAG **AA Large（3:1）**但不满足正文标准（4.5:1）——
所以**不要往这块面板上放正文小字**，正文请落在白底或浅蓝卡面上。
封面深蓝横带（`accent-cover` #0046EA + 白字 6.9:1）与 `deep-block`（#0162D7 + 白字 5.6:1）不受此限制。

## Do's and Don'ts

- ✅ 白底 + 浅蓝卡面 + 亮宝蓝模块底条；标题重字重、正文中灰
- ✅ **大号编号（01/02/03）做视觉动线**——这是模板里最能提升"逻辑感"的元素
- ✅ 封面 = 白底 + 下 1/3 深蓝横带（`#0046EA`）+ 橙标签；章节页 = 整幅**亮宝蓝**渐变（`#3B75FE → #6995FE`）
- ✅ 亮宝蓝 → 深蓝渐变用于色块与图表柱
- ✅ 关键数字用橙色并放大（一页 ≤3 处），配合等宽字体
- ✅ 卡片浮起用轻投影；同级卡片等宽等高、间距 ≥20px
- ❌ 不要把橙色用于非关键数据（会破坏蓝色主调的统一性）
- ❌ 不要整页铺色当内容页底（整页深蓝、整页亮蓝都不行）；不要每页都做渐变铺满
- ❌ 封面不要做成整幅深蓝底（那是章节页的语言；封面是白底 + 下部深蓝横带）
- ❌ 不要大圆角（>20px）+ 重投影 + 渐变叠加，会立刻变成"廉价扁平风"
- ❌ 不要用橙色 `#FFA615` 直接写白底文字（对比度不达标），改用 `accent-2-ink`
- ❌ 不要在一页里出现 4 种以上强调色；不要纯黑文字（用 `ink` #1D1D1A）
