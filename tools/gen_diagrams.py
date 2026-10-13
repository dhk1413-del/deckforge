# -*- coding: utf-8 -*-
"""生成使用说明里的流程图（SVG 真源，可复现；顺带导出 PNG 供 Word/PDF 使用）。

用法：
    .venv/bin/python tools/gen_diagrams.py            # 写入 docs/diagrams/*.svg
PNG 由一次性无头 Chrome 渲染（见 tools/render_diagrams.sh），避免依赖额外图形库。

约定：只用矩形/圆角矩形/直线/箭头/文字，配色走 ui-design 令牌（浅色为主，主色 #1E78FA）。
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'docs', 'diagrams')

ACCENT = '#1E78FA'
INK = '#101828'
SUB = '#5A6B87'
BORDER = '#D6E4F7'
FILL = '#F5F8FF'
FILL_ACCENT = '#EAF3FF'
ARROW = '#94A3B8'
FONT = "PingFang SC, Hiragino Sans GB, Microsoft YaHei, system-ui, sans-serif"


class Canvas:
    def __init__(self, width, height, title=None):
        self.w, self.h = width, height
        self.parts = []
        self.title = title

    def _add(self, markup):
        self.parts.append(markup)

    def box(self, x, y, w, h, title, lines=(), accent=False, dashed=False):
        fill = FILL_ACCENT if accent else FILL
        stroke = ACCENT if accent else BORDER
        dash = ' stroke-dasharray="6 4"' if dashed else ''
        self._add('<rect x="%s" y="%s" width="%s" height="%s" rx="12" fill="%s" stroke="%s"%s/>'
                  % (x, y, w, h, fill, stroke, dash))
        cursor = y + 26
        if title:
            self._add('<text x="%s" y="%s" font-family="%s" font-size="15" font-weight="700" fill="%s" text-anchor="middle">%s</text>'
                      % (x + w / 2, cursor, FONT, INK, esc(title)))
            cursor += 20
        for line in lines:
            self._add('<text x="%s" y="%s" font-family="%s" font-size="12" fill="%s" text-anchor="middle">%s</text>'
                      % (x + w / 2, cursor, FONT, SUB, esc(line)))
            cursor += 16

    def text(self, x, y, value, size=13, color=SUB, anchor='start', bold=False, italic=False):
        self._add('<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s" text-anchor="%s"%s%s>%s</text>'
                  % (x, y, FONT, size, color, anchor, ' font-weight="700"' if bold else '',
                     ' font-style="italic"' if italic else '', esc(value)))

    def arrow(self, x1, y1, x2, y2, label=None, dashed=False, both=False):
        dash = ' stroke-dasharray="6 4"' if dashed else ''
        marker_end = ' marker-end="url(#arrow)"'
        marker_start = ' marker-start="url(#arrow)"' if both else ''
        self._add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.6"%s%s%s/>'
                  % (x1, y1, x2, y2, ARROW, dash, marker_end, marker_start))
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            self._add('<text x="%s" y="%s" font-family="%s" font-size="11" fill="%s" text-anchor="middle">%s</text>'
                      % (mx, my - 6, FONT, SUB, esc(label)))

    def path_arrow(self, d, label=None):
        self._add('<path d="%s" fill="none" stroke="%s" stroke-width="1.6" marker-end="url(#arrow)"/>' % (d, ARROW))
        if label:
            self.text(0, 0, '', 1)  # 占位，标签由调用方显式放置

    def render(self):
        head = ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s" '
                'role="img" aria-label="%s">' % (self.w, self.h, self.w, self.h, esc(self.title or '流程图')))
        defs = ('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % ARROW)
        bg = '<rect width="100%%" height="100%%" fill="#FFFFFF"/>'
        title = ''
        if self.title:
            title = '<text x="24" y="34" font-family="%s" font-size="17" font-weight="700" fill="%s">%s</text>' % (FONT, INK, esc(self.title))
        return '\n'.join([head, defs, bg, title] + self.parts + ['</svg>'])


def esc(value):
    return (str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


DIAGRAMS = {}


def diagram(name):
    def wrap(fn):
        DIAGRAMS[name] = fn
        return fn
    return wrap


@diagram('architecture')
def architecture():
    c = Canvas(1080, 620, 'DeckForge 系统架构')
    c.box(40, 80, 250, 130, '浏览器界面', ['React 19 + TypeScript + Tailwind v4', '构建产物由后端托管', '（浅色为主，中文界面）'], accent=True)
    c.box(40, 250, 250, 120, '单文件离线网页', ['deckforge-standalone.html', '零依赖，数据存 localStorage'])
    c.box(380, 80, 300, 130, 'FastAPI 服务（本机常驻）', ['/api/* 路由层 · main.py', '作业与流水线 · pipeline.py', 'SSE 逐页进度 / 取消'])
    c.box(380, 250, 300, 120, '渲染与导出', ['render.py 本地兜底渲染', 'pptx/render_native.mjs（PptxGenJS）', 'export_pptx.py 图片版装配'])
    c.box(380, 410, 300, 110, '数据与文件', ['SQLite（WAL）· data/deckforge.db', 'data/files/<项目>/ 原稿与产物'])
    c.box(760, 80, 280, 130, '文本模型', ['DeepSeek：内容梳理 / 备注', '无 key 时本地规则切页兜底'])
    c.box(760, 240, 280, 120, '视觉模型', ['Qwen-VL 等 OpenAI 兼容端点', '无 key 时本地色板/插画分析'])
    c.box(760, 390, 280, 130, '生图模型', ['GuaiHub / 阿里百炼', '无 key 时 local_render 兜底（费用 0）'])
    c.arrow(290, 145, 380, 145, 'HTTP / SSE')
    c.arrow(290, 310, 380, 310, '可选：连接本地后端')
    c.arrow(680, 145, 760, 145)
    c.arrow(680, 300, 760, 300)
    c.arrow(680, 430, 760, 455)
    c.arrow(530, 210, 530, 250)
    c.arrow(530, 370, 530, 410)
    c.text(40, 560, '铁律：内容归模型、格式归代码；取不到真源就少画一个元素，绝不编造；零 key 全流程可跑通。', 12, SUB)
    return c


@diagram('flow-document')
def flow_document():
    c = Canvas(1080, 430, '流程一：文档导入生成（把 Markdown / TXT / DOCX / PDF / PPTX 变成整套 PPT）')
    steps = [
        ('① 输入内容', ['上传文档或粘贴文本', '解析出全文与建议页数']),
        ('② 页面确认', ['逐页勾选参与范围', '改标题、选版式']),
        ('③ 内容确认', ['逐页核对标题与要点', '保存状态/修订冲突可见']),
        ('④ 选择风格', ['风格库或自定义风格包', '预览与选择分离']),
        ('⑤ 生成结果', ['逐页出图 + 进度', '导出图片版 / 可编辑版']),
    ]
    x = 40
    for i, (title, lines) in enumerate(steps):
        c.box(x, 90, 180, 130, title, lines, accent=(i == 0))
        if i:
            c.arrow(x - 22, 155, x - 4, 155)
        x += 202
    c.text(40, 270, '每一步都能刷新/直链（#/wizard/<项目>/<1..5>）；步骤条按真实数据放行，未就绪的步骤会说明缺什么。', 12)
    c.arrow(130, 330, 130, 250, '可回退修改')
    c.text(40, 360, '零 key 时：大纲走本地切页，出图走 local_render 本地兜底（费用 0 元），整条流程与导出照常可用。', 12)
    c.text(40, 386, '细化重建可选：把已生成的图片页交给「精细重建引擎」转成原生可编辑对象（约 13 分钟/页）。', 12)
    return c


@diagram('flow-beautify')
def flow_beautify():
    c = Canvas(1080, 520, '流程二：PPT 美化（原稿先预览、确认后全量、可转可编辑）')
    c.box(40, 90, 200, 120, '① 上传内容', ['拖入 PPTX / PDF', '按原页顺序识别'])
    c.box(270, 90, 200, 120, '② 页面确认', ['原页缩略图逐页勾选', '可选「保留原页图片素材」'])
    c.box(500, 90, 200, 120, '③ 内容梳理', ['左栏切页 · 单页呈现', '文字按最终页面样式预览'])
    c.box(730, 90, 200, 120, '④ 选择风格', ['风格包 / 自定义风格', 'img2img 或 redesign'])
    c.box(846, 250, 190, 110, '⑤ 生成结果', ['逐页结果 · 放大查看', '可单页重新生成'], accent=True)
    c.arrow(240, 150, 270, 150)
    c.arrow(470, 150, 500, 150)
    c.arrow(700, 150, 730, 150)
    c.arrow(830, 210, 900, 250, '前 3 页预览')
    c.box(560, 250, 250, 110, '确认预览 → 全量生成', ['只补未生成的页，不重跑预览页', '随后 Codex 重建全部页'])
    c.arrow(846, 305, 810, 305)
    c.box(560, 400, 250, 90, '导出', ['图片集 PPT（整页铺底）', '可编辑版 PPT（原生对象）'])
    c.arrow(685, 360, 685, 400)
    c.text(40, 300, '预览阶段只生成所选页的前 3 页；', 12)
    c.text(40, 322, '费用与警告在「生成详情」里逐项列出，', 12)
    c.text(40, 344, '未配置单价时金额记 0 并明确提示「不代表免费」。', 12)
    c.text(40, 400, '单页重新生成是非破坏性操作：', 12)
    c.text(40, 422, '只重写该页，其它页结果与导出一律不动。', 12)
    c.text(40, 470, '零 key 时逐页生图降级为「原图直通」，并在结果页如实标注「已用原图」。', 12)
    return c


@diagram('flow-editable')
def flow_editable():
    c = Canvas(1080, 430, '流程三：图片转可编辑（第三方精细重建引擎）')
    c.box(40, 90, 210, 120, '① 导入原页', ['PDF / PNG / JPG / PPTX', '逐页渲染成原页图'], accent=True)
    c.box(285, 90, 210, 120, '② 勾选页面', ['只转换选中的页', '未勾选页永不自动转换'])
    c.box(530, 90, 210, 120, '③ 引擎探测', ['GET /api/editable-engines', '缺 CLI/skill 时如实报错'])
    c.box(775, 90, 265, 120, '④ 逐页重建', ['prepare → dispatch → page build', '→ validate → run finalize'])
    c.box(775, 270, 265, 110, '⑤ 产物与校验', ['页面自带 validation.json', '任一页不过 → 整个作业 failed'], accent=True)
    c.arrow(250, 150, 285, 150)
    c.arrow(495, 150, 530, 150)
    c.arrow(740, 150, 775, 150)
    c.arrow(907, 210, 907, 270)
    c.text(40, 280, '实测约 13 分钟/页；产物只含所转页面，导出为 /files 下的独立文件。', 12)
    c.text(40, 306, '失败会保留 run 目录与失败明细（页码 / 阶段 / 原因），可 resume=true 复用现场续跑。', 12)
    c.text(40, 356, '与「文档生成」的区别：这里不重新排版，而是把原页的文字与形状重建为可编辑对象。', 12)
    return c


@diagram('flow-notes')
def flow_notes():
    c = Canvas(1080, 400, '独立模块：PPT 备注（给已有 .pptx 逐页写演讲者备注）')
    c.box(40, 90, 220, 120, '① 上传 PPTX', ['秒回页清单', '不调用模型、不花钱'], accent=True)
    c.box(300, 90, 220, 120, '② 画面识别', ['auto / all / off 三档', '逐页结果可核验'])
    c.box(560, 90, 220, 120, '③ 写备注', ['只依据本页文字+识别结果', '可填一句要求让 AI 重写'])
    c.box(820, 90, 220, 120, '④ 导出', ['写回备注栏的副本', '原页面内容/版式不动'], accent=True)
    c.arrow(260, 150, 300, 150)
    c.arrow(520, 150, 560, 150)
    c.arrow(780, 150, 820, 150)
    c.text(40, 260, '硬约定：备注内容只能来自该页文本框/表格 + 画面识别；两者皆空就不生成，并说明原因（不允许模型凭常识补全）。', 12)
    c.text(40, 286, '渲染 PDF 页数必须等于 pptx 页数，否则拒绝继续——防止备注错页；导出前会再校验一次。', 12)
    c.text(40, 312, '原备注默认保留，AI 备注以「【演讲备注】」分隔追加在下方；零 key 时上传/解析可用，识别与写作会明确提示未配置。', 12)
    return c


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in DIAGRAMS.items():
        path = os.path.join(OUT, name + '.svg')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(fn().render())
        print('✓ docs/diagrams/%s.svg' % name)


if __name__ == '__main__':
    main()
