import service from './index'

// Events
export const listEvents = () => service.get('/api/events')
export const createEvent = (payload) => service.post('/api/events', payload)

// Ingestion tasks (thin wrappers — also available in simulation.js)
export const listIngestionTasks = (params = {}) => service.get('/api/ingestion/tasks', { params })
export const getIngestionTask = (taskId) => service.get(`/api/ingestion/tasks/${taskId}`)
export const triggerIngestionTask = (payload) => service.post('/api/ingestion/tasks', payload)
export const retryIngestionTask = (taskId) => service.post(`/api/ingestion/tasks/${taskId}/retry`)

// Memory items
export const listMemoryItems = (params = {}) => service.get('/api/memory/items', { params })
export const getMemoryItem = (memoryId) => service.get(`/api/memory/items/${memoryId}`)

// Report tool logs
export const listReportToolLogs = (params = {}) => service.get('/api/report/tool-logs', { params })

// Traceable report
export const runTraceableReport = (payload) => service.post('/api/report/traceable', payload)
export const getTraceableReport = (reportId) => service.get(`/api/report/traceable/${reportId}`)

// Review
export const listReviewClaims = () => service.get('/api/review/claims')
export const evaluateClaim = (claim) => service.post('/api/review/evaluate', { claim })
