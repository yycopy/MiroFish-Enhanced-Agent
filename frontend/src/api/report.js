import service, { requestWithRetry } from './index'

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/generate', data), 3, 1000)
}

/**
 * 获取报告生成状态
 * @param {string} reportId
 */
export const getReportStatus = (reportId) => {
  return service.get(`/api/report/generate/status`, { params: { report_id: reportId } })
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/chat', data), 3, 1000)
}

// ============== 可追溯报告接口 ==============

/**
 * 运行可追溯报告（增强版ReportAgent）
 * @param {Object} payload - { simulation_id, question?, use_review? }
 */
export const runTraceableReport = (payload) => {
  return service.post('/api/report/traceable', payload)
}

/**
 * 获取可追溯报告
 * @param {string} reportId
 */
export const getTraceableReport = (reportId) => {
  return service.get(`/api/report/traceable/${reportId}`)
}

/**
 * 查询可追溯报告生成进度
 * @param {string} taskId
 */
export const getTraceableStatus = (taskId) => {
  return service.get('/api/report/traceable/status', { params: { task_id: taskId } })
}

// ============== ReportAgent 工具日志 ==============

/**
 * 获取ReportAgent工具调用日志
 * @param {Object} params - { report_id?, limit? }
 */
export const listReportToolLogs = (params = {}) => {
  return service.get('/api/report/tool-logs', { params })
}

// ============== 多Agent可信评审 ==============

/**
 * 列出评审声明
 * @param {string} reportId - 可选，按报告ID过滤
 */
export const listReviewClaims = (reportId) => {
  const params = reportId ? { report_id: reportId } : {}
  return service.get('/api/review/claims', { params })
}

/**
 * 评估一个声明（5角色评审）
 * @param {Object} payload - { claim, evidence_context? }
 */
export const evaluateClaim = (payload) => {
  return service.post('/api/review/evaluate', payload)
}

// ============== 长期记忆接口 ==============

/**
 * 列出记忆条目
 * @param {Object} params - { keyword?, limit?, offset?, event_id?, source_type? }
 */
export const listMemoryItems = (params = {}) => {
  return service.get('/api/memory/items', { params })
}

/**
 * 获取单条记忆详情
 * @param {number} memoryId
 */
export const getMemoryItem = (memoryId) => {
  return service.get(`/api/memory/items/${memoryId}`)
}
