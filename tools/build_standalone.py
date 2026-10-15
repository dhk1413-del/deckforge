# -*- coding: utf-8 -*-
"""构建单文件自包含应用：slidecraft-standalone.html

设计要点：
· 令牌来源 = ui-design/app.css（不复制一份，直接内联，避免与规范漂移）
· 风格包来源 = style-packs/styles/*/style.md 的 front matter + prompt.md 摘要
· 版式来源 = style-packs/layouts/*.md
· 纯前端：内容梳理用本地规则（与后端 local_split 同规则）、页面渲染用 Canvas（与 Python local_render 同逻辑）、
  PPTX 导出用**手写 OOXML + 自实现 ZIP(store)**（图片版：整页图铺底；可编辑版：图片底 + 原生文本框）
· 可选「连接本地后端」：能连上 :8640 时把文案梳理/生图切到后端，连不上自动回落本地
"""
import io
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UI = os.path.join(ROOT, "ui-design")
SP = os.path.join(ROOT, "style-packs")
OUT = os.path.join(ROOT, "slidecraft-standalone.html")

META = {
    "tech-deepblue": dict(name="深蓝光感科技发布风", category="科技/深色", badge="热门",
                          summary="深空底 + 冷蓝渐变，发布会/技术方案气质"),
    "biz-bluegold": dict(name="商务蓝金汇报风", category="商务/汇报", badge="",
                         summary="纯白底 + 深蓝主色 + 克制金饰，政务/国央汇报"),
    "med-teal": dict(name="医疗青蓝专业风", category="医疗/医药", badge="推荐",
                     summary="洁净白底 + 青蓝主色 + 绿色安全点缀，临床/护理/培训"),
}
LAYOUT_TITLES = {
    "cover": "封面", "section": "章节过渡", "cards_4": "并列要点/卡片栅格", "comparison_2col": "左右对比",
    "data_chart": "数据/图表页", "timeline": "流程/时间线", "summary": "总结/结语",
}


def front_matter(md):
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if not m:
        return {}
    try:
        import yaml
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def collect_packs():
    packs = []
    base = os.path.join(SP, "styles")
    for sid in sorted(os.listdir(base)):
        d = os.path.join(base, sid)
        if not os.path.isdir(d):
            continue
        fm = front_matter(io.open(os.path.join(d, "style.md"), encoding="utf-8").read())
        colors = fm.get("colors", {}) or {}
        prompt_md = io.open(os.path.join(d, "prompt.md"), encoding="utf-8").read()
        visual = ""
        m = re.search(r"## 底材与配色\n(.+?)\n\n", prompt_md, re.S)
        if m:
            visual = m.group(1).strip()
        packs.append(dict(
            id=sid, name=META.get(sid, {}).get("name", sid), category=META.get(sid, {}).get("category", ""),
            badge=META.get(sid, {}).get("badge", ""), summary=META.get(sid, {}).get("summary", ""),
            colors={k: v for k, v in colors.items()}, visual=visual,
            layouts=sorted(f[:-3] for f in os.listdir(os.path.join(SP, "layouts")) if f.endswith(".md")),
        ))
    return packs


def collect_layouts():
    out = []
    base = os.path.join(SP, "layouts")
    for f in sorted(os.listdir(base)):
        if not f.endswith(".md"):
            continue
        key = f[:-3]
        body = io.open(os.path.join(base, f), encoding="utf-8").read()
        m = re.search(r"-\s*\*\*用途\*\*：(.*)", body)
        out.append(dict(key=key, title=LAYOUT_TITLES.get(key, key), best_for=(m.group(1).strip() if m else "")))
    return out


CSS = io.open(os.path.join(UI, "app.css"), encoding="utf-8").read()
import json
PACKS_JSON = json.dumps(collect_packs(), ensure_ascii=False)
LAYOUTS_JSON = json.dumps(collect_layouts(), ensure_ascii=False)

JS = r"""
/* ============================ 状态与持久化 ============================ */
const LS_KEY = 'deckforge.standalone.v1';
const state = {
  projects: [],           // {id,title,createdAt,pages:[{pageNo,title,role,layout,points,mustKeep,outline}],pack,slides:[]}
  ledger: [],             // {ts,action,provider,model,size,cny,ms,ok,detail}
  settings: { keys: {}, network: 'none', backend: 'http://127.0.0.1:8640', useBackend: false },
  cur: null,              // 当前项目 id
  wizard: { step: 1, draft: { title: '未命名项目', text: '', target: 10 }, pages: [], packId: 'tech-deepblue', selected: new Set(), generated: 0 },
};
function save() { try { localStorage.setItem(LS_KEY, JSON.stringify({projects: state.projects, ledger: state.ledger, settings: state.settings})); } catch (e) {} }
function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(LS_KEY) || '{}');
    state.projects = raw.projects || []; state.ledger = raw.ledger || [];
    state.settings = Object.assign(state.settings, raw.settings || {});
  } catch (e) {}
}
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const uid = (p) => p + '_' + Math.random().toString(16).slice(2, 10);
const nowISO = () => new Date().toISOString().slice(0, 19);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt2 = (n) => (Math.round(n * 100) / 100).toFixed(2);
function logUsage(action, provider, model, size, cny, ms, ok, detail) {
  state.ledger.unshift({ ts: nowISO(), action, provider, model, size, cny, ms, ok: ok !== false, detail: detail || '' });
  if (state.ledger.length > 500) state.ledger.pop();
  save();
}

/* ============================ 后端适配（可选） ============================ */
const BACKEND = {
  async ping() {
    if (!state.settings.useBackend) return null;
    try {
      const r = await fetch(state.settings.backend + '/api/health', { cache: 'no-store' });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  },
  async outline(text, target) {
    try {
      const p = await (await fetch(state.settings.backend + '/api/projects', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title: state.wizard.draft.title, intake_mode:'doc'})})).json();
      await fetch(state.settings.backend + '/api/projects/' + p.id + '/upload', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
      const ol = await (await fetch(state.settings.backend + '/api/projects/' + p.id + '/outline', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target_pages: target})})).json();
      if (!ol.pages) return null;
      return { pages: ol.pages.map(x => ({ pageNo: x.page_no, title: x.title, role: x.role, layout: x.layout, outline: x.outline, points: x.points || [], mustKeep: x.must_keep || [] })), via: 'backend', note: ol.configured ? 'DeepSeek 已梳理' : (ol.hint || '后端本地切页') };
    } catch (e) { return null; }
  },
  async image(slide, pack, layoutKey, total, projectTitle) {
    try {
      // 走后端真出图：建项目→上传→生成单页→取图 URL
      const p = await (await fetch(state.settings.backend + '/api/projects', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title: projectTitle, intake_mode:'doc'})})).json();
      await fetch(state.settings.backend + '/api/projects/' + p.id + '/upload', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text: slide.title + '\n' + (slide.points||[]).join('\n')})});
      const ol = await (await fetch(state.settings.backend + '/api/projects/' + p.id + '/outline', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target_pages: 1})})).json();
      const g = await (await fetch(state.settings.backend + '/api/projects/' + p.id + '/generate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({style_pack_id: pack.id, size:'2K', page_nos:[1]})})).json();
      for (let i = 0; i < 40; i++) {
        await new Promise(r => setTimeout(r, 700));
        const j = await (await fetch(state.settings.backend + '/api/jobs/' + g.job_id)).json();
        if (j.status === 'done' || j.status === 'failed') break;
      }
      const slides = await (await fetch(state.settings.backend + '/api/projects/' + p.id + '/slides')).json();
      const one = (slides.items || [])[0];
      if (!one || !one.image_url) return null;
      const blob = await (await fetch(state.settings.backend + one.image_url)).blob();
      return { bitmap: await createImageBitmap(blob), provider: one.provider, model: one.model, size: one.size, cny: one.cost_cny, ms: one.latency_ms };
    } catch (e) { return null; }
  },
};
"""

