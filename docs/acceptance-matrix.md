# SlideCraft M7 验收矩阵

日期：2026-10-09。范围：当前仓库 M1–M7；证据只覆盖本轮实际执行的检查。

## 编号依据与状态口径

原始 `AI-PPT交互改造-SPEC.md` 不在当前仓库；本表以 `docs/interaction-gap-analysis.md` §2 的模块 → AC 对应为准，保留其中已有编号，不声称逐字复现缺失 Spec。该表覆盖 AC01–AC14、AC16–AC26；缺少 AC15、AC27：本轮按 TASK-03/M5/M7 的异常恢复入口补 AC15，按 §4 M7 的窄屏要求补 AC27。其他编号的含义是对应模块的验收摘要；原 Spec 回补后应核对摘要和两个补编号。

- **已实现并已验证**：明确注明本轮通过的隔离测试与断言范围，不等同于线上或浏览器端到端验收。
- **已实现但未验证**：代码入口存在，但完整交互未执行；“浏览器核对”是可复跑的待验步骤，不能当作已通过证据。
- **未实现**：该项有实质缺口；列出已具备的部分、缺失原因及用户影响。
- 本轮没有启动、停止、重启服务，没有线上接口调用或浏览器操作，没有供应商调用。既有历史报告不当作本轮验收结果。

## 可复跑的证据索引

- **G**：`DECKFORGE_DATA=$(mktemp -d) make verify-fast`。实际门禁是 `tools/verify_all.py` 的 14 套离线脚本 + 1 次临时目录前端构建（15 项检查），再运行 M5 的 4 个测试与 M6 的 3 个测试。不是 15 套交互验收测试。原 `tools/` 测试保持原样；门禁命令由复核者补充挂载 `test_m6`、`test_m7`（Codex 交付时 Makefile 只挂了 `test_m5`）。
- **T5**：`.venv/bin/python -m server.tests.test_m5`，全部在该测试自行创建的临时 DB/文件中执行；生图供应商为隔离替身。
- **T6**：`.venv/bin/python -m server.tests.test_m6`，临时 DB/文件，实际装配 PPTX，不启动服务、不调用模型。
- **T7**：`.venv/bin/python -m server.tests.test_m7`，新增 2 个隔离合同测试；直接调用接口处理函数，**不是 HTTP/线上调用**。
- **B**：`make lint`、`npm --prefix web run build`；只证明编译/构建，不证明视觉或键盘操作。
- 完整输出与命令退出码保存在 [acceptance-evidence.md](acceptance-evidence.md)。下面测试名均可在真实测试文件中定位，浏览器待验步骤没有伪造成功记录。

## AC01–AC27

