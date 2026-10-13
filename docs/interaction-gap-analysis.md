# AI-PPT 交互改造 · 现状差距映射（M0）

依据：`AI-PPT交互改造-SPEC.md`（v1.0）＋ 对**本仓库真实代码**的逐一核查（非推测）。
核查时间：2026-10-08。快照：`.backup/pre-interaction-spec-20261008-200538/`（改动前）。

## 0. 结论摘要

- **目标系统** = 本仓库（DeckForge，`/workspace/智能ppt生成工作台`）。参考平台 `ai.pangmenzd.vip` 仅作交互参照，不修改、不克隆其后台。
- **计费**：本系统**没有积分体系**，只有 `usage_log`（单位「元」）成本账本。→ 按 Spec §9/§13：**隐藏积分组件**，保留「操作范围 + 影响 + 预估费用(元)」确认；不新增支付系统、不硬编码参考平台价格。
- **已具备（可直接复用）**：文档/粘贴输入、页清单确认、DeepSeek 内容梳理（零 key 本地兜底）、风格包与预览/选择分离、逐页生成 + **SSE 进度**、**任务取消**、单页重生成、图片版导出、图片转可编辑（第三方 skill，带断点续跑）、PPT 美化 v2、风格构建、项目列表、用量账本。
- **主要缺口**：项目级持久化与恢复、稳定 `slideId` 在 UI 的真实使用、内容可编辑与保真核对、保存状态机、报价与幂等、单页版本、转换版本绑定、导出快照、五步导航与文案一致。

## 1. 先查清（Spec §2 要求）

| 问题 | 核查结果 | 证据 |
|---|---|---|
| 哪些输入方式真实可用 | 文档导入、粘贴文本、PPTX 原稿、图片/PDF 导入（图片转可编辑）；**无「按页录入」** | `HomePage` 三模式；`main.py` `/upload`、`/import-pages` |
| 哪些输出类型真实可用 | 图片版 PPTX；**文字可编辑版**（第三方 skill，`editable_hi`）；**原生可编辑**（`render_native.mjs`，走换皮 B 口径） | `main.py:421 /export`、`pipeline._export_native_pptx` |
| 任务标识是否持久化 | **服务端持久化**（`jobs` 表 + `GET /api/jobs/{id}`）；但**前端不持久化**：`genJobId` 是组件内 `useState`，刷新即丢 | `ProjectWorkbench.tsx:61`、`db.py` jobs 表 |
| 内容/风格能否回显 | 风格可（`projects.style_pack_id`）；内容**不能**跨刷新回显（向导状态全在 `WizardPage` 本地 state） | `WizardPage.tsx:88-121` |
| 余额/费用是否服务端计算 | 无余额概念；费用为 `usage_log` 事后记账（元），**无提交前报价** | `main.py:523 /usage` |
| 生成是否覆盖旧图 | **会覆盖**：`slides.image_path` 直接覆写，无单页历史版本 | `pipeline._generate_worker`、`db.py` slides 表 |
| 如何导出当前版本 | 导出读 `slides.image_path` 的**当前值**，无版本快照 | `pipeline.do_export` |
| 旧项目如何恢复 | 列表可打开（`/projects/:id` → `ProjectWorkbench`），但**只回到工作台页签**，不回向导阶段、不恢复配置 | `ProjectsPage`、`WizardPage` 无恢复入口 |

## 2. 差距映射表

