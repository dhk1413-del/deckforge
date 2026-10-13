/* DeckForge 原生 PPTX 渲染器。
 * stdin: {output, project, tokens, slides}; stdout: {pages, objects, warnings}
 * 不读取或嵌入整页渲染 PNG；所有版式均由 PowerPoint 原生对象组成。
 */
import fs from 'node:fs'
import path from 'node:path'
import PptxGenJS from 'pptxgenjs'
import JSZip from 'jszip'

const input = JSON.parse(fs.readFileSync(0, 'utf8'))
const pptx = new PptxGenJS()
pptx.layout = 'LAYOUT_WIDE'
pptx.author = 'DeckForge'
pptx.subject = '原生可编辑演示文稿'
pptx.title = input.project?.title || 'DeckForge'
pptx.company = 'DeckForge'
pptx.lang = 'zh-CN'
pptx.theme = {
  headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: 'zh-CN',
}

const colors = input.tokens?.colors || {}
const hex = (name, fallback) => String(colors[name] || fallback).replace('#', '')
let C = {
  bg: hex('bg', 'F6F8FC'), surface: hex('surface', 'FFFFFF'), ink: hex('ink', '1E232E'),
  sub: hex('ink-sub', '637083'), accent: hex('accent', '1E78FA'), accent2: hex('accent-2', '26ABFE'),
  edge: 'DDE5F0',
}
const W = 13.333, H = 7.5
const margin = 0.72
let objectCount = 0
const addShape = (s, type, opts) => { s.addShape(type, opts); objectCount += 1 }
const addText = (s, text, opts) => { if (text) { s.addText(String(text), opts); objectCount += 1 } }
const addImage = (s, asset, opts) => {
  if (asset?.path && fs.existsSync(asset.path)) { s.addImage({ path: asset.path, ...opts }); objectCount += 1 }
}
const textOpts = (size, extra = {}) => ({ fontFace: 'Microsoft YaHei', fontSize: size, color: C.ink, breakLine: false, margin: 0, fit: 'shrink', valign: 'mid', ...extra })
const firstAsset = (page) => (page.image_assets || []).find(a => a.kind === 'illustration_crop')
const clean = (v, fallback) => String(v || fallback).replace('#', '')
const applyVisual = (page) => {
  const v = page.visual || {}
  const dark = v.dark === true
  C = {
    bg: clean(v.background, dark ? '03162E' : hex('bg', 'F6F8FC')),
    surface: clean(v.surface, dark ? '081E3C' : hex('surface', 'FFFFFF')),
    ink: clean(v.ink, dark ? 'F7FBFF' : hex('ink', '1E232E')),
    sub: clean(v.sub, dark ? 'C2D5EE' : hex('ink-sub', '637083')),
    accent: clean(v.accent, hex('accent', '1E78FA')),
    accent2: clean(v.accent2, hex('accent-2', '26ABFE')),
    edge: dark ? '1766A8' : 'DDE5F0',
  }
}
const addIcon = (slide, name, x, y, w, color = C.accent) => {
  // 采用 PowerPoint 原生图形作为图标：可直接改色、缩放、替换，不产生图片媒体文件。
  const shapes = { sparkles: 'star5', target: 'ellipse', layers: 'hexagon', 'trending-up': 'triangle' }
  const type = pptx.ShapeType[shapes[name] || 'diamond']
  addShape(slide, type, { x, y, w, h: w, fill: { color, transparency: 8 }, line: { color, transparency: 100 } })
}
const header = (s, title) => {
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: C.bg }, line: { color: C.bg, transparency: 100 } })
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: 0.08, fill: { color: C.accent }, line: { color: C.accent, transparency: 100 } })
  addText(s, title, textOpts(25, { x: margin, y: 0.48, w: 11.5, h: 0.45, bold: true }))
  addShape(s, pptx.ShapeType.line, { x: margin, y: 1.13, w: 0.85, h: 0, line: { color: C.accent, width: 2 } })
}
const footer = (s, project, page, total) => {
  addText(s, project?.title || '', textOpts(8.5, { x: margin, y: 7.06, w: 5, h: 0.18, color: C.sub }))
  addText(s, `${page} / ${total}`, textOpts(8.5, { x: 11.7, y: 7.06, w: 0.9, h: 0.18, color: C.sub, align: 'right' }))
}
/* ⚠️ 渲染器只负责“排版”，不负责“内容”：任何页面文案都必须来自该页的结构化真源
 * （title / outline / points / vision）。这里不做任何兜底造句，取不到就少画一个元素，
 * 绝不用占位文字或序号假数据把版面“填满”。 */