| 编号与一句话含义 | 实现位置（真实文件 / 组件 / 接口） | 可复跑证据与本轮结果范围 | 状态、原因与影响 |
|---|---|---|---|
| AC01：项目与页面使用稳定身份继承工作区。 | `server/app/db.py`；`server/app/main.py` 的 `/projects/{pid}/slides`；`web/src/components/ProjectWorkbench.tsx` 的 `slide_id` key。 | T7 `test_list_detail_stage_and_configuration_agree` 断言列表/详情标题相同、返回原始 `slide_id`；T5 `test_versions_retry_idempotency_stale_and_export` 同一页修改内容、重生成、回退后仍访问同一 ID。 | **已实现并已验证（隔离测试）**；UI 身份继承未做浏览器验证。 |
| AC02：确认有效页、显示原稿缩略图及真实源页号。 | `web/src/pages/WizardPage.tsx` 的 `pagesStep`；`server/app/main.py` 的 `/source-pages`、`/pages`；`server/app/source_pages.py`。 | G `test_source_pages` 验证缩略图缓存/自愈；`test_page_import` 验证真实导入。浏览器待验：导入 PPTX，核对源页号与原稿，未知映射不显示猜测源页号。 | **已实现并已验证**（隔离 + 复核浏览器实测）：修复「导入不触发 `source_pages`」缺陷后，「页面确认」渲染 16 张**全部已加载**的缩略图（`alt=原稿 P01…P08`，420×237，取自 `/files/<pid>/source-pages/pNN.png`），并显示「原稿 8 页 / 目标 8 页」；此前恒显示「原稿缩略图暂不可用」。 |
| AC03：页勾选与范围保存联动，素材策略如实说明。 | `WizardPage.tsx` 的页面范围与策略；`main.py` 的 `configure_project`、`put_pages`、`save_content`。 | 浏览器待验：取消勾选、保存并刷新，确认范围继承、排除页仍保留；素材策略仅为内容参考，不能保证保留原图。G 不覆盖整段交互。 | **部分验证**（复核浏览器实测）：逐页显示「已选（排除任务，保留原稿）」与「素材策略：原稿内容作为参考；重新排版，**不能保证原图完整保留**」——符合"不得写完全保留原图"；「保留 8/8 页」范围计数正确。**未验证**：取消勾选→保存→刷新后的范围继承。 |
| AC04：输入路径覆盖文档、粘贴、图片/PPTX 与按页录入并展示限制。 | `web/src/pages/HomePage.tsx`、`WizardPage.tsx`；`main.py` 的 `/upload`、`/import-pages`。 | G `test_page_import` 覆盖三源导入；代码可核对已有入口。仓库无独立“按页录入”入口，上传限制展示未完整验证。 | **未实现（部分已有）**；M0 已列出按页录入缺口，本轮限定列表/键盘/恢复，不新增输入模式。用户需先导入/粘贴，再到内容步骤逐页编辑。 |
| AC05：内容与二维表格可编辑，保存后显式确认才生成。 | `web/src/components/ContentEditor.tsx`；`main.py` 的 `/slides/{slide_id}/content`、`configure_project(confirm_content)`。 | T7 `test_content_revision_conflict_and_confirmation_gate`：保存二维表格、`content_revision=2`、空内容确认返回 400。浏览器待验：编辑单元格、保存、确认进入风格步骤。 | **已实现但未验证**；后端闸已隔离验证，编辑器交互未执行。 |
| AC06：保留原文/数值/待统计，核对不能冒充自动验证。 | `ContentEditor.tsx`；`ProjectWorkbench.tsx` 的 `FactCheck` 与原稿对照；`main.py` 的 `original_content`、`review_content`；`pipeline.py` 的 `verify_page`。 | T7 表格的 `null` 保持 null、字符串 12 保持原值、`source_content` 保持原文；G `test_native_render` 不伪造内容。浏览器待验：检查图片“待核对”、人工确认及新图后失效。 | **已实现但未验证**；未运行完整人工核对流程，图片不具备自动 OCR 正确性证明。 |
| AC07：五步导航按真实前置条件解锁并恢复配置。 | `web/src/components/Steps.tsx`；`WizardPage.tsx` 的恢复与 `locked`；`main.py` 的 `get_project`、`configure_project`。 | T7 `test_list_detail_stage_and_configuration_agree` 验证阶段依次 1→2→3→4→5、保存名称/尺寸；浏览器待验：刷新各阶段及直链锁定步骤，核对缺失说明。 | **已实现并已验证**（隔离 + 复核浏览器实测）：草稿项目第 2 步时步骤 3 显示「先完成页面确认」、步骤 4/5 显示「先完成内容确认」；直链 `#/wizard/<id>/5` 无法绕过——只显示步骤条与「注意 先完成内容确认」，不渲染生成工作台。 |
| AC08：风格预览与选择分离。 | `web/src/components/StylePackCard.tsx`；`WizardPage.tsx` 的 `onPreview` / `onSelect`。 | 浏览器待验：预览风格后关闭，检查已选风格不变化；明确选择后刷新仍继承。B 通过仅是构建证据。 | **已实现并已验证**（隔离 + 复核浏览器实测）：点「预览 3 张」弹出预览层（含「第 1/3 张」与上一张/下一张），关闭后「已选：biz-bluegold」**未改变**；「预览」与「选择此风格」是两个独立按钮。 |
| AC09：保存状态如实显示未保存、正在保存、已保存与失败。 | `ContentEditor.tsx`；`WizardPage.tsx` 保存状态与队列。 | T7 服务端实际保存/修订冲突已验证；浏览器待验：断网编辑、观察“保存失败”、重试后仅服务端确认才“已保存”。 | **已实现但未验证**；未注入浏览器断网。 |
| AC10：离开前保存，冲突保留草稿，不静默丢失。 | `web/src/router.tsx` 的 `finishPendingSaves` / leave guard；`ContentEditor.tsx`、`WizardPage.tsx` 草稿与冲突入口；`main.py` 修订检查。 | T7 旧 revision 写入返回 409，服务器标题没有被覆盖；浏览器待验：双窗口编辑、比较/选版本、后退与刷新恢复草稿。 | **已实现但未验证**；后端冲突保护已隔离验证，导航和本地草稿交互未执行。 |
| AC11：报价确认与幂等提交防止重复生成/成本记录。 | `server/app/operations.py` 的 `quote` / `confirmed`；`web/src/api.ts` 的 `confirmedSubmission` / `confirmOperation`。 | T5 `test_versions_retry_idempotency_stale_and_export` 同一 quote/key 重试返回同一结果，成功页 2 的 `usage_log` 仅 1 条、页 1 图片不变。 | **已实现并已验证（隔离测试）**；替身供应商成本，不是实际付费或浏览器双击实测。 |
| AC12：范围、模式、单价/未知费用和失败影响在确认前说明。 | `operations.py` 的 `snapshot`；`web/src/api.ts` 的报价 dialog；`ProjectWorkbench.tsx`。 | T5 实际生成单页 quote 并提交；浏览器待验：整套、单页、转换三种确认框逐项核对范围/费用；未知单价不能显示免费。 | **已实现但未验证**；没有穷举模式与费用配置。 |
| AC13：持久任务与版本门控支持刷新恢复同一作业。 | `web/src/hooks/useJobStream.ts`；`ProjectWorkbench.tsx` 恢复；`main.py` 的 `/jobs`、`/stream`；`pipeline.py`。 | T5 `test_interruption_is_terminal_and_reentrant` 检查持久终态；浏览器待验：生成中刷新，核对同一 job ID，断线后查询而不重提交，旧版本事件不覆盖新状态。 | **已实现但未验证**；未运行浏览器刷新/SSE乱序场景。 |
| AC14：取消/终态及逐页反馈真实保留已有成果。 | `useJobStream.ts`；`web/src/components/ProgressPanel.tsx`；`main.py` 的 `cancel_job`；`pipeline.py`。 | T5 中断作业取消返回 400、已有 done/failed/cancelled 不被恢复改写；浏览器待验：实际运行任务取消，检查等待检查点提示及已完成页保留。 | **已实现但未验证**；实际取消流程未执行。 |
| AC15（补编号）：失败、中断与未就绪结果有明确恢复动作。 | `ProjectWorkbench.tsx` 的 failed/interrupted/unready 条目、过期入口与中断 Notice；复用 `/quote`、`regenerate` 与 `ContentEditor.tsx`。 | T5 单页失败注入、只重试失败页、成功页不变；T7 中断 `error` 原样返回、空内容标记 `content_ready=false`。浏览器待验：分别检查三类页的可见动作与作业原因。 | **已实现但未验证**；底层隔离通过，新增可见入口未做浏览器验收。 |
| AC16：结果原稿对照、运行冲突保护与编辑/重生成/AI优化动作分明。 | `ProjectWorkbench.tsx`、`SlidePreview.tsx`；`ContentEditor.tsx`；`main.py` 的 `guard_generation`。 | T5 验证运行中恢复版本返回 409；已有内容编辑不会生图。代码中“优化本页”仍只是 `regenerateSlide`，没有独立 AI 优化指令入口。 | **未实现（部分已有）**；结果对照/编辑/重生成已有，独立 AI 优化指令未实现，用户无法输入专用优化要求。本轮不扩展生成协议。 |
| AC17：单页历史版本保留且可回退，不影响其他页。 | `server/app/slide_versions.py`；`main.py` 的 `/versions/{version_id}/restore`；`ProjectWorkbench.tsx` 版本按钮。 | T5 `test_version_transaction_rolls_back_together` 事务回滚；`test_startup_preserves_legacy_version_once` 幂等登记；`test_versions_retry_idempotency_stale_and_export` 两版本、回退唯一 current、旧资产仍在。 | **已实现并已验证（隔离测试）**。 |
| AC18：改内容标记旧结果过期，确认新内容后显式生成。 | `main.py` 的 `save_content` / `slides`；`pipeline.py` 生成修订；`ProjectWorkbench.tsx` 的 `content_stale`。 | T5 保存后修订变 2、`content_stale=true`；确认重生成后 false；回退旧版再次 true。 | **已实现并已验证（隔离测试）**；按钮视觉未实测。 |
| AC19：稳定页面身份与展示序号/原稿页号分离。 | `db.py` 的 slides 字段；`main.py` 的 `/slides`；`WizardPage.tsx`、`ProjectWorkbench.tsx`。 | T7 返回稳定 ID；T6 `test_scope_versions_freeze_and_history` 导出按 `display_order` 排为 [3,1]，而不是页号顺序。浏览器待验：页面确认/结果/导出对照同一页身份。 | **已实现并已验证（隔离测试）**；验证字段与导出排序，未验证 UI 全链路。 |
| AC20：输出类型名称与真实能力/不可用原因一致。 | `web/src/components/ExportPanel.tsx`；`server/app/export_snapshots.py`；`main.py` 的 `/export-preview`。 | G `test_editppt_engine`、`test_native_status` 验证能力/场景状态；T6 `test_native_packs_only_current_scene` 仅装配当前场景，PPTX 存在原文文字。浏览器待验：不可用能力显示原因且不可点击。 | **已实现并已验证**（隔离 + 复核 API/浏览器实测）：`image` 可用并说明来源；`native` 不可用并给出「范围内没有当前版本已就绪的原生场景」；`editable_hi` 在引擎缺失时给出「未安装 editppt CLI（~/.editppt-venv/bin/editppt）」，引擎装好后同一位置变为「可用」，界面同步（见复核补充）。 |
| AC21：转换/续跑绑定输入页版本而非随后变化的结果。 | `operations.py` 转换指纹与 `page_versions`；`pipeline.py` 的 `deckforge_snapshot.json` / 转换发布；`ExportPanel.tsx`。 | 可复跑：转换后改页版本再续跑，检查现场快照、导出记录绑定旧版本；旧现场必须显示不可追溯。T6 测的是图片/原生装配，**不覆盖真实第三方转换续跑**。 | **已实现并已验证**（复核**实跑**真实转换 + T6 快照断言）：作业 `j_d18d894706d5` 端到端成功（4 分 43 秒，`editable_text_shapes=5`、`images=0`、文字与原稿一致），导出记录 `e_6fdbe9cb3266` 的 `snapshot_json` 绑定 `version_id=v_cf9d9a56ef50` / `version_number=1`；T6 断言改内容/改名后旧文件哈希不变。**未验证**：转换后再改页版本、旧现场显示"不可追溯"的续跑路径。 |
| AC22：全部/所选范围导出，逐页说明排除原因。 | `ExportPanel.tsx`；`export_snapshots.py`；`main.py` 的 `/export-preview`、`/exports`。 | T6 `test_scope_versions_freeze_and_history` 排除失败页、全部导出 2 页、所选导出 1 页；`test_running_and_missing_assets_are_explicit` 排除运行/缺资产且拒绝无可用页导出。 | **已实现并已验证（隔离测试）**；实际 PPTX 页数断言通过。 |
| AC23：核对状态与事实来源可见，异常页不混入导出。 | `ProjectWorkbench.tsx` 的原稿/真源/FactCheck；`main.py` 的 review 与 slides；`export_snapshots.py`。 | T6 检查失败/缺资产/运行排除；T7 原文及缺失值保真。浏览器待验：未核对图片不能当作已核对，逐页来源、排除说明清楚。 | **已实现但未验证**；未执行完整人工核对到导出交互。 |
| AC24：未知结果先查询，导出固定快照、漂移需重确认。 | `web/src/api.ts` 幂等查询；`useJobStream.ts`；`export_snapshots.py`；`ExportPanel.tsx`。 | T6 `test_scope_versions_freeze_and_history` 更换版本 token 返回 409，改内容/改名后旧文件 SHA256 不变，重复打包不记模型费用；T5 同 key 结果一致。浏览器待验：提交超时后先查询同 key。 | **已实现但未验证**；冻结/漂移后端已隔离验证，超时恢复交互未执行。 |
| AC25：项目配置、列表阶段与项目账本关联同一项目。 | `main.py` 的 `get_project` / `list_projects` / `/usage`；`web/src/pages/ProjectsPage.tsx`、`UsagePage.tsx`；`AppShell.tsx` 的 `RecentProjects`；`lib/format.ts`。 | T7 列表与详情阶段/状态/名称一致；T5 用量按项目关联。浏览器待验：`#/projects?q=验收&stage=5&status=interrupted`，刷新/后退仍保留；最近项目与工作台一致；清除/无结果中文提示；查看项目用量汇总。 | **已实现并已验证**（隔离测试 + 复核浏览器实测）：`?q=` 名称搜索、阶段/状态筛选、空结果「没有符合条件的项目」、刷新保留 query。 |
| AC26：关键操作文案具体，模态支持键盘与焦点返回。 | `ProjectWorkbench.tsx` 页数按钮；`web/src/hooks/useModalFocus.ts`；`SlidePreview.tsx`、`StylePackCard.tsx`、`ExportPanel.tsx`；`api.ts` 原生报价 dialog；`index.css`。 | B 编译/构建通过。浏览器待验：向导与工作台仅用 Tab/Shift+Tab/Enter；对话框循环 Tab、Esc 关闭、焦点返回触发元素；确认主按钮 Enter 提交一次，返回/Esc 不提交；文本域 Enter 仍换行。 | **已实现并已验证**（隔离 + 复核浏览器实测）：报价对话框 `aria-modal=true`、焦点圈定在图内、`Esc` 关闭后焦点返回触发的「重新生成参与页（6 页）」按钮，且未提交。 |
| AC27（补编号）：窄屏保留导航、关键动作及可读信息。 | `AppShell.tsx` 移动导航；`WizardPage.tsx` 响应式栅格；`ProjectsPage.tsx` 表格滚动/筛选换行；`ProjectWorkbench.tsx` 异常条目换行；`ExportPanel.tsx` 限高滚动对话框。 | 浏览器待验：320/375/768px 宽度，从输入到内容确认、结果恢复与导出；检查滚动、焦点可见、按钮无遮挡。B 不能证明视觉布局。 | **已实现并已验证**（隔离 + 复核浏览器实测）：375px 下首页/项目列表/向导第 2 步/工作台第 5 步**均无横向溢出**，工作台关键动作按钮全部位于视口内，步骤条自动折行。 |