JS += r"""
/* ============================ 内容梳理（与后端 local_split 同规则） ============================ */
const LAYOUT_CYCLE = ['cover', 'cards_4', 'data_chart', 'comparison_2col', 'timeline', 'cards_4', 'summary'];
function localSplit(text, target) {
  const blocks = []; let cur = [];
  String(text || '').split(/\r?\n/).forEach(line => {
    const s = line.trim();
    if (!s) { if (cur.length) { blocks.push(cur); cur = []; } return; }
    const isHead = /^(#{1,4}\s|第[一二三四五六七八九十]+[章节部分]|[一二三四五六七八九十]+、|\d+(\.\d+)*\s)/.test(s);
    if (isHead && cur.length) { blocks.push(cur); cur = [s]; } else cur.push(s);
  });
  if (cur.length) blocks.push(cur);
  if (!blocks.length) blocks = [[String(text || '')]];
  let pages = blocks.map((blk, i) => {
    const head = blk[0].replace(/^#+\s*/, '').slice(0, 18);
    const pts = blk.slice(1, 5).map(x => x.replace(/^[-*·\d.]+\s*/, '').slice(0, 40));
    const mk = (blk.join(' ').match(/\d+(?:\.\d+)?%?|[A-Z]{2,}/g) || []).slice(0, 6);
    return { pageNo: i + 1, title: head || ('第 ' + (i + 1) + ' 页'), role: i === 0 ? 'cover' : 'content',
             outline: (blk[1] || head).slice(0, 60), points: pts.length ? pts : [head], mustKeep: Array.from(new Set(mk)),
             layout: i === 0 ? 'cover' : LAYOUT_CYCLE[i % LAYOUT_CYCLE.length] };
  });
  if (target && pages.length > target) pages = pages.slice(0, target);
  pages.forEach((p, i) => {
    p.pageNo = i + 1;
    if (i === 0) { p.layout = 'cover'; p.role = 'cover'; }
    else if (i === pages.length - 1) { p.layout = 'summary'; p.role = 'summary'; }
    else p.role = p.role || 'content';
  });
  return pages;
}

/* ============================ Canvas 页面渲染（与 Python local_render 同逻辑） ============================ */
const SIZE_PX = { '1K': [1024, 576], '2K': [2048, 1152], '4K': [4096, 2304] };
function hex(c, d) { c = (c || d || '#FFFFFF').replace('#', ''); return '#' + (c.length === 6 ? c : 'FFFFFF'); }
function wrapText(ctx, text, maxW) {
  const out = []; let line = '';
  for (const ch of String(text || '')) {
    if (ch === '\n') { out.push(line); line = ''; continue; }
    if (ctx.measureText(line + ch).width <= maxW) line += ch;
    else { out.push(line); line = ch; }
  }
  if (line) out.push(line);
  return out;
}
function renderPageCanvas(slide, pack, size, pageNo, total, projectTitle) {
  const [W, H] = SIZE_PX[size] || SIZE_PX['2K'];
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const ctx = cv.getContext('2d');
  const c = pack.colors || {};
  const bg = hex(c.bg || c.neutral, '#FFFFFF'), surface = hex(c.surface, '#F6F7F9');
  const accent = hex(c.accent || c.primary, '#1E78FA'), accent2 = hex(c['accent-2'] || c.tertiary, '#26ABFE');
  const ink = hex(c.ink, '#1E232E'), inkSub = hex(c['ink-sub'] || c.secondary, '#666666');
  const s = W / 2048, px = v => Math.max(1, Math.round(v * s));
  const F = (sz, w) => (w || 400) + ' ' + px(sz) + 'px "PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif';
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = accent; ctx.fillRect(0, 0, W, px(10));
  const M = px(120);
  const layout = slide.layout || 'cards_4', title = slide.title || '', points = slide.points || [];
  let y = M;
  if (layout === 'cover') {
    y = px(300);
    ctx.fillStyle = accent; ctx.fillRect(M, y, px(8), px(260));
    ctx.fillStyle = ink; ctx.font = F(74, 600);
    wrapText(ctx, title, W - 2 * M - px(40)).slice(0, 3).forEach(l => { ctx.fillText(l, M + px(36), y + px(60)); y += px(96); });
    ctx.fillStyle = inkSub; ctx.font = F(48, 400); y += px(24);
    wrapText(ctx, slide.outline || '', W * 0.7).slice(0, 3).forEach(l => { ctx.fillText(l, M + px(36), y + px(40)); y += px(64); });
  } else {
    ctx.fillStyle = ink; ctx.font = F(74, 600);
    wrapText(ctx, title, W - 2 * M).slice(0, 2).forEach(l => { ctx.fillText(l, M, y + px(60)); y += px(92); });
    y += px(30); ctx.fillStyle = accent; ctx.fillRect(M, y, px(120), px(6)); y += px(50);
    const areaTop = y, areaH = H - areaTop - px(110);
    ctx.font = F(38, 400);
    if (layout === 'cards_4' && points.length) {
      const n = Math.min(4, points.length), gap = px(28), cw = Math.floor((W - 2 * M - gap * (n - 1)) / n);
      for (let i = 0; i < n; i++) {
        const x0 = M + i * (cw + gap);
        ctx.fillStyle = surface; ctx.fillRect(x0, areaTop, cw, areaH);
        ctx.fillStyle = i % 2 ? accent2 : accent; ctx.fillRect(x0, areaTop, cw, px(10));
        ctx.fillStyle = ink; ctx.font = F(38, 400);
        let ty = areaTop + px(40) + px(44);
        wrapText(ctx, points[i], cw - px(48)).slice(0, 10).forEach(l => { ctx.fillText(l, x0 + px(24), ty); ty += px(56); });
      }
    } else if (layout === 'comparison_2col' && points.length >= 2) {
      const half = Math.ceil(points.length / 2), cols = [points.slice(0, half), points.slice(half)], gap = px(40);
      const cw = Math.floor((W - 2 * M - gap) / 2);
      cols.forEach((items, ci) => {
        const x0 = M + ci * (cw + gap);
        ctx.fillStyle = surface; ctx.fillRect(x0, areaTop, cw, areaH);
        ctx.fillStyle = ci ? accent2 : accent; ctx.fillRect(x0, areaTop, cw, px(12));
        ctx.fillStyle = ink; ctx.font = F(38, 400);
        let ty = areaTop + px(50) + px(44);
        items.forEach(it => { wrapText(ctx, '· ' + it, cw - px(56)).slice(0, 4).forEach(l => { ctx.fillText(l, x0 + px(28), ty); ty += px(54); }); ty += px(12); });
      });
    } else if (layout === 'data_chart' && points.length) {
      const leftW = Math.floor(W * 0.42);
      ctx.fillStyle = ink; ctx.font = F(38, 400);
      let ty = areaTop + px(44);
      points.slice(0, 6).forEach(it => { wrapText(ctx, '· ' + it, leftW - M).slice(0, 3).forEach(l => { ctx.fillText(l, M, ty); ty += px(52); }); ty += px(10); });
      const nums = points.slice(0, 6).map(it => { const m = String(it).match(/(\d+(?:\.\d+)?)/); return m ? parseFloat(m[1]) : 0; });
      if (nums.some(v => v > 0)) {
        const mx = Math.max.apply(null, nums) || 1, cx0 = M + leftW, cw = W - M - cx0;
        const bw = Math.floor((cw - px(20) * (nums.length - 1)) / Math.max(1, nums.length));
        nums.forEach((v, i) => {
          const h = Math.round(areaH * 0.85 * (v / mx)), x0 = cx0 + i * (bw + px(20));
          ctx.fillStyle = i % 2 ? accent2 : accent;
          ctx.fillRect(x0, areaTop + areaH - h, bw, h);
          ctx.fillStyle = ink; ctx.font = F(28, 500);
          ctx.fillText(String(v), x0 + px(6), areaTop + areaH - h - px(16));
          ctx.font = F(38, 400);
        });
      }
    } else if (layout === 'timeline' && points.length) {
      const n = Math.min(5, points.length), axisY = areaTop + px(80);
      ctx.fillStyle = accent2; ctx.fillRect(M + px(20), axisY, W - 2 * M - px(40), px(6));
      const seg = n > 1 ? Math.floor((W - 2 * M - px(40)) / (n - 1)) : 0;
      ctx.font = F(38, 400);
      for (let i = 0; i < n; i++) {
        const x0 = M + px(20) + i * seg;
        ctx.fillStyle = accent; ctx.beginPath(); ctx.arc(x0, axisY + px(3), px(16), 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = ink;
        let ty = axisY + px(50) + px(44);
        wrapText(ctx, points[i], seg ? Math.floor(seg * 0.92) : px(400)).slice(0, 6).forEach(l => { ctx.fillText(l, x0 - px(10), ty); ty += px(54); });
      }
    } else {
      const items = points.length ? points.slice(0, 4) : [title];
      ctx.font = F(48, 600);
      let ty = areaTop + px(56);
      items.forEach((it, i) => {
        ctx.fillStyle = accent; ctx.font = F(48, 700); ctx.fillText(String(i + 1).padStart(2, '0'), M, ty);
        ctx.fillStyle = ink; ctx.font = F(48, 600);
        wrapText(ctx, it, W - 2 * M - px(140)).slice(0, 3).forEach(l => { ctx.fillText(l, M + px(140), ty); ty += px(66); });
        ty += px(24);
      });
    }
  }
  ctx.fillStyle = inkSub; ctx.font = F(28, 400);
  ctx.fillText(String(projectTitle || '').slice(0, 40), M, H - px(56));
  ctx.fillText(pageNo + ' / ' + total, W - M - px(90), H - px(56));
  return cv;
}
function canvasToBytes(cv) {
  return new Promise(res => cv.toBlob(async b => res(new Uint8Array(await b.arrayBuffer())), 'image/png'));
}

/* ============================ ZIP(store) + 手写 OOXML → PPTX ============================ */
const CRC_TABLE = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1); t[n] = c >>> 0; } return t; })();
function crc32(u8) { let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = CRC_TABLE[(c ^ u8[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
function utf8(s) { return new TextEncoder().encode(s); }
function zipStore(files) {   // files: [{name, data:Uint8Array}]
  const chunks = [], central = []; let offset = 0;
  const dt = new Date(), dosTime = ((dt.getHours() << 11) | (dt.getMinutes() << 5) | (dt.getSeconds() / 2)) & 0xFFFF;
  const dosDate = (((dt.getFullYear() - 1980) << 9) | ((dt.getMonth() + 1) << 5) | dt.getDate()) & 0xFFFF;
  for (const f of files) {
    const name = utf8(f.name), crc = crc32(f.data), len = f.data.length;
    const lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true);
    lh.setUint16(10, dosTime, true); lh.setUint16(12, dosDate, true); lh.setUint32(14, crc, true);
    lh.setUint32(18, len, true); lh.setUint32(22, len, true); lh.setUint16(26, name.length, true); lh.setUint16(28, 0, true);
    chunks.push(new Uint8Array(lh.buffer), name, f.data);
    const ch = new DataView(new ArrayBuffer(46));
    ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true);
    ch.setUint16(10, 0, true); ch.setUint16(12, dosTime, true); ch.setUint16(14, dosDate, true); ch.setUint32(16, crc, true);
    ch.setUint32(20, len, true); ch.setUint32(24, len, true); ch.setUint16(28, name.length, true);
    ch.setUint32(38, 0, true); ch.setUint32(42, offset, true);
    central.push(new Uint8Array(ch.buffer), name);
    offset += 30 + name.length + len;
  }
  let cdSize = 0; central.forEach(c => cdSize += c.length);
  const eocd = new DataView(new ArrayBuffer(22));
  eocd.setUint32(0, 0x06054b50, true); eocd.setUint16(8, files.length, true); eocd.setUint16(10, files.length, true);
  eocd.setUint32(12, cdSize, true); eocd.setUint32(16, offset, true);
  const all = chunks.concat(central, [new Uint8Array(eocd.buffer)]);
  let total = 0; all.forEach(c => total += c.length);
  const out = new Uint8Array(total); let p = 0; all.forEach(c => { out.set(c, p); p += c.length; });
  return out;
}
const NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"';
const XMLHEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
function buildPptx(slides, blobs, editableSet) {
  // slides: [{title, outline, points, layout}], blobs: [Uint8Array(png)], editableSet: 可编辑页号集合
  const SW = 12192000, SH = 6858000;
  const files = [];
  const ct = [XMLHEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
    '<Default Extension="xml" ContentType="application/xml"/>',
    '<Default Extension="png" ContentType="image/png"/>',
    '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
    '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
    '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'];
  slides.forEach((_, i) => ct.push('<Override PartName="/ppt/slides/slide' + (i + 1) + '.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'));
  ct.push('</Types>');
  files.push({ name: '[Content_Types].xml', data: utf8(ct.join('')) });
  files.push({ name: '_rels/.rels', data: utf8(XMLHEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>') });
  const sldIds = slides.map((_, i) => '<p:sldId id="' + (256 + i) + '" r:id="rId' + (i + 2) + '"/>').join('');
  files.push({ name: 'ppt/presentation.xml', data: utf8(XMLHEAD + '<p:presentation ' + NS + ' saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>' + sldIds + '</p:sldIdLst><p:sldSz cx="' + SW + '" cy="' + SH + '"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>') });
  const prels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'];
  slides.forEach((_, i) => prels.push('<Relationship Id="rId' + (i + 2) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide' + (i + 1) + '.xml"/>'));
  files.push({ name: 'ppt/_rels/presentation.xml.rels', data: utf8(XMLHEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + prels.join('') + '</Relationships>') });
  files.push({ name: 'ppt/slideMasters/slideMaster1.xml', data: utf8(XMLHEAD + '<p:sldMaster ' + NS + '><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>') });
  files.push({ name: 'ppt/slideMasters/_rels/slideMaster1.xml.rels', data: utf8(XMLHEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>') });
  files.push({ name: 'ppt/slideLayouts/slideLayout1.xml', data: utf8(XMLHEAD + '<p:sldLayout ' + NS + ' type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>') });
  files.push({ name: 'ppt/slideLayouts/_rels/slideLayout1.xml.rels', data: utf8(XMLHEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>') });

  const SLOTS = {
    cover: [[0.07, 0.30, 0.80, 40, 'title'], [0.07, 0.50, 0.70, 20, 'subtitle']],
    section: [[0.07, 0.44, 0.80, 36, 'title']],
    cards_4: [[0.06, 0.05, 0.88, 28, 'title'], [0.06, 0.24, 0.88, 14, 'points']],
    comparison_2col: [[0.06, 0.05, 0.88, 28, 'title'], [0.06, 0.24, 0.88, 14, 'points']],
    data_chart: [[0.06, 0.05, 0.88, 28, 'title'], [0.06, 0.24, 0.42, 14, 'points']],
    timeline: [[0.06, 0.05, 0.88, 28, 'title'], [0.06, 0.34, 0.88, 13, 'points']],
    summary: [[0.06, 0.05, 0.88, 28, 'title'], [0.06, 0.28, 0.88, 16, 'points']],
  };
  slides.forEach((s, i) => {
    const n = i + 1, imgId = 2, txt = [];
    let shapes = '<p:pic><p:nvPicPr><p:cNvPr id="3" name="page' + n + '.png"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>' +
      '<p:blipFill><a:blip r:embed="rId' + imgId + '"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>' +
      '<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="' + SW + '" cy="' + SH + '"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>';
    if (editableSet.has(n)) {
      let sid = 10;
      (SLOTS[s.layout] || SLOTS.cards_4).forEach(function (slot) {
        const lx = slot[0], ly = slot[1], lw = slot[2], fs = slot[3] * 100, kind = slot[4];
        let value = kind === 'points' ? (s.points || []).map(x => '· ' + x).join('\n') : (kind === 'subtitle' ? (s.outline || '') : (s.title || ''));
        if (!value) return;
        const paras = String(value).split('\n').map(line => {
          const runs = (line.match(/[\u4e00-\u9fff]|[^\u4e00-\u9fff]+/g) || [line]).map(t => {
            const cjk = /[\u4e00-\u9fff]/.test(t);
            return '<a:r><a:rPr lang="zh-CN" sz="' + fs + '" b="' + (kind === 'title' ? 1 : 0) + '"' + (cjk ? '' : '') + '><a:solidFill><a:srgbClr val="' + (kind === 'title' ? '1E232E' : '333333') + '"/></a:solidFill><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/></a:rPr><a:t>' + esc(t) + '</a:t></a:r>';
          }).join('');
          return '<a:p><a:pPr><a:buNone/></a:pPr>' + runs + '</a:p>';
        }).join('');
        shapes += '<p:sp><p:nvSpPr><p:cNvPr id="' + (sid++) + '" name="TextBox ' + sid + '"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>' +
          '<p:spPr><a:xfrm><a:off x="' + Math.round(SW * lx) + '" y="' + Math.round(SH * ly) + '"/><a:ext cx="' + Math.round(SW * lw) + '" cy="' + Math.round(SH * (1 - ly) - 200000) + '"/></a:xfrm>' +
          '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>' +
          '<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>' + paras + '</p:txBody></p:sp>';
      });
    }
    files.push({ name: 'ppt/slides/slide' + n + '.xml', data: utf8(XMLHEAD + '<p:sld ' + NS + '><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>' + shapes + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>') });
    files.push({ name: 'ppt/slides/_rels/slide' + n + '.xml.rels', data: utf8(XMLHEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId' + imgId + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image' + n + '.png"/></Relationships>') });
    files.push({ name: 'ppt/media/image' + n + '.png', data: blobs[i] });
  });
  return zipStore(files);
}
function download(name, u8) {
  const url = URL.createObjectURL(new Blob([u8], { type: 'application/octet-stream' }));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
"""

