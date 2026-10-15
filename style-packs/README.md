# SlideCraft 风格包（style-packs）

形态：**B + C 混合**（D4 已定，2026-09-16）—— 目录按 B（布局 × 风格解耦、一层一文件、按需加载），
风格文件按 C（Google DESIGN.md 令牌格式 + prose，可 lint / diff / 导出 DTCG）。

```
style-packs/
├── base-prompt.md          # 整页生图 prompt 的拼装模板（所有风格共用）
├── layouts/                # 版式槽位（信息结构）——与风格正交，可自由组合
│   ├── cover.md  section.md  cards_4.md  comparison_2col.md
│   └── data_chart.md  timeline.md  summary.md
└── styles/<风格名>/
    ├── style.md            # DESIGN.md 格式：YAML 令牌（颜色/字体/圆角/间距/组件）+ prose 说明
    ├── prompt.md           # 画面语言与审美提示词（配图倾向/元素密度/留白/光影）+ 负向词
    └── previews/           # 3~5 张成品预览（自证据）
```

## 拼装顺序（生图时）

```
base-prompt.md（任务定义 + 硬约束）
  + layouts/<布局>.md（版面槽位）
  + styles/<风格>/prompt.md（画面语言）
  + styles/<风格>/style.md 的 YAML 令牌（颜色/字号层级）
  + 页面内容 JSON（逐字给出的上屏文字）
  → 最终 prompt
```

## 三条规范（抄自 baoyu-infographic / Mck-ppt-design-skill 的实践）

1. **布局与风格彻底解耦**：布局只管「信息怎么摆」，风格只管「长什么样」；任意组合都成立。
2. **一层一个文件、按需加载**：只把用到的那一个布局 + 那一个风格读进上下文（省 token，也让模型注意力集中）。
3. **机器可读的 Gate**：生成后用脚本出 JSON（文字保真 / 分辨率一致 / 画面占位），`passed` 是布尔值，不做 AI 自我评价（对应 D20）。
4. **`prompt.md` 必须 ≤1500 字符**：生图时 `render.assemble_prompt()` 只取 `prompt_md[:1500]`（前 1500 字符）——
   超出的部分会被**静默截断**，通常正好截掉末尾的「负向词」段，导致水印/乱码风险回升。
   自查：`python -c "import io;print(len(io.open('style-packs/styles/<名>/prompt.md',encoding='utf-8').read().strip()))"`。
   参考量级：violet-gradient 1181 / biz-blueorange 1442 / biz-bluegold 778 字符。

## 推荐搭配表（内容类型 → 布局 + 风格）

| 内容类型 | 布局 | 推荐风格 |
|---|---|---|
| 封面 / 首页 | `cover` | 任意（跟整册统一） |
| 章节过渡 | `section` | 任意 |
| 三个以上并列要点 | `cards_4` | 科技深蓝发布风 / 商务蓝金汇报风 |
| 逻辑图 / 结构图 / 编号要点 | `cards_4` | 双蓝橙活力汇报风 |
| 清新 / 年轻向汇报、校园·双创·科技项目 | `cards_4` 或 `data_chart` | 双蓝绿清新汇报风 |
| A vs B 对比 | `comparison_2col` | 商务蓝金汇报风 |
| 数据 / 图表页 | `data_chart` | 科技深蓝发布风 / 医疗青蓝专业风 |
| 流程 / 时间线 | `timeline` | 商务蓝金汇报风 |
| 总结 / 结语 | `summary` | 任意 |

## Keyword Shortcuts（用户关键词 → 自动选布局 + 主推风格）

| 关键词 | 布局 | 主推风格 |
|---|---|---|
| 汇报 / 述职 / 总结 | `summary` 或 `cards_4` | 商务蓝金汇报风 |
| 业绩 / 项目进度 / 成果复盘（要活力） | `cards_4` 或 `data_chart` | 双蓝橙活力汇报风 |
| 校园 / 双创 / 清新 / 科技项目 | `cards_4` | 双蓝绿清新汇报风 |
| 发布会 / 技术方案 / 架构 | `data_chart` 或 `comparison_2col` | 科技深蓝发布风 |
| 医疗 / 临床 / 护理 / 学术 | `cards_4` | 医疗青蓝专业风 |
| 培训 / 操作规程 | `timeline` 或 `cards_4` | 医疗青蓝专业风 |
| 时间线 / 里程碑 / 路线图 | `timeline` | 商务蓝金汇报风 |

## 校验

- `style.md` 用 DESIGN.md 规范：`npx -y @google/design.md lint styles/<名>/style.md`
- 改色板后做回归：`npx -y @google/design.md diff 旧.md 新.md`
- 导出给结构化兜底轨：`npx -y @google/design.md export --format dtcg style.md > tokens.json`
