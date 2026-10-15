/** 风格构建页（#/style-builder）：上传 PPTX / PDF 模板或风格参考图 → 自动解析设计规范 → 预览 → 保存成新风格包。 */
import { StyleBuilderPanel } from '../components/StyleBuilderPanel'
import { IconChevronRight } from '../components/Icons'
import { Link, useNavigate } from '../router'

export function StyleBuilderPage() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="m-0 text-h1 font-semibold">风格构建</h1>
        <span className="flex-1" />
        <Link to="/styles" className="btn btn-secondary rounded-full! gap-1.5! shadow-[0_1px_2px_rgba(16,40,90,.06)] transition-transform hover:-translate-x-0.5" title="回到风格库">
          <IconChevronRight className="h-4 w-4 rotate-180" aria-hidden="true" />
          返回风格库
        </Link>
      </div>
      <StyleBuilderPanel onSaved={(id) => navigate(`/styles/${id}`)} onCancel={() => navigate('/styles')} />
    </div>
  )
}