let pageWarnings = []

// 取「标签：内容」里的标签（LLM 常这样写对比项/分类项）。取不到返回空串，不编造。
const labelOf = (text) => {
  const m = String(text || '').match(/^([^：:]{2,12})[：:]/)
  return m ? m[1].trim() : ''
}

// 只认要点里真实写着的数字（含单位）。一个都没有时宁可不画图表 —— 不拿序号充数。
const numericPoints = (points) => (points || [])
  .map((p) => {
    if (/待统计/.test(String(p)) || (String(p).match(/-?\d+(?:\.\d+)?/g) || []).length !== 1) return null
    const m = String(p).match(/(-?\d+(?:\.\d+)?)\s*(%|个百分点|分钟|小时|天|周|个月|月|年|人|单|次|元|万元|万|个|家|台|核)?/)
    if (!m) return null
    return { label: String(p).split(/[，,。；;（(]/)[0].slice(0, 14), value: Number(m[1]), unit: m[2] || '' }
  })
  .filter(Boolean)

// 两栏的分栏策略：能按「标签：」分成两组就按标签分；否则按内容对半，不给栏目编造标题。
const twoColumns = (items) => {
  const order = []
  const map = new Map()
  items.forEach((it) => {
    const lb = labelOf(it)
    if (!map.has(lb)) { map.set(lb, []); order.push(lb) }
    map.get(lb).push(it)
  })
  if (order.length === 2) return order.map((k) => ({ label: k, items: map.get(k) }))
  const mid = Math.ceil(items.length / 2)
  return [{ label: '', items: items.slice(0, mid) }, { label: '', items: items.slice(mid) }]
}

function cover(s, page) {
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: C.bg }, line: { color: C.bg, transparency: 100 } })
  // 与图片版的封面构图相同：左上标题/导语 + 底部信息卡 + 右上独立插画裁片。
  addImage(s, firstAsset(page), { x: 9.05, y: 0.05, w: 4.28, h: 2.22, transparency: 4 })
  addText(s, page.title, textOpts(31, { x: 0.58, y: 0.88, w: 8.2, h: 0.82, bold: true }))
  addShape(s, pptx.ShapeType.line, { x: 0.6, y: 2.0, w: 0.72, h: 0, line: { color: C.accent2, width: 2.5 } })
  addText(s, page.outline, textOpts(15, { x: 0.6, y: 2.18, w: 8.15, h: 0.62, color: C.sub, valign: 'top' }))
  const items = (page.points || []).slice(0, 5), n = Math.max(1, items.length), gap = 0.14, cw = (W - 0.72 - gap * (n - 1)) / n
  items.forEach((item, i) => {
    const x = 0.36 + i * (cw + gap)
    addShape(s, pptx.ShapeType.roundRect, { x, y: 3.35, w: cw, h: 3.55, rectRadius: 0.09, fill: { color: C.surface, transparency: 8 }, line: { color: C.edge, width: 0.8 } })
    addIcon(s, ['trending-up', 'target', 'layers', 'sparkles', 'target'][i], x + 0.24, 3.62, 0.43, i % 2 ? C.accent2 : C.accent)
    addShape(s, pptx.ShapeType.line, { x: x + 0.23, y: 4.36, w: 0.34, h: 0, line: { color: C.accent2, width: 2 } })
    addText(s, item, textOpts(12.4, { x: x + 0.23, y: 4.55, w: cw - 0.46, h: 1.92, valign: 'top' }))
  })
  footer(s, input.project, page.page_no, input.slides.length)
}

function section(s, page, index) {
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: C.accent }, line: { color: C.accent, transparency: 100 } })
  addText(s, String(index).padStart(2, '0'), textOpts(42, { x: margin, y: 1.55, w: 2, h: 0.7, color: C.surface, bold: true }))
  addText(s, page.title, textOpts(32, { x: margin, y: 2.55, w: 10.8, h: 0.8, color: C.surface, bold: true }))
  addText(s, page.outline, textOpts(15, { x: margin, y: 3.6, w: 8.8, h: 0.7, color: C.surface, transparency: 12 }))
}

