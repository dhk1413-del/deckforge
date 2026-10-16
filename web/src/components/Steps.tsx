/** 文档生成向导的步骤定义；步骤条由 FlowSteps 渲染。 */
export const WIZARD_STEPS = [
  { key: 1, label: '上传内容' },
  { key: 2, label: '编辑大纲' },
  { key: 3, label: '内容梳理' },
  { key: 4, label: '选择风格' },
  { key: 5, label: '确认设计' },
  { key: 6, label: '生成页面' },
] as const

export type WizardStepNo = (typeof WIZARD_STEPS)[number]['key']