| Spec 模块 | 当前路由/组件 | 状态/接口/数据来源 | 问题 | 最小改动 | 验收 |
|---|---|---|---|---|---|
| PRJ-01 统一项目身份 | `WizardPage.tsx`（本地 state）、`db.py` slides 表 | `projects`/`slides` 表；`slides.id` TEXT PK **已存在** | UI 全用 `page_no` 作身份（`ProjectWorkbench.tsx:217 key={s.page_no}`）；后端未对外暴露 `slideId` | 暴露 `slide_id`；前端改用它定位 | AC01,AC19 |
| PRJ-02 持续继承配置 | WizardPage 本地 state | 仅 `#/?style=` deep-link（`WizardPage.tsx:136-142`） | 刷新/重开全丢；名称/风格/页范围不继承 | 项目级配置落库 + 打开项目恢复 | AC07,AC25 |
| PRJ-03 工作区布局 | `ProjectWorkbench.tsx` | — | 无统一顶部保存状态/步骤导航；无固定底栏 | 统一工作区外壳 | AC26 |
| IN-01 输入路径 | `HomePage`(3 模式)、`WizardPage`① | `/projects`,`/upload`,`/import-pages`,`/beautify/*` | 无「按页录入」；上传控件未显示服务端限额 | 已有入口显示限额/阶段；**按页录入列为缺口** | AC04 |
| IN-02 页面确认 | `WizardPage` ②（表格） | `PUT /projects/{id}/pages` | 是表格非卡片；PPTX 原稿缩略图**仅对照、与目标页无映射**；无素材策略 | 加缩略图+源页号+策略；勾选↔范围联动 | AC02,AC03 |
| CT-01 内容先确认 | `WizardPage` ③（只读列表） | `POST /projects/{id}/outline` | 梳理结果**只读**；无二维表格编辑；梳理与生图间**无独立确认闸**（③→④直接走） | 内容可编辑 + 独立确认 | AC05,AC06 |
| CT-02 事实保真 | `pipeline.verify_page` | `slides.verify_json`（**源侧校验**，`text_accuracy` 恒 1.0） | 无原稿对照、无数值核对、无「待统计」语义；未识别的生成图不标「待核对」 | 原稿对照 + 数字核查 + 待核对标记 | AC06,AC23 |
| CT-03 内容修订/过期 | — | 无 `content_revision` | 改标题/内容**不标记结果过期** | 内容修订号 + 过期标记 | AC18 |
| NAV-01/02 五步导航 | `WizardPage` `Steps`（**6 步**） | 前端 state；解锁只靠 `maxReached`（`WizardPage.tsx:89-90`） | 步数不符；解锁不按真实前置条件 | 改 5 步 + 条件解锁 + 说明缺什么 | AC07 |
| STY-01 预览/选择分离 | `StylePackCard` + `WizardPage`④ | `GET /style-packs` | **已满足**（`onPreview`/`onSelect` 分离，`WizardPage.tsx:815-826`） | 保持 | AC08 |
| STY-02 范围与费用联动 | `ProjectWorkbench` 生成面板 | `POST /generate` | 无报价；范围即 `pageNos`；模式切换无单价说明 | 报价确认（无积分为「页数/模式/预估费用元」） | AC11,AC12 |
| SAVE-01 保存状态 | — | 无 | 无 `dirty/saving/saved/save_failed`；`PUT /pages` 无修订号 | 保存状态机 + 修订号 | AC09,AC10 |
| TASK-01/02 状态模型 | `useJobStream`/`ProgressPanel`；`jobs` 表 | `GET /jobs/{id}`、`/stream`、`POST /jobs/{id}/cancel` | **SSE/取消已有** ✓；但任务 id 未持久化到 UI | 任务 id 持久化 + 按 id/版本收敛 | AC13,AC14 |
| TASK-03 刷新/恢复 | `ProjectWorkbench.tsx:61` | `jobs` 表可查 | 刷新丢 `genJobId` → **不恢复任务**；无「未知结果先查询」 | 恢复任务 + 幂等 | AC13,AC24 |
| TASK-04 运行中可用操作 | `ProjectWorkbench` | — | 运行中仍可改尺寸/重提交；无禁用原因 | 冲突操作禁用并解释 | AC16 |
| PAY-01 统一操作确认 | — | 无 | 无范围/费用确认，按钮直接提交 | 报价弹窗（降级为元/页数） | AC11,AC12 |
| PAY-02 幂等 | `submitting` 本地标志 | 无幂等键 | 双击可能重复提交 | 幂等键 + 服务端去重 | AC11 |
| PAY-03 项目账本 | `usage_log` + `UsagePage` | `GET /usage` | 有账本 ✓，但**不按项目汇总** | 项目维度汇总 | AC25 |
| RES-01 结果视图 | `ThumbGrid`/`SlidePreview` | `GET /slides` | 缩略图+大图预览 ✓；无原稿对照、无检查状态 | 加对照 + 检查状态 | AC16 |
| RES-02 三动作区分 | `optimize()`/`regenerateSlide` | `POST /slides/{no}/regenerate` | 只有「重生成」；**无「改内容不重生成」**；无 AI 优化指令 | 三动作分离 | AC16,AC17 |
| VER-01 单页版本 | — | `slides.image_path` 覆写 | **重生成覆盖旧图，无历史** | 单页版本表 + 恢复 | AC17 |
| EXP-01 能力命名 | `/export?kind=image\|editable_hi` | `GET /export` | 命名较真实 ✓；**转换未绑定 `slideVersionId`** | 转换绑定版本 | AC20,AC21 |
| EXP-02 范围/快照 | `exports` 表 | `GET /export` | **无版本快照**；文件名含时间 ✓ | 快照 + 部分导出 | AC22,AC23,AC24 |
| LIST-01 项目列表 | `ProjectsPage` | `GET /projects` | 有状态；**打开不恢复阶段** | 恢复实际阶段 | AC25 |
| UI-01 文案/按钮 | 各处 | — | 部分按钮含糊（如「开始生成」不带页数） | 统一具体文案 | AC26 |
| UI-02 模态/键盘 | `SlidePreview` 等 | — | 焦点管理**未核实** | 补焦点管理 | AC26 |