JS += r"""
/* ============================ 视图 ============================ */
const NAV = [['#/', '生成向导'], ['#/projects', '项目'], ['#/styles', '风格'], ['#/usage', '用量'], ['#/settings', '设置']];
function shell(inner, active) {
  return '<div class="app">' +
    '<aside class="side"><div class="brand">SlideCraft<span class="tag" style="margin-left:8px">本地版</span></div>' +
    '<nav>' + NAV.map(([h, t]) => '<a href="' + h + '" class="' + (h === active ? 'on' : '') + '">' + t + '</a>').join('') + '</nav>' +
    '<div class="side-foot"><div class="metric-label">生图能力</div><div id="capLine" class="num">检测中…</div>' +
    '<div class="metric-label" style="margin-top:8px">本项目累计</div><div class="num" id="capCost">¥0.00</div></div></aside>' +
    '<main class="main">' + inner + '</main></div>';
}
function viewWizard() {
  const w = state.wizard;
  const steps = ['① 上传内容', '② 页面确认', '③ 内容梳理', '④ 选择风格', '⑤ 生成结果', '⑥ 转可编辑与导出'];
  const bar = '<div class="steps">' + steps.map((t, i) => '<span class="step ' + (w.step === i + 1 ? 'active' : (w.step > i + 1 ? 'done' : 'pending')) + '">' + t + (w.step > i + 1 ? ' ✓' : '') + '</span>' + (i < 5 ? '<span class="step-sep">›</span>' : '')).join('') + '</div>';
  let body = '';
  if (w.step === 1) body = `
    <div class="card"><h2 class="card-title">① 上传内容</h2>
      <p class="card-desc">支持 .md / .txt 直接解析；也可直接粘贴文本。纯前端解析，内容不出本机。</p>
      <div class="row"><input id="pjTitle" class="input" style="max-width:320px" value="${esc(w.draft.title)}" placeholder="项目名称">
        <label class="metric-label">目标页数</label><input id="pjTarget" class="input num" style="width:96px" type="number" min="3" max="30" value="${w.draft.target}">
        <button class="btn btn-secondary" id="btnSample">载入示例素材</button></div>
      <textarea id="txSource" class="input" style="height:220px;margin-top:12px;padding:12px;line-height:1.7" placeholder="粘贴你的汇报/方案文本…">${esc(w.draft.text)}</textarea>
      <div class="row" style="margin-top:12px"><span class="hint" id="charHint">0 字</span><span style="flex:1"></span>
        <button class="btn btn-primary" id="btnToStep2">解析并确认页面 ›</button></div></div>`;
  else if (w.step === 2) body = `
    <div class="card"><h2 class="card-title">② 页面确认</h2>
      <p class="card-desc">可修改每页标题与版式，取消勾选则不生成（不影响计费——本地渲染免费）。</p>
      <table class="ledger"><thead><tr><th style="width:56px">保留</th><th style="width:56px">页码</th><th>页标题</th><th style="width:170px">版式</th></tr></thead><tbody>
      ${w.pages.map(p => '<tr><td><input type="checkbox" data-keep="' + p.pageNo + '" ' + (p.keep !== false ? 'checked' : '') + '></td><td class="num">' + p.pageNo + '</td>' +
        '<td><input class="input" data-title="' + p.pageNo + '" value="' + esc(p.title) + '"></td>' +
        '<td><select class="input" data-layout="' + p.pageNo + '">' + LAYOUTS.map(l => '<option value="' + l.key + '" ' + (l.key === p.layout ? 'selected' : '') + '>' + l.title + '</option>').join('') + '</select></td></tr>').join('')}
      </tbody></table>
      <div class="row" style="margin-top:12px"><button class="btn btn-secondary" id="btnBack1">‹ 上一步</button><span style="flex:1"></span>
        <span class="hint">已选 <b class="num" id="keepCount">${w.pages.filter(p => p.keep !== false).length}</b> 页</span>
        <button class="btn btn-primary" id="btnToStep3">内容梳理 ›</button></div></div>`;
  else if (w.step === 3) body = `
    <div class="card"><h2 class="card-title">③ 内容梳理</h2>
      <p class="card-desc" id="olNote">${esc(w.olNote || '按小标题/段落本地切页，并抽取要点与需保留的数字/专有名词。')}</p>
      <div class="thumb-grid" style="grid-template-columns:1fr">${w.pages.filter(p => p.keep !== false).map(p => `
        <div class="card" style="padding:12px"><div class="row"><b>${p.pageNo}. ${esc(p.title)}</b><span class="tag">${esc(p.role)}</span><span class="tag">${esc(p.layout)}</span></div>
        <div class="card-desc" style="margin:6px 0 4px">${esc(p.outline || '')}</div>
        <div>${(p.points || []).map(x => '<span class="tag" style="margin:2px 4px 2px 0">' + esc(x) + '</span>').join('')}</div>
        ${(p.mustKeep && p.mustKeep.length) ? '<div class="metric-label" style="margin-top:6px">必须保留：<span class="num">' + p.mustKeep.map(esc).join('、') + '</span></div>' : ''}</div>`).join('')}</div>
      <div class="row" style="margin-top:12px"><button class="btn btn-secondary" id="btnBack2">‹ 上一步</button><span style="flex:1"></span><button class="btn btn-primary" id="btnToStep4">选择风格 ›</button></div></div>`;
  else if (w.step === 4) body = `
    <div class="card"><h2 class="card-title">④ 选择风格</h2>
      <p class="card-desc">风格包 = 令牌（颜色/字号）+ 画面语言 + 版式集合。这里用的是你已定稿的 3 套内置风格。</p>
      <div class="cols-3">${PACKS.map(p => `
        <div class="card pack ${p.id === w.packId ? 'sel' : ''}" data-pack="${p.id}">
          <div class="row"><h3 class="card-title" style="margin:0;font-size:var(--text-h3)">${esc(p.name)}</h3>${p.badge ? '<span class="badge">' + esc(p.badge) + '</span>' : ''}</div>
          <p class="card-desc" style="margin:8px 0">${esc(p.summary)}</p>
          <div class="row">${['bg','surface','accent','accent-2','ink'].filter(k => p.colors[k]).map(k => '<span class="sw-mini" style="background:' + esc(p.colors[k]) + '" title="' + k + ' ' + esc(p.colors[k]) + '"></span>').join('')}
            <span class="num hint">${esc(p.colors.accent || '')}</span></div>
          <p class="metric-label" style="margin:10px 0 0">可用版式 ${p.layouts.length} 个 · 分类 ${esc(p.category)}</p>
        </div>`).join('')}</div>
      <div class="row" style="margin-top:12px"><button class="btn btn-secondary" id="btnBack3">‹ 上一步</button><span style="flex:1"></span>
        <label class="metric-label">输出尺寸</label><select class="input" id="genSize" style="width:120px"><option>1K</option><option selected>2K</option><option>4K</option></select>
        <button class="btn btn-primary" id="btnGenerate">开始生成 ›</button></div></div>`;
  else if (w.step === 5) body = `
    <div class="card"><h2 class="card-title">⑤ 生成结果</h2>
      <p class="card-desc">${esc(w.genNote || '本地渲染（Canvas）：按风格令牌与版式出 16:9 整页图，免费、可离线。')}</p>
      <div class="progress" style="margin:10px 0"><i id="genBar" style="width:0%"></i></div>
      <p class="hint"><span id="genMsg">准备中…</span></p>
      <div class="thumb-grid" id="thumbGrid"></div>
      <div class="row" style="margin-top:12px"><button class="btn btn-secondary" id="btnBack4">‹ 上一步</button><span style="flex:1"></span>
        <button class="btn btn-secondary" id="btnImgPptx">下载图片版 PPTX</button>
        <button class="btn btn-primary" id="btnToStep6">转可编辑与导出 ›</button></div></div>`;
  else body = `
    <div class="card"><h2 class="card-title">⑥ 转可编辑与导出</h2>
      <p class="card-desc"><b>可编辑化由你手动勾选</b>（默认全不选）：勾选的页会在 PPTX 里叠加<b>原生文本框</b>（可改字/改字号）；
        未勾选的页保持「图片直通」并在备注中标注。图片铺底保证视觉 100% 不变。</p>
      <div class="thumb-grid" id="editGrid"></div>
      <div class="row" style="margin-top:12px"><button class="btn btn-secondary" id="btnBack5">‹ 上一步</button><span style="flex:1"></span>
        <span class="hint">已勾选 <b class="num" id="editCount">0</b> 页</span>
        <button class="btn btn-secondary" id="btnImgPptx2">下载图片版</button>
        <button class="btn btn-primary" id="btnEditPptx">下载可编辑版 PPTX</button></div></div>`;
  return shell('<div class="topbar"><h1 class="page">' + (w.step === 1 ? '新项目 · 生成向导' : esc(w.draft.title)) + '</h1>' + bar + '</div>' + body, '#/');
}
function viewProjects() {
  return shell('<h1 class="page">项目</h1><p class="page-sub">本地保存（浏览器 localStorage）——换浏览器不会同步。</p>' +
    (state.projects.length ? '<div class="card"><table class="ledger"><thead><tr><th>项目</th><th>创建时间</th><th class="num">页数</th><th>风格</th><th></th></tr></thead><tbody>' +
      state.projects.map(p => '<tr><td>' + esc(p.title) + '</td><td class="num">' + esc(p.createdAt) + '</td><td class="num">' + (p.slides || []).length + '</td><td>' + esc((PACKS.find(x => x.id === p.packId) || {}).name || '-') + '</td>' +
        '<td style="text-align:right"><button class="btn btn-ghost" data-open="' + p.id + '">打开</button><button class="btn btn-ghost" data-del="' + p.id + '">删除</button></td></tr>').join('') +
      '</tbody></table></div>' : empty('还没有项目', '回到「生成向导」导入一份文档开始', '#/', '去生成')), '#/projects');
}
function viewStyles() {
  return shell('<h1 class="page">风格库</h1><p class="page-sub">来自 <code>style-packs/</code>（B+C 形态）：金牌令牌 + 画面语言 + 7 个可组合版式。</p>' +
    '<div class="cols-3">' + PACKS.map(p => '<div class="card"><div class="row"><h3 class="card-title" style="margin:0;font-size:var(--text-h3)">' + esc(p.name) + '</h3>' + (p.badge ? '<span class="badge">' + esc(p.badge) + '</span>' : '') + '</div>' +
      '<p class="card-desc" style="margin:8px 0">' + esc(p.summary) + '</p>' +
      '<div class="swatches">' + Object.entries(p.colors).filter(([k]) => ['bg','surface','ink','ink-sub','accent','accent-2','primary','tertiary','border','surface-tag'].includes(k)).map(([k, v]) => '<div class="sw"><div class="sw-chip" style="background:' + esc(v) + '"></div><div class="sw-name">' + k + '</div><div class="sw-hex num">' + esc(v) + '</div></div>').join('') + '</div>' +
      '<p class="metric-label" style="margin-top:10px">画面语言：' + esc(p.visual || '—') + '</p></div>').join('') + '</div>' +
    '<h2 class="page" style="font-size:var(--text-h2);margin-top:28px">版式（与风格正交，可任意组合）</h2>' +
    '<div class="card"><table class="ledger"><thead><tr><th>键</th><th>名称</th><th>适用</th></tr></thead><tbody>' +
    LAYOUTS.map(l => '<tr><td class="num">' + esc(l.key) + '</td><td>' + esc(l.title) + '</td><td class="hint">' + esc(l.best_for) + '</td></tr>').join('') + '</tbody></table></div>', '#/styles');
}
function viewUsage() {
  const total = state.ledger.reduce((a, b) => a + (b.cny || 0), 0);
  const cnt = state.ledger.filter(x => x.action === 'generate').length;
  const avg = cnt ? Math.round(state.ledger.filter(x => x.action === 'generate').reduce((a, b) => a + (b.ms || 0), 0) / cnt) : 0;
  return shell('<h1 class="page">用量与成本</h1><p class="page-sub">本地渲染模式成本为 0；接入后端真出图后会按 provider 单价折算（模型可见）。</p>' +
    '<div class="cols-3"><div class="card"><div class="metric"><span class="metric-label">累计成本</span><span class="metric-value num">¥' + fmt2(total) + '</span></div></div>' +
    '<div class="card"><div class="metric"><span class="metric-label">生成次数</span><span class="metric-value num">' + cnt + '</span></div></div>' +
    '<div class="card"><div class="metric"><span class="metric-label">平均耗时</span><span class="metric-value num">' + avg + 'ms</span></div></div></div>' +
    (state.ledger.length ? '<div class="card" style="margin-top:16px;padding:0;overflow:hidden"><table class="ledger"><thead><tr><th>时间</th><th>动作</th><th>供应商</th><th>模型</th><th>尺寸</th><th style="text-align:right">耗时</th><th style="text-align:right">成本</th></tr></thead><tbody>' +
      state.ledger.slice(0, 60).map(r => '<tr><td class="num">' + esc(r.ts.replace('T', ' ')) + '</td><td>' + esc(r.action) + '</td><td class="num">' + esc(r.provider) + '</td><td class="num">' + esc(r.model) + '</td><td class="num">' + esc(r.size) + '</td><td class="num" style="text-align:right">' + (r.ms || 0) + 'ms</td><td class="num" style="text-align:right">¥' + fmt2(r.cny || 0) + '</td></tr>').join('') +
      '</tbody></table></div>' : empty('还没有用量记录', '生成一次即可看到明细', '#/', '去生成')), '#/usage');
}
function viewSettings() {
  const k = state.settings.keys || {};
  return shell('<h1 class="page">设置</h1><p class="page-sub">本地版把所有配置存在浏览器里（<b>仅本机</b>）。真实出图请用后端（见下方「连接本地后端」）。</p>' +
    '<div class="card"><h2 class="card-title">连接本地后端（可选）</h2>' +
    '<p class="card-desc">若你已启动 <code>bash server/run.sh</code>（:8640），打开开关即可让「内容梳理 / 生图」走后端真实模型；连不上会自动回落本地渲染。</p>' +
    '<div class="row"><label class="metric-label"><input type="checkbox" id="useBackend" ' + (state.settings.useBackend ? 'checked' : '') + '> 启用后端</label>' +
    '<input class="input" id="backendUrl" style="max-width:260px" value="' + esc(state.settings.backend) + '">' +
    '<button class="btn btn-secondary" id="btnPing">连通性测试</button><span class="status status-info" id="pingOut">未测试</span></div></div>' +
    '<div class="card" style="margin-top:16px"><h2 class="card-title">生图供应商密钥（本机保存）</h2>' +
    '<table class="ledger"><thead><tr><th>供应商</th><th>Key</th><th>状态</th></tr></thead><tbody>' +
    PROVIDERS.map(p => '<tr><td>' + esc(p.label) + '</td><td><input class="input" type="password" data-key="' + p.id + '" placeholder="填入后仅存本机" value="' + esc(k[p.id] || '') + '"></td>' +
      '<td class="num">' + (k[p.id] ? '<span class="status status-success">已填 ' + mask(k[p.id]) + '</span>' : '<span class="status status-warn">未填</span>') + '</td></tr>').join('') +
    '</tbody></table><div class="row" style="margin-top:12px"><button class="btn btn-primary" id="btnSaveKeys">保存</button>' +
    '<span class="hint">⚠️ 浏览器里保存 key 只适合自用演示；正式使用请填到后端 <code>config/.env</code> 或后端设置页（那里有掩码与热加载）。</span></div></div>' +
    '<div class="card" style="margin-top:16px"><h2 class="card-title">网络模式（后端生效）</h2>' +
    '<p class="card-desc">境外模型（gpt-image-2 / Nano Banana）需走代理；国内三家直连。<b>TUN 与 HTTP_PROXY 互斥</b>——用 TUN 客户端时后端要清空 HTTP_PROXY。</p>' +
    '<div class="row"><select class="input" id="netMode" style="width:200px">' +
    ['http_proxy', 'tun', 'none'].map(m => '<option ' + (state.settings.network === m ? 'selected' : '') + '>' + m + '</option>').join('') +
    '</select><span class="hint">改动需在后端同步（本页仅记录偏好）</span></div></div>', '#/settings');
}
function empty(title, desc, href, btn) {
  return '<div class="card"><div class="empty"><div style="font-size:34px">◫</div><h3 style="margin:6px 0">' + esc(title) + '</h3>' +
    '<p class="card-desc">' + esc(desc) + '</p><a class="btn btn-primary" href="' + href + '">' + esc(btn) + '</a></div></div>';
}
const mask = (s) => !s ? '' : s.slice(0, 3) + '*'.repeat(Math.max(4, s.length - 7)) + s.slice(-4);
"""