function cards(s, page) {
  header(s, page.title)
  const items = page.points?.slice(0, 4) || []
  const n = Math.max(1, items.length)
  const gap = 0.22, cardW = (W - margin * 2 - gap * (n - 1)) / n
  items.forEach((item, i) => {
    const x = margin + i * (cardW + gap)
    addShape(s, pptx.ShapeType.roundRect, { x, y: 1.58, w: cardW, h: 4.55, rectRadius: 0.1, fill: { color: C.surface }, line: { color: C.edge, width: 0.7 } })
    addShape(s, pptx.ShapeType.rect, { x, y: 1.58, w: cardW, h: 0.1, fill: { color: i % 2 ? C.accent2 : C.accent }, line: { color: C.accent, transparency: 100 } })
    addIcon(s, ['sparkles', 'target', 'layers', 'trending-up'][i], x + 0.25, 1.98, 0.38)
    addText(s, String(i + 1).padStart(2, '0'), textOpts(11, { x: x + cardW - 0.58, y: 2.02, w: 0.35, h: 0.2, color: C.sub, align: 'right' }))
    addText(s, item, textOpts(15, { x: x + 0.25, y: 2.65, w: cardW - 0.5, h: 2.75, breakLine: false, valign: 'top' }))
  })
  footer(s, input.project, page.page_no, input.slides.length)
}

function comparison(s, page) {
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: C.bg }, line: { color: C.bg, transparency: 100 } })
  addText(s, page.title, textOpts(26, { x: 0.72, y: 0.35, w: 11.9, h: 0.52, bold: true, align: 'center' }))
  addText(s, page.outline, textOpts(12.5, { x: 0.85, y: 1.05, w: 11.65, h: 0.34, color: C.sub, align: 'center' }))
  const groups = twoColumns(page.points || [])
  groups.forEach((group, col) => {
    const x = col ? 6.98 : 0.35
    // 有真实标签才写栏目标题；没有就只画一条强调线，不编造“项目创新”这类假标题。
    if (group.label) {
      addShape(s, pptx.ShapeType.roundRect, { x, y: 1.5, w: 5.98, h: 0.52, rectRadius: 0.08, fill: { color: col ? C.accent2 : C.accent }, line: { color: C.accent, transparency: 100 } })
      addText(s, group.label, textOpts(19, { x, y: 1.58, w: 5.98, h: 0.22, color: C.surface, bold: true, align: 'center' }))
    } else {
      addShape(s, pptx.ShapeType.line, { x: x + 0.1, y: 1.72, w: 1.0, h: 0, line: { color: col ? C.accent2 : C.accent, width: 2.5 } })
    }
    group.items.slice(0, 3).forEach((item, i) => {
      const y = 2.2 + i * 1.35
      addShape(s, pptx.ShapeType.roundRect, { x, y, w: 5.98, h: 1.18, rectRadius: 0.08, fill: { color: C.surface, transparency: 7 }, line: { color: C.edge, width: 0.7 } })
      addIcon(s, ['layers', 'target', 'trending-up'][i], x + 0.42, y + 0.34, 0.34, col ? C.accent2 : C.accent)
      addShape(s, pptx.ShapeType.line, { x: x + 1.15, y: y + 0.22, w: 0, h: 0.72, line: { color: C.accent2, width: 1 } })
      addText(s, item, textOpts(12.7, { x: x + 1.4, y: y + 0.19, w: 4.28, h: 0.78, valign: 'top' }))
    })
  })
  addShape(s, pptx.ShapeType.line, { x: 6.66, y: 1.4, w: 0, h: 4.9, line: { color: C.accent2, transparency: 35, width: 1.2 } })
  // 底部结论带：只放两栏没展示完的真实要点；没有就不画（原来写死的口号已删除）。
  const rest = (page.points || []).filter((p) => !groups.some((g) => g.items.slice(0, 3).includes(p)))
  if (rest.length) {
    addShape(s, pptx.ShapeType.roundRect, { x: 0.35, y: 6.53, w: 12.62, h: 0.48, rectRadius: 0.08, fill: { color: C.surface, transparency: 5 }, line: { color: C.accent, width: 0.8 } })
    addText(s, rest.join(' ｜ '), textOpts(13, { x: 0.65, y: 6.66, w: 12.0, h: 0.18, color: C.accent2, bold: true, align: 'center' }))
  }
  footer(s, input.project, page.page_no, input.slides.length)
}