## 3. 需补的最小数据/接口（映射现有，不重建）

| 逻辑对象 | 现有承载 | 需补 |
|---|---|---|
| `slideId` | `slides.id`（已存在） | `GET /slides` 暴露 `slide_id` |
| 内容修订 | — | `slides.content_revision`（+ `updated_at`） |
| 保存状态 | — | 前端状态机（可先纯前端 + `PUT /pages` 返回修订号） |
| 单页版本 | — | 新表 `slide_versions`（页、输入修订、风格/模式、任务、资产、时间、当前选中） |
| 任务持久化 | `jobs` 表 | 前端按 `project_id` 查「最近未完成任务」 |
| 报价 | — | `POST /projects/{id}/quote`（返回页数/模式/预估元） |
| 幂等 | — | 提交带 `idempotency_key`，服务端去重 |
| 转换绑定 | `exports.editable_pages_json` | 记录 `slide_version_id` |
| 导出快照 | `exports` 表 | 记录页/顺序/版本快照 |

## 4. 实施顺序（M1–M7）

- **M1 项目与导航**：五步工作区、条件解锁、配置继承与持久化、旧项目恢复到实际阶段。
- **M2 输入与内容**：有效页确认（缩略图+源页号+策略）、内容可编辑（含表格）、原稿对照、保存状态与过期提示。
- **M3 风格与任务**：报价前置（元）、逐页任务反馈、刷新恢复同一任务、冲突保护。
- **M4 操作与计费**：报价确认、幂等提交、账本按项目汇总；**无积分 → 不显示积分，仅范围/费用确认**。
- **M5 结果与版本**：结果总览、三动作区分、单页版本与恢复、任务失败保留旧版。
- **M6 转换与导出**：转换绑定版本、类型命名真实、导出范围与快照、打包重试不再生图。
- **M7 管理与验收**：项目列表同步、键盘/窄屏、AC01–AC27 记录与证据。

> **底线**（Spec §1）：版本保留、禁止重复扣费、禁止数据丢失。凡开放修订入口，必须先具备版本保留。

---

## 附：本次核查未能确认的项（不臆测）

- `SlidePreview` 等弹窗的焦点/键盘行为未逐行核实 → 标「未核实」，M7 用浏览器验证补。
- 前端是否存在独立 `#/editable` 页面路由未逐行核实（`ProjectWorkbench` 内已含 editable 页签）→ 实施前再确认。

## 施工须知（本轮实测踩到，每个里程碑都要遵守）

1. **改完前端必须显式重建 `web/dist`**：`make verify-fast` 的前端构建在**临时目录**里跑，**不会更新正在托管的 `web/dist`**
   （`tools/verify_all.py` 明确写着「验收构建不覆盖正在托管的 web/dist」）。只跑 verify 而不再 `npm --prefix web run build`，
   页面仍是旧产物 —— 「代码改了、界面没变」就是这个坑（M1 已实测踩到一次）。
2. **改完后端要按 AGENTS.md 的姿势重启**：`bash server/stop-daemon.sh && bash server/start-lan-public.sh`
   （`start-lan-public.sh` 绑 `0.0.0.0`，保留局域网访问；用 `start-lan.sh` 会回到 `127.0.0.1`，局域网 IP 立刻 502）。
3. **`tools/` 下的测试不得改动/削弱**；套件清单在 `tools/verify_all.py` 显式维护。
4. 改动前先做快照到 `.backup/<label>-<时间戳>/`（本仓无提交历史，这是既有惯例）。
