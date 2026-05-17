/**
 * Workflow 步骤导航状态管理
 * 使用 sessionStorage 在跨页面间共享 workflow ID 链和步骤完成状态
 */
const KEYS = {
  projectId: 'wf_projectId',
  simulationId: 'wf_simulationId',
  reportId: 'wf_reportId',
  completedSteps: 'wf_completedSteps',
  currentStep: 'wf_currentStep'
}

export function saveWorkflowId(key, value) {
  if (value != null) {
    sessionStorage.setItem(KEYS[key], String(value))
  }
}

export function getWorkflowId(key) {
  return sessionStorage.getItem(KEYS[key])
}

export function markStepCompleted(stepNumber) {
  const steps = getCompletedSteps()
  if (!steps.includes(stepNumber)) {
    steps.push(stepNumber)
    steps.sort((a, b) => a - b)
    sessionStorage.setItem(KEYS.completedSteps, JSON.stringify(steps))
  }
}

export function getCompletedSteps() {
  try {
    return JSON.parse(sessionStorage.getItem(KEYS.completedSteps) || '[]')
  } catch {
    return []
  }
}

export function setCurrentStep(stepNumber) {
  sessionStorage.setItem(KEYS.currentStep, String(stepNumber))
}

export function getCurrentStep() {
  const v = sessionStorage.getItem(KEYS.currentStep)
  return v ? parseInt(v, 10) : null
}

export function markSimulationCompleted(simulationId) {
  if (simulationId) {
    sessionStorage.setItem('wf_simulationCompleted', String(simulationId))
  }
}

export function isSimulationCompleted(simulationId) {
  return sessionStorage.getItem('wf_simulationCompleted') === String(simulationId)
}

export function resetWorkflow() {
  Object.values(KEYS).forEach(k => sessionStorage.removeItem(k))
  sessionStorage.removeItem('wf_simulationCompleted')
}