function dataChart(s, page) {
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: C.bg }, line: { color: C.bg, transparency: 100 } })
  addText(s, page.title, textOpts(29, { x: 0.58, y: 0.58, w: 5.4, h: 0.62, bold: true }))
  addShape(s, pptx.ShapeType.line, { x: 0.6, y: 1.38, w: 0.62, h: 0, line: { color: C.accent2, width: 2.5 } })
  addText(s, page.outline, textOpts(12.2, { x: 0.6, y: 1.55, w: 5.12, h: 0.55, color: C.sub, valign: 'top' }))
  // 数据真源优先级：①Qwen-VL 从页面图片里识别出的真实图表 → ②本页要点原文里真实写着的数字
  // → ③两者都没有就不画图表（不拿「项目 1/2/3」这种序号假数据充数）。
  // 一页可能识别出多组图表：选信息量最大的那组（分类×系列最多），不按顺序瞎取第一个。
  const groups = (page.charts?.length ? page.charts : (page.vision?.chart_data || []))
    .filter((c) => Array.isArray(c?.labels) && Array.isArray(c?.series))
  const extracted = groups.slice().sort((a, b) =>
    (b.labels.length * (b.series.length || 1)) - (a.labels.length * (a.series.length || 1)))[0]
  const nums = numericPoints(page.points)
  // 同一张图里只放同单位的数值，避免「8.5 分钟」和「37%」混在一个坐标轴上。
  const byUnit = new Map()
  nums.forEach((n) => { if (!byUnit.has(n.unit)) byUnit.set(n.unit, []); byUnit.get(n.unit).push(n) })
  const sameUnit = [...byUnit.values()].sort((a, b) => b.length - a.length)[0] || []
  let chart = null
  if (extracted?.labels?.length) {
    // 视觉结果已由后端归一化；这里再兜一层（values/data 两种键名），多系列最多画 3 条。
    const labels = extracted.labels.slice(0, 8)
    const series = (extracted.series || [])
      .map((s) => (s && typeof s === 'object')
        ? { name: s.name || '数值', values: (s.values || s.data || []).map(v => v == null || String(v).trim() === '' || typeof v === 'boolean' || /待统计/.test(String(v)) ? NaN : Number(v)) }
        : { name: '数值', values: Array.isArray(s) ? s.map(v => v == null || String(v).trim() === '' || typeof v === 'boolean' || /待统计/.test(String(v)) ? NaN : Number(v)) : [] })
      .filter((s) => s.values.length === labels.length && s.values.every(Number.isFinite))
      .slice(0, 3)
    if (series.length < (extracted.series || []).length) {
      pageWarnings.push(`第 ${page.page_no} 页：图表含待统计或缺失值，未绘制不完整系列；未按 0 推断`)
      addText(s, '待统计：缺失数据未绘制', textOpts(10, { x: 0.6, y: 2.2, w: 5.12, h: 0.4, color: C.sub }))
    }
    if (series.length) {
      // 数据来源标注用实际使用的视觉模型名，不写死厂商（换成中转/其它视觉模型时页面不会撒谎）。
      const visionModel = page.visual?.analysis_model || '视觉模型'
      chart = { labels, series, title: String(extracted.title || ''),
                source: `数据来源：页面图片识别（${visionModel}）` }
    }
  }
  if (!chart && sameUnit.length >= 2) {
    chart = { labels: sameUnit.map((x) => x.label),
              series: [{ name: sameUnit[0].unit ? `值（${sameUnit[0].unit}）` : '数值', values: sameUnit.map((x) => x.value) }],
              source: '数据来源：本页要点原文数值' }
  }
  if (!chart) {
    if (nums.length >= 2) {
      pageWarnings.push(`第 ${page.page_no} 页：要点里的数值单位不一致，未合并成图表`)
    } else {
      pageWarnings.push(`第 ${page.page_no} 页：要点里没有可用数值，未绘制图表（不伪造数据）`)
    }
  }
  ;(page.points || []).slice(0, 3).forEach((p, i) => {
    const y = 2.35 + i * 1.56
    addShape(s, pptx.ShapeType.roundRect, { x: 0.38, y, w: 5.1, h: 1.36, rectRadius: 0.08, fill: { color: C.surface, transparency: 7 }, line: { color: C.edge, width: 0.7 } })
    addIcon(s, ['target', 'trending-up', 'layers'][i], 0.68, y + 0.43, 0.42)
    addShape(s, pptx.ShapeType.line, { x: 1.55, y: y + 0.28, w: 0, h: 0.77, line: { color: C.accent2, width: 1 } })
    addText(s, p, textOpts(12.8, { x: 1.75, y: y + 0.26, w: 3.37, h: 0.82, valign: 'top' }))
  })
  const panel = [5.78, 0.82, 7.15, 4.15]
  addShape(s, pptx.ShapeType.roundRect, { x: panel[0], y: panel[1], w: panel[2], h: panel[3], rectRadius: 0.08, fill: { color: C.surface, transparency: 7 }, line: { color: C.edge, width: 0.7 } })
  if (chart) {
    // 识别到的图表标题是真源信息，画出来（以前被丢掉）。
    if (chart.title) addText(s, chart.title, textOpts(13.5, { x: 6.12, y: 1.02, w: 6.45, h: 0.3, bold: true }))
    drawChart(s, chart, [6.12, 1.45, 6.45, 3.1])
    // 数据口径写在明面上：这组数字是哪来的，用户一眼可查。
    addText(s, chart.source, textOpts(8, { x: 6.12, y: 4.62, w: 6.45, h: 0.18, color: C.sub, align: 'right' }))
  } else {
    // 没有可信数据时，右侧只放左栏没展示的剩余要点（绝不重复左栏内容），
    // 一条都不剩就留空面板：宁可少画，也不编数据和废话。
    const restPoints = (page.points || []).slice(3, 8)
    if (restPoints.length) {
      addText(s, '补充要点', textOpts(17, { x: 6.08, y: 1.05, w: 3, h: 0.28, bold: true }))
      restPoints.forEach((p, i) => {
        addText(s, `${String(i + 1).padStart(2, '0')}　${p}`, textOpts(11.6, { x: 6.12, y: 1.45 + i * 0.58, w: 6.5, h: 0.52, color: C.ink, valign: 'top' }))
      })
    }
  }
  // 底部面板：图表已占用右侧且仍有第 9 条起的内容才画。
  const rest = chart ? (page.points || []).slice(3) : []
  if (rest.length) {
    addShape(s, pptx.ShapeType.roundRect, { x: 5.78, y: 5.12, w: 7.15, h: 1.45, rectRadius: 0.08, fill: { color: C.surface, transparency: 7 }, line: { color: C.edge, width: 0.7 } })
    addText(s, '关键要点', textOpts(17, { x: 6.08, y: 5.34, w: 2.1, h: 0.25, bold: true }))
    rest.slice(0, 3).forEach((p, i) => addText(s, `${String(i + 1).padStart(2, '0')}  ${p}`, textOpts(9.6, { x: 6.15, y: 5.78, w: 2.08, h: 0.5, color: C.sub, valign: 'top' })))
  }
  footer(s, input.project, page.page_no, input.slides.length)
}