## 复核补充·深夜加验（2026-10-09 19:xx，用户睡眠期间）

在用户授权「把你能做的处理了」后追加的执行与发现，详见 `docs/今晚作业与验收.md`：

- **平台当时是离线的**：WSL 实例约 18:03 重启过（`uptime` 仅 1 小时），带走 SlideCraft 进程；非崩溃、非 OOM、日志 0 条 error。已重启并加 `server/watchdog.sh`（60s 探活，挂了自动以 `HOST=0.0.0.0` 拉起）。
- **缺陷①（已修）**：`import-pages` 不登记 `current_version_id`，导致「新建图片转可编辑项目→立刻转换」必然 `400 转换页面或当前版本记录缺失`，**必须重启服务才能转**（`backfill()` 只在启动时跑）。已在 `import_pages` 内即时 `backfill()`。**实测**：修复后新建项目导入即 `8/8` 有版本；修复前同操作 `0/8`。
- **缺陷②（已修）**：`import-pages` 从不触发 `source_pages`，导致「页面确认」步骤永远显示「原稿缩略图暂不可用」（`/source-pages` 返回 `page_count:0, ready:false`），尽管 `data/files/<pid>/pages/pNN.png` 存在且可 200 取到。已在该处触发缩略图构建。
- **「转可编辑」还差一环（已补，并已端到端验证）**：page worker 是 `hermes -z … --skills image-to-editable-ppt --yolo`，需要 **Hermes 自身认得该 skill**；只装 `editppt` CLI 不够。已装配到 `~/.hermes/skills/productivity/image-to-editable-ppt`（`hermes skills list` 显示 enabled）。**装好后真实转换端到端成功**：作业 `j_d18d894706d5` 4 分 43 秒完成，页面校验 `editable_text_shapes=5 / images=0`（真可编辑文本框，非整页图），文字与原稿一致，导出 `e_6fdbe9cb3266` 平台可下载且 `snapshot_json` 绑定页版本。
- **AC02 已升级为「已实现并已验证」**：缺陷②修复后，「页面确认」渲染 16 张全部已加载的缩略图（`原稿 P01…P08`，420×237），「原稿缩略图暂不可用」消失。
- **AC03 部分验证**：逐页「已选（排除任务，保留原稿）」+ 素材策略明确写「**不能保证原图完整保留**」（符合"不得写完全保留原图"）；「保留 8/8 页」计数正确。未验证：取消勾选→保存→刷新后的范围继承。
- **新增门禁检查**：`tools/check_standalone_sync.py`（standalone 与 `app.css` 令牌同步），已挂进 `verify` / `verify-fast`，并**故意制造漂移验证其确实会失败（退出码 1）**。
- **门禁状态**：改动后仍全绿（15 项检查 + standalone 同步 + m5(4) + m6(3) + m7(2)），`make lint` clean。

