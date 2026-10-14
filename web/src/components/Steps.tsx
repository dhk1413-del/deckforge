/** 文档生成向导的步骤定义；步骤条由 FlowSteps 渲染。 */
export const WIZARD_STEPS = [
  { key: 1, label: '输入内容' },
  { key: 2, label: '页面确认' },
  { key: 3, label: '内容确认' },
  { key: 4, label: '选择风格' },
  { key: 5, label: '生成结果' },
] as const

export type WizardStepNo = (typeof WIZARD_STEPS)[number]['key']