function timeline(s, page) {
  header(s, page.title)
  const items = (page.points || []).slice(0, 5), n = Math.max(1, items.length)
  const y = 2.55, start = 1.1, end = 12.2, gap = n === 1 ? 0 : (end - start) / (n - 1)
  addShape(s, pptx.ShapeType.line, { x: start, y, w: end - start, h: 0, line: { color: C.accent2, width: 2.2 } })
  items.forEach((item, i) => {
    const x = start + i * gap
    addShape(s, pptx.ShapeType.ellipse, { x: x - 0.18, y: y - 0.18, w: 0.36, h: 0.36, fill: { color: C.accent }, line: { color: C.surface, width: 1 } })
    addText(s, String(i + 1).padStart(2, '0'), textOpts(11, { x: x - 0.3, y: 1.65, w: 0.6, h: 0.2, color: C.accent, bold: true, align: 'center' }))
    addText(s, item, textOpts(12.5, { x: Math.max(0.72, x - 0.7), y: 3.0, w: 1.4, h: 1.65, align: 'center', valign: 'top' }))
  })
  footer(s, input.project, page.page_no, input.slides.length)
}

function summary(s, page) {
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: C.bg }, line: { color: C.bg, transparency: 100 } })
  addImage(s, firstAsset(page), { x: 9.05, y: 5.75, w: 4.28, h: 1.75, transparency: 4 })
  addText(s, page.title, textOpts(31, { x: 0.58, y: 0.5, w: 8.9, h: 0.72, bold: true }))
  addText(s, page.outline, textOpts(12.5, { x: 0.6, y: 1.38, w: 11.85, h: 0.38, color: C.sub }))
  addShape(s, pptx.ShapeType.line, { x: 0.6, y: 1.93, w: 0.72, h: 0, line: { color: C.accent2, width: 2.5 } })
  const items = (page.points || []).slice(0, 6)
  items.forEach((item, i) => {
    const col = i % 3, row = Math.floor(i / 3), x = 0.55 + col * 4.14, y = 2.15 + row * 2.13
    addShape(s, pptx.ShapeType.roundRect, { x, y, w: 3.92, h: 1.82, rectRadius: 0.08, fill: { color: C.surface, transparency: 6 }, line: { color: C.edge, width: 0.75 } })
    addText(s, String(i + 1).padStart(2, '0'), textOpts(27, { x: x + 0.34, y: y + 0.25, w: 0.86, h: 0.42, color: i % 2 ? C.accent2 : C.accent, bold: true }))
    addIcon(s, ['sparkles', 'layers', 'target', 'target', 'trending-up', 'layers'][i], x + 3.08, y + 0.28, 0.38, C.accent2)
    addText(s, item, textOpts(12.3, { x: x + 0.35, y: y + 0.88, w: 3.18, h: 0.66, valign: 'top' }))
  })
  // 收尾带：只放该页真实还有的要点（points 第 7 条起）；没有就不画，不再写死宣传语。
  const rest = (page.points || []).slice(6)
  if (rest.length) {
    addShape(s, pptx.ShapeType.roundRect, { x: 0.55, y: 6.5, w: 8.0, h: 0.52, rectRadius: 0.08, fill: { color: C.surface, transparency: 6 }, line: { color: C.accent, width: 0.8 } })
    addText(s, rest.join(' ｜ '), textOpts(14, { x: 0.75, y: 6.64, w: 7.6, h: 0.19, color: C.accent2, bold: true, align: 'center' }))
  }
  footer(s, input.project, page.page_no, input.slides.length)
}