JS += r"""
/* ============================ 向导交互 ============================ */
function setStep(n) { state.wizard.step = n; render(); }
function currentPack() { return PACKS.find(p => p.id === state.wizard.packId) || PACKS[0]; }
async function step1Next() {
  const w = state.wizard;
  w.draft.title = ($('#pjTitle') || {}).value || w.draft.title;
  w.draft.text = ($('#txSource') || {}).value || '';
  w.draft.target = parseInt(($('#pjTarget') || {}).value || '10', 10) || 10;
  if (!w.draft.text.trim()) { alert('请先粘贴或载入内容'); return; }
  w.pages = localSplit(w.draft.text, w.draft.target);
  logUsage('parse', 'local', 'rule', '-', 0, 0, true, w.draft.text.length + ' 字 → ' + w.pages.length + ' 页');
  setStep(2);
}
async function step3Outline() {
  const w = state.wizard;
  $('#olNote') && ($('#olNote').textContent = '梳理中…');
  const keep = w.pages.filter(p => p.keep !== false);
  if (w.backendOn) {
    const r = await BACKEND.outline(keep.map(p => p.title + '\n' + (p.points || []).join('\n')).join('\n\n'), keep.length);
    if (r) { w.pages = r.pages.map(p => Object.assign(p, { keep: true })); w.olNote = '✅ 已通过本地后端梳理（' + r.note + '）；你可继续微调版式。'; logUsage('outline', 'deepseek', 'via-backend', '-', 0, 0, true, '后端梳理 ' + r.pages.length + ' 页'); }
    else { w.olNote = '后端不可用，已回落本地规则切页。'; }
  }
  setStep(3);
}
async function step4Generate() {
  const w = state.wizard;
  const pack = currentPack();
  const size = ($('#genSize') || {}).value || '2K';
  const pages = w.pages.filter(p => p.keep !== false);
  setStep(5);
  const grid = $('#thumbGrid'), bar = $('#genBar'), msg = $('#genMsg');
  const blobs = [];
  const t0 = performance.now();
  for (let i = 0; i < pages.length; i++) {
    const p = pages[i];
    msg.textContent = '正在生成第 ' + (i + 1) + '/' + pages.length + ' 页 · ' + p.title;
    let cv = null, provider = 'local_render', model = 'canvas', cny = 0;
    if (w.backendOn) {
      const r = await BACKEND.image(p, pack, p.layout, pages.length, w.draft.title);
      if (r && r.bitmap) {
        cv = document.createElement('canvas'); cv.width = r.bitmap.width; cv.height = r.bitmap.height;
        cv.getContext('2d').drawImage(r.bitmap, 0, 0);
        provider = r.provider; model = r.model; cny = r.cny || 0;
      }
    }
    if (!cv) cv = renderPageCanvas(p, pack, size, i + 1, pages.length, w.draft.title);
    const bytes = await canvasToBytes(cv);
    blobs.push(bytes);
    const url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
    const cell = document.createElement('div');
    cell.className = 'thumb ' + (w.selected.has(p.pageNo) ? 'selected' : '');
    cell.style.aspectRatio = 'auto';
    cell.innerHTML = '<img src="' + url + '" style="width:100%;display:block;border-radius:var(--radius-md)">' +
      '<span class="corner tag num">' + (i + 1) + '</span><span class="corner status status-info" style="left:auto;right:6px">' + esc(provider) + '</span>';
    cell.title = p.title;
    grid.appendChild(cell);
    bar.style.width = Math.round((i + 1) / pages.length * 100) + '%';
    logUsage('generate', provider, model, size, cny, 0, true, 'P' + (i + 1) + ' ' + p.layout);
  }
  const ms = Math.round(performance.now() - t0);
  w.slides = pages.map((p, i) => ({ pageNo: i + 1, title: p.title, outline: p.outline, points: p.points, layout: p.layout, blob: blobs[i], provider: 'local_render', size }));
  w.genNote = '✅ ' + pages.length + ' 页完成，用时 ' + (ms / 1000).toFixed(1) + 's（' + (w.backendOn ? '后端/本地混合' : '本地 Canvas 渲染') + '）';
  msg.textContent = w.genNote;
  persistCurrent(blobs);
}
function persistCurrent(blobs) {
  const w = state.wizard;
  const pid = w.pid || uid('p');
  w.pid = pid;
  const rec = { id: pid, title: w.draft.title, createdAt: nowISO(), packId: w.packId, size: w.size || '2K',
                pages: w.pages.filter(p => p.keep !== false), slides: (w.slides || []).map(s => ({ pageNo: s.pageNo, title: s.title, layout: s.layout, points: s.points, outline: s.outline })) };
  const i = state.projects.findIndex(p => p.id === pid);
  if (i >= 0) state.projects[i] = rec; else state.projects.unshift(rec);
  save();
}
function renderEditGrid() {
  const w = state.wizard, grid = $('#editGrid');
  if (!grid) return;
  grid.innerHTML = (w.slides || []).map(s => {
    const sel = w.selected.has(s.pageNo);
    const url = URL.createObjectURL(new Blob([s.blob], { type: 'image/png' }));
    return '<div class="thumb ' + (sel ? 'selected' : '') + '" data-toggle="' + s.pageNo + '" style="aspect-ratio:auto">' +
      '<img src="' + url + '" style="width:100%;display:block;border-radius:var(--radius-md)">' +
      '<span class="corner tag num">' + s.pageNo + '</span>' +
      '<span class="corner status ' + (sel ? 'status-success">可编辑' : 'status-info">图片直通') + '</span></div>';
  }).join('');
  $('#editCount').textContent = w.selected.size;
}
async function exportPptx(kind) {
  const w = state.wizard;
  if (!w.slides || !w.slides.length) { alert('请先生成页面'); return; }
  const editableSet = kind === 'editable' ? w.selected : new Set();
  const u8 = buildPptx(w.slides.map(s => ({ title: s.title, outline: s.outline, points: s.points, layout: s.layout })),
                       w.slides.map(s => s.blob), editableSet);
  const name = (w.draft.title || 'deck') + (kind === 'editable' ? '_可编辑版' : '_图片版') + '.pptx';
  download(name, u8);
  window.__lastPptx = { name, size: u8.length, kind, pages: w.slides.length, editable: Array.from(editableSet), b64: btoa(String.fromCharCode.apply(null, u8.slice(0, 1))) };
  // 供自动化验证：把完整字节暴露为 base64
  let s = ''; const CH = 0x8000;
  for (let i = 0; i < u8.length; i += CH) s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
  window.__lastPptxB64 = btoa(s);
  window.__lastPptxMeta = { name, kind, pages: w.slides.length, editable: Array.from(editableSet), sizeBytes: u8.length };
  logUsage(kind === 'editable' ? 'export_editable' : 'export_image', 'local_js', 'ooxml-writer', '-', 0, 0, true, name);
  if (kind === 'editable' && w.selected.size === 0) alert('当前未勾选任何页，导出的都是「图片直通」页（可在缩略图上点选要转可编辑的页）。');
}
"""

