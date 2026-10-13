# PPT 美化五步流程视觉验收

- Source visual truth: `/var/folders/qq/10bsw60x6ns279v7nn2xfz0w0000gn/T/codex-clipboard-abea2e7e-b0cb-487b-987a-a1a991840d1e.png`
- Source pixels: 2472 × 1406；截图只包含工作区，原始 CSS 密度未知。
- Implementation: `/tmp/deckforge-five-step-wide.png`；CSS viewport 1648 × 997，devicePixelRatio=1，实际截图 1633 × 988（可用捕获区）。
- State: 页面确认，5 页、全选、保留原图开关关闭。使用明确标识的本地测试 PDF，未调用模型。
- Full comparison: `/tmp/deckforge-design-comparison.png`，排除既有侧栏与顶栏后，两侧工作区分别等比缩放到 1000px 宽。未进行逐像素叠加；两端来源密度不同。
- Focused comparison: `/tmp/deckforge-design-comparison-focus.png`，同时展示步骤条与文件卡。

## Findings — iteration 1

- [P2] 预览比例偏高：参考图为约 16:9，当前使用 16:10，造成卡片与整体页面偏高。修复：改为 16:9，保留真实原页 object-fit:contain。
- [P2] 底部次按钮不符合参考图的胶囊布局：当前是白色描边按钮，参考图为浅灰填充胶囊。修复：操作栏内统一圆角与浅色主题背景。
- [P3] 参考图不含产品侧栏/顶栏，保留现有产品外壳；颜色沿用此前确认的主题蓝。参考图中的积分文案无本系统依据，使用实际生成策略说明。

## Required fidelity surfaces

- Fonts/typography: 使用已有 PingFang SC/Source Han Sans/system-ui；标题、页序、辅助文字层级对应参考，长文件名可截断并通过 title 查看；数字使用 num。
- Spacing/layout: 五步步骤条、文件信息卡、4列网格、底部操作栏结构对应；上述比例与按钮需修复。
- Colors/tokens: 主色改用既有系统蓝；完成/识别状态使用成功色；不引入截图中的橙色。
- Images: 实际原页缩略图来自后端渲染，未复制参考图中的空白占位；未新增装饰图片。
- Copy/content: 文件名、页数、标题正文来自上传文件；不显示虚构积分、假保存状态；保留原图语义为整页视觉参考，正文修改进入真实生成真源。

## Interaction evidence

浏览器已验证：选文件等待点击开始；识别5页；排除第5页后4/5；全部保留及逐页开关；抽取4页真实原文；修改标题并保存到选择风格；返回保留已确认文字。生成策略与旧预览失效通过离线回归验证，不触发真实付费调用。

## Responsive evidence

390 × 844 时网格降为一列、步骤条换行、底部操作栏换行；DOM scrollWidth=375 <= innerWidth=390。既有移动顶栏较高，与本次新增工作台无横向溢出。

## Comparison history — iteration 2

- 修复预览比例为 16:9；底部按钮统一为 999px 胶囊圆角，次按钮使用浅色主题填充。
- Post-fix implementation: `/tmp/deckforge-five-step-wide-final.png`，相同 1648 × 997 CSS 视口、5 页全选状态，真实截图 1633 × 988。
- Full post-fix comparison: `/tmp/deckforge-design-comparison-final.png`；focused comparison: `/tmp/deckforge-design-comparison-focus-final.png`。两者均将来源图与修复后页面同时放入比较图，使用相同的内容区裁剪与等比归一规则。
- 原 P2 比例与按钮形态问题均已修复。没有未解决的 P0/P1/P2 问题。
- 保留已有字体令牌与适当留白；来源截图 CSS 密度未知，未宣称逐像素一致。标题、真实预览、保存标记与费用说明以实际数据为准，这是现有产品要求下的有意适配。
- 浏览器错误日志检查：`qaTab.dev.logs({levels:['error']})` 返回空数组。
- 宽屏 DOM：四列均为 303px，preview aspectRatio=16/9，操作栏次按钮 borderRadius=999px。
- 新增后端回归 18 项通过；全量 verify 16/16，M5/M6/M7 共9项通过，lint 退出码0。最后两处纯样式修复前端构建通过，并再次执行 verify-fast。

## Remaining test gaps

真实付费生图与 Codex 全册重建未触发；生成策略、确认文字透传及旧预览失效通过离线回归验证。390px 窄屏已验证无横向溢出，已有移动顶栏较高仅列为后续产品外壳优化，不属于本次五步工作台。

## Implementation checklist

- [x] 五步流程与返回操作
- [x] 文件识别、原页预览、全选和逐页保留开关
- [x] 原文抽取、编辑、保存与生成真源
- [x] 内容变更使旧预览失效
- [x] 宽屏/窄屏、可操作控件与错误日志验证
- [x] 修复后双图对照

final result: passed