// 画柱状图（dataChart 与 visionAbsolute 共用一套样式；图表数据只来自识别结果或原文数字）
const drawChart = (s, chart, box) => {
  s.addChart(pptx.ChartType.bar, chart.series.map((sr) => ({ name: sr.name, labels: chart.labels, values: sr.values })),
    { x: box[0], y: box[1], w: box[2], h: box[3], catAxisLabelFontFace: 'Microsoft YaHei',
      catAxisLabelFontSize: 9, valAxisLabelFontSize: 8, catAxisLabelColor: C.sub, valAxisLabelColor: C.sub,
      showTitle: false, showLegend: chart.series.length > 1, showValue: chart.series.length === 1,
      showCatName: false, chartColors: [C.accent, C.accent2, C.sub],
      valGridLine: { color: C.edge, transparency: 35, width: 0.5 } })
  objectCount += 1
}

// 按视觉识别的归一化坐标把内容放回原位：忠于原页版面，且每个文本块都能在 PowerPoint 里直接编辑。
// 只画识别到的东西（文字/卡片/图表）；识别为空就退回模板版式，绝不用占位文字凑版面。
const visionAbsolute = (s, page) => {
  const blocks = page.blocks || []
  if (!blocks.length) { cards(s, page); return }
  const ptOf = (h) => Math.min(54, Math.max(8, h * H * 72 * 0.62))   // 块高 → 字号（单行约占块高 62%）
  addShape(s, pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H,
    fill: { color: C.bg }, line: { color: C.bg, transparency: 100 } })
  // 卡片/形状底衬 + 图表区域：只在识别到合理区域时画，避免凭空造版式
  for (const c of (page.block_shapes || [])) {
    const cw = (c.w || 0) * W, ch = (c.h || 0) * H
    if (cw < 0.8 || ch < 0.4) continue
    if (c.type === 'chart') continue                                   // 图表区域单独处理
    addShape(s, pptx.ShapeType.roundRect, { x: (c.x || 0) * W, y: (c.y || 0) * H, w: cw, h: ch, rectRadius: 0.06,
      fill: { color: C.surface, transparency: 12 }, line: { color: C.edge, width: 0.8 } })
  }
  const chart = (page.charts || [])[0]
  const chartZone = (page.block_shapes || []).filter((c) => c.type === 'chart' && c.w * W >= 2 && c.h * H >= 1.5)[0]
  if (chart && chartZone) {
    if (chart.title) addText(s, chart.title, textOpts(13, { x: (chartZone.x * W) + 0.3, y: (chartZone.y * H) + 0.12,
      w: (chartZone.w * W) - 0.6, h: 0.3, bold: true }))
    drawChart(s, chart, [(chartZone.x * W) + 0.35, (chartZone.y * H) + 0.5,
                         (chartZone.w * W) - 0.7, Math.max(1.6, (chartZone.h * H) - 1.0)])
  }
  // 图表区域内的文字（图例/坐标轴标签/数值）属于图表本身，不再单独画，避免与图表叠字
  const inChart = (b) => {
    if (!chartZone) return false
    const cx = b.x + b.w / 2, cy = b.y + b.h / 2
    return cx >= chartZone.x && cx <= chartZone.x + chartZone.w
      && cy >= chartZone.y && cy <= chartZone.y + chartZone.h
  }
  for (const b of blocks) {
    if (inChart(b)) continue
    const isTitle = b.role === 'title'
    // 字号优先用视觉模型给的估算（更贴近原页），缺失才由块高推算
    const size = (b.font_size_pt >= 8 && b.font_size_pt <= 60) ? b.font_size_pt : ptOf(b.h)
    addText(s, b.text, textOpts(size, {
      x: b.x * W, y: b.y * H, w: Math.max(0.5, b.w * W), h: Math.max(0.2, b.h * H), bold: isTitle,
      color: isTitle ? C.accent : (b.role === 'label' ? C.sub : C.ink),
      valign: isTitle ? 'mid' : 'top',
    }))
  }
}