JS += r"""
/* ============================ 路由与事件 ============================ */
const SAMPLE = `## 项目概述
校园智慧零售平台，解决学生排队久、选品少的问题，已完成两个校区试点。
## 项目背景与痛点
- 校园超市高峰期平均排队 8.5 分钟
- 缺货感知率达到 37%
- 滞销商品库存周转超过 45 天
## 解决方案
- 学生端小程序：预定、拼单、到店自提码
- 商家端后台：库存预警与一键补货
- 运营端看板：品类结构与时段热力
## 技术架构
- 前端微信小程序 + 后台 Web；后端 FastAPI + PostgreSQL
- 单台 2 核 4G 云服务器，支持 500 并发
## 运营数据
试点 4 个月注册 3860 人，日均订单 412 单，复购率 63%，排队时长降至 2.1 分钟。
## 商业模式
商家 SaaS 服务费 600 元/月，交易抽成 2%，单校区年收入约 3.2 万元，毛利率 78%。
## 团队与分工
5 人团队：产品 1、开发 2、运营 1、市场 1；指导教师 2 人。
## 发展规划
第一阶段两校区试点完成；第二阶段扩展至 5 个校区；第三阶段输出标准化 SaaS。
## 成果与荣誉
校级创新创业大赛一等奖，入选省级大创计划项目，已申请软件著作权 1 项。`;

function render() {
  const h = location.hash || '#/';
  const app = $('#app');
  if (h.startsWith('#/projects')) app.innerHTML = viewProjects();
  else if (h.startsWith('#/styles')) app.innerHTML = viewStyles();
  else if (h.startsWith('#/usage')) app.innerHTML = viewUsage();
  else if (h.startsWith('#/settings')) app.innerHTML = viewSettings();
  else app.innerHTML = viewWizard();
  bind();
  if (h.startsWith('#/')) refreshCaps();
}
function refreshCaps() {
  const el = $('#capLine'); if (!el) return;
  el.textContent = state.settings.useBackend ? '后端模式（探测中）' : '本地 Canvas 渲染';
  BACKEND.ping().then(h => {
    if (!el) return;
    el.textContent = h ? ('后端在线 · ' + (h.providers.picked || '-')) : '本地 Canvas 渲染';
  });
  const c = $('#capCost'); if (c) c.textContent = '¥' + fmt2(state.ledger.reduce((a, b) => a + (b.cny || 0), 0));
}
function bind() {
  const on = (sel, ev, fn) => { const el = $(sel); if (el) el.addEventListener(ev, fn); };
  // 向导
  on('#btnSample', 'click', () => { $('#txSource').value = SAMPLE; $('#pjTarget').value = 9; hintChars(); });
  on('#txSource', 'input', hintChars);
  on('#btnToStep2', 'click', () => { state.wizard.backendOn = false; step1Next(); });
  on('#btnBack1', 'click', () => setStep(1));
  on('#btnBack2', 'click', () => setStep(2));
  on('#btnBack3', 'click', () => setStep(3));
  on('#btnBack4', 'click', () => setStep(4));
  on('#btnBack5', 'click', () => setStep(5));
  on('#btnToStep3', 'click', () => { collectPages(); if (state.wizard.backendOn === undefined) state.wizard.backendOn = state.settings.useBackend; step3Outline(); });
  on('#btnToStep4', 'click', () => setStep(4));
  on('#btnGenerate', 'click', () => { state.wizard.size = ($('#genSize') || {}).value || '2K'; state.wizard.backendOn = state.settings.useBackend; state.wizard.selected = new Set(); step4Generate(); });
  on('#btnToStep6', 'click', () => { setStep(6); setTimeout(renderEditGrid, 30); });
  on('#btnImgPptx', 'click', () => exportPptx('image'));
  on('#btnImgPptx2', 'click', () => exportPptx('image'));
  on('#btnEditPptx', 'click', () => exportPptx('editable'));
  $$('[data-pack]').forEach(el => el.addEventListener('click', () => { state.wizard.packId = el.dataset.pack; render(); }));
  $$('[data-toggle]').forEach(el => el.addEventListener('click', () => {
    const n = parseInt(el.dataset.toggle, 10);
    state.wizard.selected.has(n) ? state.wizard.selected.delete(n) : state.wizard.selected.add(n);
    renderEditGrid();
  }));
  // 项目
  $$('[data-open]').forEach(el => el.addEventListener('click', () => { location.hash = '#/'; }));
  $$('[data-del]').forEach(el => el.addEventListener('click', () => {
    state.projects = state.projects.filter(p => p.id !== el.dataset.del); save(); render();
  }));
  // 设置
  on('#btnPing', 'click', async () => {
    const out = $('#pingOut'); out.textContent = '测试中…';
    state.settings.useBackend = true; state.settings.backend = $('#backendUrl').value;
    const h = await BACKEND.ping();
    out.className = 'status ' + (h ? 'status-success' : 'status-danger');
    out.textContent = h ? ('在线 · 版本 ' + h.version + ' · 当前 ' + (h.providers.picked || '-')) : '连不上（确认后端已启动）';
    save();
  });
  on('#btnSaveKeys', 'click', () => {
    state.settings.keys = state.settings.keys || {};
    $$('[data-key]').forEach(i => { state.settings.keys[i.dataset.key] = i.value; });
    state.settings.useBackend = !!($('#useBackend') || {}).checked;
    state.settings.network = ($('#netMode') || {}).value || state.settings.network;
    save(); render(); alert('已保存到本机（浏览器 localStorage）');
  });
  on('#useBackend', 'change', e => { state.settings.useBackend = e.target.checked; save(); });
  on('#netMode', 'change', e => { state.settings.network = e.target.value; save(); });
}
function hintChars() { const el = $('#charHint'); if (el) el.textContent = ($('#txSource').value || '').length + ' 字'; }
function collectPages() {
  const w = state.wizard;
  $$('[data-keep]').forEach(cb => { const n = parseInt(cb.dataset.keep, 10); const p = w.pages.find(x => x.pageNo === n); if (p) p.keep = cb.checked; });
  $$('[data-title]').forEach(i => { const p = w.pages.find(x => x.pageNo === parseInt(i.dataset.title, 10)); if (p) p.title = i.value; });
  $$('[data-layout]').forEach(s => { const p = w.pages.find(x => x.pageNo === parseInt(s.dataset.layout, 10)); if (p) p.layout = s.value; });
  const kc = $('#keepCount'); if (kc) kc.textContent = w.pages.filter(p => p.keep !== false).length;
}
window.addEventListener('hashchange', render);
window.addEventListener('DOMContentLoaded', () => {
  load();
  if (!state.wizard.draft.text) state.wizard.draft.text = '';
  render();
  // 自动化验证入口
  window.__df = {
    state, PACKS, LAYOUTS, localSplit, renderPageCanvas, buildPptx, step1Next, step3Outline, step4Generate, exportPptx,
    // 供自动化验证：只构建字节、不触发下载
    buildBytes(kind) {
      const w = state.wizard;
      const editableSet = kind === 'editable' ? w.selected : new Set();
      return buildPptx(w.slides.map(s => ({ title: s.title, outline: s.outline, points: s.points, layout: s.layout })),
                       w.slides.map(s => s.blob), editableSet);
    },
    async drive(text, target) {
      location.hash = '#/';
      state.wizard = { step: 1, draft: { title: '自动化验收项目', text: '', target: target || 6 },
                       pages: [], packId: 'tech-deepblue', selected: new Set(), generated: 0, backendOn: false };
      render();                                   // 先渲染出步骤 1 的表单
      $('#pjTitle').value = '自动化验收项目';       // 必须写进 DOM——step1Next 是从表单读取的
      $('#txSource').value = text;
      $('#pjTarget').value = target || 6;
      await step1Next();
      setStep(3); await step3Outline();
      setStep(4); state.wizard.packId = 'biz-bluegold'; state.wizard.size = ($('#genSize') || {}).value || '2K';
      setStep(5); await step4Generate();
      setStep(6); renderEditGrid();
      return { pages: state.wizard.slides.length, step: state.wizard.step, title: state.wizard.draft.title };
    },
  };
});
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SlideCraft · AI 生成整套 PPT（本地单文件版）</title>
<style>
__CSS__
/* —— 应用外壳（本文件特有；组件样式全部来自 ui-design/app.css 令牌） —— */
.app { display: flex; min-height: 100vh; }
.side { width: 236px; flex: 0 0 236px; background: var(--color-surface); border-right: 1px solid var(--color-border); padding: 20px 16px; display: flex; flex-direction: column; gap: 18px; position: sticky; top: 0; height: 100vh; }
.brand { font-weight: 600; font-size: 18px; letter-spacing: .2px; }
.side nav { display: flex; flex-direction: column; gap: 4px; }
.side nav a { display: block; padding: 8px 10px; border-radius: var(--radius-sm); color: var(--color-ink); text-decoration: none; font-size: var(--text-body-sm); }
.side nav a:hover { background: var(--color-surface-alt); }
.side nav a.on { background: var(--color-surface-tag); color: var(--color-accent-tint-ink); font-weight: 500; }
.side-foot { margin-top: auto; border-top: 1px solid var(--color-divider); padding-top: 12px; }
.main { flex: 1; padding: 24px 28px 80px; max-width: 1240px; }
.topbar { position: sticky; top: 0; z-index: 5; background: color-mix(in srgb, var(--color-neutral) 92%, transparent); backdrop-filter: blur(8px); padding-bottom: 12px; margin-bottom: 4px; }
h1.page { font-size: var(--text-h1); margin: 0 0 4px; }
.page-sub { color: var(--color-ink-sub); margin: 0 0 16px; }
.cols-3 { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.hint { color: var(--color-ink-sub); font-size: var(--text-body-sm); }
.sw-mini { display: inline-block; width: 20px; height: 20px; border-radius: 5px; border: 1px solid var(--color-border); }
.swatches { display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 8px; }
.sw { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 6px; }
.sw-chip { height: 34px; border-radius: 4px; border: 1px solid var(--color-border); }
.sw-name { font-size: var(--text-caption); margin-top: 4px; }
.sw-hex { font-size: var(--text-caption); color: var(--color-ink-sub); }
.card.pack { cursor: pointer; }
.card.pack.sel { border-color: var(--color-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 16%, transparent); }
.toolbar-note { font-size: var(--text-caption); color: var(--color-ink-sub); }
code { background: var(--color-surface-alt); padding: 1px 5px; border-radius: 4px; font-family: var(--font-mono); font-size: .92em; }
</style>
</head>
<body>
<div id="app"></div>
<script>
const PACKS = __PACKS__;
const LAYOUTS = __LAYOUTS__;
const PROVIDERS = [
  { id: 'dashscope', label: '阿里百炼 Qwen-Image（国内直连）' },
];
__JS__
</script>
</body>
</html>
"""

HTML = HTML.replace("__CSS__", CSS).replace("__PACKS__", PACKS_JSON).replace("__LAYOUTS__", LAYOUTS_JSON).replace("__JS__", JS)
io.open(OUT, "w", encoding="utf-8").write(HTML)
print("✅ 已生成 %s（%.1f KB）" % (OUT, len(HTML.encode()) / 1024))
print("   风格包:", ", ".join(p["id"] for p in json.loads(PACKS_JSON)))
print("   版式:", ", ".join(l["key"] for l in json.loads(LAYOUTS_JSON)))
