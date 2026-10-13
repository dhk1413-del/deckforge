# -*- coding: utf-8 -*-
"""读取 CSS 生成器上下文与 app.css，生成自包含的 v2 明暗预览页。"""
import io, json, os
from pathlib import Path

R = str(Path(__file__).resolve().parents[1] / "ui-design")
ctx = json.load(io.open("/tmp/pm/ui_ctx.json", encoding="utf-8"))
colors, spacing, rounded, typo, dark = ctx["colors"], ctx["spacing"], ctx["rounded"], ctx["typo"], ctx["dark"]

def lin(c):
    c = c/255.0
    return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
def lum(h):
    h = h.lstrip("#"); r,g,b = (int(h[i:i+2],16) for i in (0,2,4))
    return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)
def cr(a,b):
    la,lb = lum(a),lum(b); hi,lo = max(la,lb),min(la,lb); return (hi+0.05)/(lo+0.05)
# CSS 与暗色令牌由 gen_ui_css.py 唯一生成；预览不回写它。
css = io.open(os.path.join(R, "app.css"), encoding="utf-8").read()
print("暗色 primary：%s，白字对比 %.2f:1" % (dark["primary"], cr("#FFFFFF", dark["primary"])))

# ── 生成预览页（自包含：内联 app.css）──
def swatch(name, val):
    return ('<div class="sw"><div class="sw-chip" style="background:%s"></div>'
            '<div class="sw-name">%s</div><div class="sw-hex num">%s</div></div>' % (val, name, val.upper()))

color_cards = "\n".join(swatch(k, v) for k, v in colors.items())
typo_rows = "\n".join(
    '<tr><td class="num">%s</td><td style="font-family:%s;font-size:%s;font-weight:%s">DeckForge 智能 PPT 生成工作台 / 0123456789</td>'
    '<td class="num">%s · %s</td></tr>' % (k, t["f"], t["size"], t["w"], t["size"], t["w"])
    for k, t in typo.items())

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>DeckForge UI 设计规范 · 预览</title>
<style>
{css}
/* —— 预览页自身的排版（不属于规范）—— */
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 96px; }}
h1.page {{ font-size: var(--text-h1); margin: 0 0 4px; }}
.page-sub {{ color: var(--color-ink-sub); margin: 0 0 8px; }}
section {{ margin-top: 40px; }}
section > h2 {{ font-size: var(--text-h2); margin: 0 0 4px; }}
section > .hint {{ color: var(--color-ink-sub); font-size: var(--text-body-sm); margin: 0 0 16px; }}
.grid {{ display: grid; gap: 16px; }}
.row {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
.swatches {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(132px, 1fr)); gap: 12px; }}
.sw {{ background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 8px; }}
.sw-chip {{ height: 44px; border-radius: var(--radius-sm); border: 1px solid var(--color-border); }}
.sw-name {{ font-size: var(--text-caption); margin-top: 6px; }}
.sw-hex {{ font-size: var(--text-caption); color: var(--color-ink-sub); }}
.cols-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.cols-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.code {{ background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md);
        padding: 16px; overflow: auto; font-family: var(--font-mono); font-size: 12px; line-height: 1.6; color: var(--color-ink-sub); }}
.toolbar {{ position: sticky; top: 0; z-index: 9; background: color-mix(in srgb, var(--color-neutral) 88%, transparent);
           backdrop-filter: blur(8px); border-bottom: 1px solid var(--color-border); padding: 10px 0; }}
</style>
</head>
<body>
<div class="toolbar"><div class="wrap" style="padding-top:0;padding-bottom:0;display:flex;gap:12px;align-items:center">
  <strong>DeckForge UI 规范预览</strong>
  <span class="tag">浅色为主</span>
  <span class="num" style="color:var(--color-ink-sub)">{len(colors)} 色 · 25 组件</span>
  <span style="flex:1"></span>
  <button class="btn btn-secondary" onclick="document.documentElement.toggleAttribute('data-theme');var d=document.documentElement.hasAttribute('data-theme');document.documentElement.setAttribute('data-theme', d?'dark':'light')">切换明/暗（演示）</button>
</div></div>