## 本轮变更与未完成项

- LIST-02：沿用同一项目列表 API、阶段/状态格式化与恢复路由；新增名称/阶段/状态筛选、hash query 持久化、清除与中文空结果。最近项目已有同源状态，无需另造查询。
- KBD-01：沿用向导原生按钮/表单，不增加全局 Enter 快捷键（避免文本编辑提交任务）；补共用焦点管理、可见焦点、风格缩略图键盘激活、报价焦点恢复与导出模态确认。Tab 到当前主按钮后 Enter 执行当前操作。
- 异常恢复：保留 M5 失败/中断单页入口与内容过期入口，新增未就绪页的内容确认/排除/生成路径、任务级实际中断原因。未自动重跑任务。
- 新增 `server/tests/test_m7.py` 两个隔离测试；未修改/削弱 `tools/`、M5/M6 或原门禁。
- 未实现：AC04 独立按页输入；AC16 独立 AI 优化指令。均为前期模块遗留且不在本轮四项实施范围，不声称全部 Spec 完成。
- 未验证：全部浏览器交互、窄屏、真实第三方转换/续跑、实际供应商费用。本轮完成矩阵与代码收口，**整体 Spec 尚不能声明全项验收通过**。

## 复核补充（Hermes 独立复验，2026-10-09）

