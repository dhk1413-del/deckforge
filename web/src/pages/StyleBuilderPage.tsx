/** 风格构建页（#/style-builder）：上传 PPTX / PDF 模板或风格参考图 → 自动解析设计规范 → 预览 → 保存成新风格包。 */
import { StyleBuilderPanel } from '../components/StyleBuilderPanel'
import { Link, useNavigate } from '../router'

export function StyleBuilderPage() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="m-0 text-h1 font-semibold">风格构建</h1>
          <p className="m-0 mt-1 text-ink-sub">
            上传 <span className="num">.pptx / .pdf / .png / .jpg / .jpeg / .webp</span> 参考文件（图片可多张），自动解析出配色、字体层级、
            版式与画面语言，生成一套新的风格规范并写入风格库。
          </p>
        </div>
        <span className="flex-1" />
        <Link to="/styles" className="btn">
          返回风格库
        </Link>
      </div>
      <StyleBuilderPanel onSaved={(id) => navigate(`/styles/${id}`)} onCancel={() => navigate('/styles')} />
    </div>
  )
}