for (const page of input.slides || []) {
  const slide = pptx.addSlide()
  const before = objectCount
  pageWarnings = []
  applyVisual(page)
  switch (page.layout) {
    case 'vision_absolute': visionAbsolute(slide, page); break
    case 'cover': cover(slide, page); break
    case 'section': section(slide, page, page.page_no); break
    case 'comparison_2col': comparison(slide, page); break
    case 'data_chart': dataChart(slide, page); break
    case 'timeline': timeline(slide, page); break
    case 'summary': summary(slide, page); break
    default: cards(slide, page)
  }
  page.native_object_count = objectCount - before
  page.render_warnings = pageWarnings
}
fs.mkdirSync(path.dirname(input.output), { recursive: true })
await pptx.writeFile({ fileName: input.output })
// PptxGenJS 的默认主题把东亚字体留空，LibreOffice 会回退到没有中文的字体。
// 显式写入 East Asian / Hans 字体，保证 PowerPoint 和 LibreOffice 都能显示中文。
const zip = await JSZip.loadAsync(fs.readFileSync(input.output))
const themePath = 'ppt/theme/theme1.xml'
const theme = await zip.file(themePath).async('string')
zip.file(themePath, theme
  .replaceAll('<a:ea typeface=""/>', '<a:ea typeface="Microsoft YaHei"/>')
  .replaceAll('typeface="等线 Light"', 'typeface="Microsoft YaHei"')
  .replaceAll('typeface="等线"', 'typeface="Microsoft YaHei"'))
fs.writeFileSync(input.output, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }))
process.stdout.write(JSON.stringify({ pages: (input.slides || []).map(s => ({ page_no: s.page_no, object_count: s.native_object_count, warnings: s.render_warnings || [] })), objects: objectCount, warnings: [] }))