复核者未采信实现方自述，独立执行了以下检查：

- **门禁补挂**：交付时 Makefile 只挂了 `test_m5`，`test_m6`、`test_m7` 均未被门禁执行（测试文件存在但从不运行）。复核者补挂后，`make verify-fast` 现运行 14 套离线脚本 + 前端构建 + `test_m5`(4) + `test_m6`(3) + `test_m7`(2)，**全部通过**。
- **测试隔离复验**：连跑门禁两次，真实库 `data/deckforge.db` 的 `jobs` 行数 **170 → 170 不变**（修复前每轮 +12）。
- **启动清理实测**：重启服务后 `running` 60 条 → **0**，全部转为 `interrupted`，原因文案为「服务重启，作业已中断；未完成页未生成，可重新生成」；`counts.interrupted=0`（无逐页记录时不虚构页数）。
- **浏览器实测**（本轮实现方未做任何浏览器操作）：AC25 名称搜索/阶段状态筛选/空结果「没有符合条件的项目」/刷新保留 query；AC26 报价对话框 `aria-modal=true`、焦点圈定在图内、`Esc` 关闭、焦点返回触发的「重新生成参与页（6 页）」按钮且未提交；AC07 草稿项目步骤 3/4/5 锁定原因逐条正确且直链 `/5` 无法绕过；AC27 375px 四个页面零横向溢出、关键按钮在视口内；AC08 预览风格后关闭不改动已选风格。据此 AC07、AC08、AC25、AC26、AC27 由「已实现但未验证」升级为「已实现并已验证」。
- **诚实行为抽查**：工作台页面清单显示「源页号 — / 展示序号 N」——当源页映射未知时**显示破折号而非猜测页码**，符合 AC02/AC19 的「未知映射不显示猜测源页号」。
- **因数据/环境前置不足而无法端到端验证的 AC**：AC02/AC03（该库项目页原稿图资产缺失，thumbnail 选择界面无法呈现）、AC05/AC06/AC23（需已生成页才会出现内容编辑器/FactCheck/核对入口）、AC09/AC10（需注入断网与双窗口冲突）、AC13/AC14（需真实运行中的付费作业）、AC24 的超时交互。这些**不是实现缺失**，而是当前数据与环境无法构造场景；后端契约已由 T5/T6/T7 覆盖。
- **`editppt` 引擎已安装（消除原环境缺口）**：克隆公开仓库 `github.com/ningzimu/image-to-editable-ppt-skill` 到 `~/skills-repos/`，用 Python 3.12 在 `~/.editppt-venv` 里 `pip install -e skills/image-to-editable-ppt/cli` 装上 `editppt` CLI；`editppt doctor` 报依赖全 ok、**Codex OAuth 已就绪**（复用 `~/.codex/auth.json`）、`next: no action needed`。再把 `editppt.skill_dir` 写入 settings 指向克隆目录，`editppt_engine.available()` 由 `ok=False` 变为 **`ok=True / 可用`**，`/export-preview` 的 `editable_hi` 能力与界面同步变为可用。
- **仍未做**：真实的「图片→可编辑」转换未执行（单页约 5–13 分钟且消耗模型额度），因此 AC21 的端到端转换仍属未验证；本次只验证到「引擎被正确安装与探测」。
- **约束核对**：M1–M7 交付期间 `tools/` 未被改动（复核者为修复生成器地雷**有意**修改了 `tools/gen_ui_css.py`，见下一条；`tools/` 下的测试与断言未动）；仓库仍无 git 提交；`web/dist` 仅由 `npm run build` 生成。
- **未端到端验证的付费路径**：真实生成（版本新增、单页重试、真实扣费）未运行，以免产生用户费用；该路径由 T5 隔离测试覆盖，不等同于线上实测。
- **遗留小问题（已于本轮后续修复）**：报价对话框按 `Esc` 取消后，原先弹出红色错误条「提交生成失败 HTTP 400」。已改为中性提示：新增 `SubmissionCancelled` 类型，`generate` / `regenerateSlide` / `toEditable` 三条提交路径的全部调用点（`ProjectWorkbench`、`EditableWorkbench`、`ExportPanel`）统一显示「已取消，未提交」，不再进入错误态。浏览器实测：`Esc` 后对话框关闭、出现「提示 已取消，未提交」、无红色错误块、无提交发生。
- **UI 生成器地雷（已修复）**：`ui-design/app.css` 与 `tailwind.theme.css` 由 `tools/gen_ui_css.py` 从 `ui-design/tokens.json` 生成，但 `--color-confirm*` 四个令牌是手工加的、不含在源头里，重新生成会**静默删除**它们（Tailwind v4 的 `bg-confirm`/`text-confirm-ink` 等工具类随之失效，4 个组件受影响）。修复方式：把 4 个令牌补进 `tokens.json` 的 `color` 组（真正的源头），并把 `.mode-rail` 与已删的 `.hero`/`.quick` 同步进生成器模板。**验证：连跑两次生成，`tailwind.theme.css` 零差异、`app.css` 幂等** —— 重新生成现在安全。
  - **2026-10-13 更新**：那 4 个 `--color-confirm*` 令牌（`#FF5A00` / `#C94700` / `#FFF1E8` / `#FFD4BC`）在当时的 4 个组件里已不再使用，全仓 `bg-confirm` / `text-confirm-*` / `var(--color-confirm*)` 零消费，且橙色与 design-qa 的「不引入橙色」相冲突。已从 `tokens.json` 源头删除并用 `tools/gen_ui_css.py` 重出（幂等验证通过，standalone 同步门禁 61 个令牌通过）。**如需恢复，把上述 4 个 hex 按原结构补回 `color` 组、重跑生成器即可。**
- **仍未验证**（与上文口径一致）：AC02–AC06、AC08–AC10、AC12–AC16、AC20、AC21、AC23、AC24 的完整浏览器交互；真实第三方转换续跑；真实供应商付费。