<div class="wrap">
  <h1 class="page">DeckForge 界面设计规范</h1>
  <p class="page-sub">浅色为主的企业级蓝调工作台 · 令牌逐像素取自参考图 · 卡片柔和投影 · 色带分层 · 保留暗色</p>

  <section>
    <h2>1 · 颜色令牌（{len(colors)} 个）</h2>
    <p class="hint">改版同步 <code>ui-design/tokens.json</code> 与生成器模板 并重导出，此处与组件自动同步。</p>
    <div class="swatches">{color_cards}</div>
  </section>

  <section>
    <h2>2 · 排版</h2>
    <p class="hint">正文基准 14px；数字继承正文字体，仅启用 tnum 对齐。</p>
    <div class="card"><table class="ledger">
      <thead><tr><th style="width:110px">令牌</th><th>示例</th><th style="width:180px">规格</th></tr></thead>
      <tbody>{typo_rows}</tbody>
    </table></div>
  </section>

  <section class="hero">
    <div class="hero-content">
      <h2>蓝色云平台风 · v2</h2>
      <p class="page-sub">Hero 渐变带、柔和投影与成组色带；数字继承正文，页脚保持浅色。</p>
    </div>
  </section>
  <section class="band">
    <h2>3 · 按钮</h2>
    <p class="hint">主按钮填充用 <code>primary #2068F0</code>；主按钮采用品牌渐变；<code>accent #3B8DF7</code> 只用于图形，不做白字底色。</p>
    <div class="row">
      <button class="btn btn-primary">开始生成 ›</button>
      <button class="btn btn-secondary">详情/取消</button>
      <button class="btn btn-ghost">重新生成</button>
      <button class="btn btn-primary" disabled>未配置模型</button>
      <button class="btn btn-primary is-disabled"><span class="spinner">◌</span> 生成中…</button>
    </div>
  </section>

  <section class="band">
    <h2>4 · 标签 / 角标</h2>
    <div class="tabs" style="margin:12px 0"><button class="btn" aria-pressed="true">已选页签</button><button class="btn" aria-pressed="false">其他页签</button></div>
    <div class="chips" style="margin-bottom:12px"><button aria-pressed="true">已选筛选</button><button aria-pressed="false">其他筛选</button></div>
    <div class="row">
      <span class="tag">AI 写作</span><span class="tag">报告生成</span><span class="tag">智能分析</span>
      <span class="badge">旗舰产品</span><span class="badge">上新</span>
    </div>
  </section>

  <section>
    <h2>5 · 卡片（风格包示例）</h2>
    <div class="cols-3">
      <div class="card"><h3 class="card-title">深蓝光感科技发布风</h3>
        <p class="card-desc">发布会 / 技术方案 · 深底冷蓝渐变</p>
        <div class="row"><span class="tag">科技</span><span class="tag">深色</span><span class="badge">热门</span></div>
        <p style="color:var(--color-ink-sub);font-size:var(--text-caption);margin:16px 0 12px">适用于 46 个页面 · 3 张预览</p>
        <button class="btn btn-primary">选用</button></div>
      <div class="card"><h3 class="card-title">商务蓝金汇报风</h3>
        <p class="card-desc">政务 / 国央企汇报 · 白底衬线标题 + 细金线</p>
        <div class="row"><span class="tag">商务</span><span class="tag">汇报</span></div>
        <p style="color:var(--color-ink-sub);font-size:var(--text-caption);margin:16px 0 12px">适用于 32 个页面 · 3 张预览</p>
        <button class="btn btn-secondary">选用</button></div>
      <div class="card"><h3 class="card-title">医疗青蓝专业风</h3>
        <p class="card-desc">临床 / 护理 / 培训 · 洁净白底 + 青蓝主色</p>
        <div class="row"><span class="tag">医疗</span><span class="tag">学术</span><span class="badge">推荐</span></div>
        <p style="color:var(--color-ink-sub);font-size:var(--text-caption);margin:16px 0 12px">适用于 28 个页面 · 3 张预览</p>
        <button class="btn btn-secondary">选用</button></div>
    </div>
  </section>

  <section>
    <h2>6 · 表单</h2>
    <div class="cols-2">
      <div class="card"><label class="metric-label">DeepSeek API Key</label>
        <input class="input" placeholder="sk-… （留空则仅文案梳理不可用）" style="margin-top:6px">
        <p class="hint" style="margin:8px 0 0">已加密存储，回显仅显示 <code class="num">sk-****1234</code></p></div>
      <div class="card"><label class="metric-label">生图供应商</label>
        <input class="input" value="OpenAI gpt-image-2（对标同源）" style="margin-top:6px">
        <p class="hint" style="margin:8px 0 0">切换不影响已完成的项目；失败自动轮换下一家</p></div>
    </div>
  </section>

  <section>
    <h2>7 · 步骤条（6 步流程）</h2>
    <p class="hint">已完成步骤可回跳；<code>⑤ 生成结果</code> 后另有可选的 <code>⑥ 转可编辑</code>（用户手动触发）。</p>
    <div class="card"><div class="steps">
      <span class="step done">① 上传内容 ✓</span><span class="step-sep">›</span>
      <span class="step done">② 页面确认 ✓</span><span class="step-sep">›</span>
      <span class="step done">③ 内容梳理 ✓</span><span class="step-sep">›</span>
      <span class="step active">④ 选择风格（进行中）</span><span class="step-sep">›</span>
      <span class="step pending">⑤ 生成结果</span><span class="step-sep">›</span>
      <span class="step pending">⑥ 转可编辑</span>
    </div>
    <div style="margin-top:16px"><div class="progress"><i style="width:62%"></i></div>
      <p class="hint" style="margin-top:8px">已完成 <span class="num">8/13</span> 页 · 预计剩余 <span class="num">00:42</span></p></div>
    <div class="row" style="margin-top:12px"><span class="step error">③ 内容梳理 · 失败（点击重试）</span></div>
    </div>
  </section>

  <section>
    <h2>8 · 缩略图网格（含可编辑 / 图片直通标记）</h2>
    <p class="hint">可编辑性与失败态**必须用文字角标**明示，不得只靠颜色。</p>
    <div class="card"><div class="thumb-grid">
      <div class="thumb selected"><span class="corner tag">已选</span>P1<span class="pageno num">1/13</span></div>
      <div class="thumb"><span class="corner status status-success">可编辑</span>P2<span class="pageno num">2/13</span></div>
      <div class="thumb"><span class="corner status status-info">图片直通</span>P3<span class="pageno num">3/13</span></div>
      <div class="thumb"><span class="corner status status-warn">生成中</span>P4<span class="pageno num">4/13</span></div>
      <div class="thumb"><span class="corner status status-danger">失败</span>P5<span class="pageno num">5/13</span></div>
      <div class="thumb">P6<span class="pageno num">6/13</span></div>
    </div>
    <div class="row" style="margin-top:16px">
      <button class="btn btn-primary">转可编辑 PPTX（已选 1 页）</button>
      <button class="btn btn-secondary">换风格</button>
      <button class="btn btn-secondary">下载图片版</button>
      <span class="hint" style="margin:0">预计耗时 <span class="num">6s</span> · 成本 <span class="num">¥0.00</span>（本地 OCR）</span>
    </div></div>
  </section>

  <section>
    <h2>9 · 状态胶囊 / 成本揭示 / 账本</h2>
    <div class="row" style="margin-bottom:16px">
      <span class="status status-success">成功</span><span class="status status-warn">配额不足</span>
      <span class="status status-danger">调用失败</span><span class="status status-info">复用历史结果</span>
    </div>
    <div class="cols-2">
      <div class="card"><div class="row" style="gap:32px">
        <div class="metric"><span class="metric-label">本页成本</span><span class="metric-value num">¥0.50</span></div>
        <div class="metric"><span class="metric-label">本月累计</span><span class="metric-value num">¥12.86</span></div>
        <div class="metric"><span class="metric-label">耗时</span><span class="metric-value num">7.4s</span></div>
      </div>
      <p class="hint" style="margin:12px 0 0">模型 <code>openai_official · gpt-image-2 · 2K</code>（每次生成都记录，见 D19）</p></div>
      <div class="card" style="padding:0;overflow:hidden"><table class="ledger">
        <thead><tr><th>时间</th><th>动作</th><th>模型</th><th style="text-align:right">金额</th></tr></thead>
        <tbody>
          <tr><td class="num">10:42</td><td>生成 P1–P13</td><td class="num">gpt-image-2·2K</td><td class="num" style="text-align:right">¥6.50</td></tr>
          <tr><td class="num">10:43</td><td>文案梳理</td><td class="num">deepseek-v4-pro</td><td class="num" style="text-align:right">¥0.06</td></tr>
          <tr><td class="num">10:51</td><td>转可编辑 ×1</td><td class="num">本地 OCR</td><td class="num" style="text-align:right">¥0.00</td></tr>
        </tbody></table></div>
    </div>
  </section>

  <section>
    <h2>10 · 空状态 / 错误态 / Toast</h2>
    <div class="cols-3">
      <div class="card"><div class="empty">
        <div style="font-size:32px">◫</div>
        <p class="card-title" style="font-size:var(--text-h3)">还没有项目</p>
        <p class="card-desc">导入一份文档，或按页录入内容开始</p>
        <button class="btn btn-primary">导入文档</button></div></div>
      <div class="card"><div class="error-box">
        <strong>生图模型未配置</strong>
        <p style="margin:8px 0">缺少 <code class="num">OPENAI_API_KEY</code>。到「设置 → 模型与密钥」填写后点「连通性测试」即可。</p>
        <div class="row"><button class="btn btn-secondary">去填写</button><button class="btn btn-ghost">复制详情</button></div></div></div>
      <div class="card"><div class="row" style="flex-direction:column;align-items:stretch;gap:12px">
        <div class="toast"><span class="status status-success">成功</span> 13 页已生成，用时 <span class="num">58s</span></div>
        <div class="toast"><span class="status status-warn">注意</span> 第 5 页文字校验未通过</div>
        <div class="toast"><span class="status status-danger">失败</span> 节点超时，已自动切换供应商</div>
      </div></div>
    </div>
  </section>

  <section>
    <h2>11 · 暗色（Phase 2 演示）</h2>
    <p class="hint">仅令牌级覆盖：暗色把 <code>primary</code> 压深到 <code>{dark['primary']}</code>（白字 {cr('#FFFFFF', dark['primary']):.2f}:1），<code>accent</code> 保持 <code>{dark['accent']}</code> 供图形使用。</p>
    <div class="card" data-theme="dark" style="background:var(--color-neutral);border-color:var(--color-border)">
      <div class="row">
        <span class="step active">④ 选择风格</span><span class="step done">③ 内容梳理 ✓</span><span class="step pending">⑤ 生成结果</span>
        <button class="btn btn-primary">开始生成 ›</button>
        <button class="btn btn-secondary">取消</button>
        <span class="tag">科技</span><span class="status status-success">可编辑</span><span class="status status-warn">生成中</span>
      </div>
      <p style="color:var(--color-ink-sub);margin:12px 0 0">暗色下的正文与辅助文字对比度均已 ≥4.5:1（实现时仍须跑 CLI lint 复核）。</p>
    </div>
  </section>

  <section>
    <h2>12 · 接入代码（复制即用）</h2>
    <p class="hint">Tailwind v4：入口 CSS <code>@import "./tailwind.theme.css";</code>；非 Tailwind 项目直接 <code>@import "./app.css"</code>。</p>
    <div class="code">/* ui-design/tailwind.theme.css（节选） */
@theme {{
  --color-neutral: {colors['neutral']};       /* 页面底 */
  --color-surface: {colors['surface']};       /* 卡片 */
  --color-border: {colors['border']};         /* 描边 */
  --color-ink: {colors['ink']};               /* 主文字 */
  --color-primary: {colors['primary']};       /* 按钮填充 / 白底蓝字 */
  --color-accent: {colors['accent']};         /* 图标 / 描边 / 选中（不做白字底色） */
  --color-accent-tint-ink: {colors['accent-tint-ink']}; /* 浅蓝底上的蓝字 */
  --font-mono: "JetBrains Mono", ui-monospace, monospace;  /* 数字 */
  --radius-md: {rounded['md']};
}}</div>
  </section>
</div>
</body>
</html>
"""
io.open(os.path.join(R, "preview.html"), "w", encoding="utf-8").write(HTML)
print("✅ preview.html (%d 字节)" % len(HTML.encode()))
