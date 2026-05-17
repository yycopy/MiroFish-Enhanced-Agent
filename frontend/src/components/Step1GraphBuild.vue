<template>
  <div class="workbench-panel">
    <IngestionStatusStrip :projectId="props.projectData?.project_id || ''" />
    <div class="scroll-container">
      <!-- Step 01: Ontology -->
      <div class="step-card" :class="{ 'active': currentPhase === 0, 'completed': currentPhase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">{{ $t('step1.ontologyGeneration') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 0" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 0" class="badge processing">{{ $t('step1.ontologyGenerating') }}</span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/graph/ontology/generate</p>
          <p class="description">
            {{ $t('step1.ontologyDesc') }}
          </p>

          <!-- Loading / Progress -->
          <div v-if="currentPhase === 0 && ontologyProgress" class="progress-section">
            <div class="spinner-sm"></div>
            <span>{{ ontologyProgress.message || $t('step1.analyzingDocs') }}</span>
          </div>

          <!-- Detail Overlay -->
          <div v-if="selectedOntologyItem" class="ontology-detail-overlay">
            <div class="detail-header">
               <div class="detail-title-group">
                  <span class="detail-type-badge">{{ selectedOntologyItem.itemType === 'entity' ? 'ENTITY' : 'RELATION' }}</span>
                  <span class="detail-name">{{ selectedOntologyItem.name }}</span>
               </div>
               <button class="close-btn" @click="selectedOntologyItem = null">×</button>
            </div>
            <div class="detail-body">
               <div class="detail-desc">{{ selectedOntologyItem.description }}</div>
               
               <!-- Attributes -->
               <div class="detail-section" v-if="selectedOntologyItem.attributes?.length">
                  <span class="section-label">ATTRIBUTES</span>
                  <div class="attr-list">
                     <div v-for="attr in selectedOntologyItem.attributes" :key="attr.name" class="attr-item">
                        <span class="attr-name">{{ attr.name }}</span>
                        <span class="attr-type">({{ attr.type }})</span>
                        <span class="attr-desc">{{ attr.description }}</span>
                     </div>
                  </div>
               </div>

               <!-- Examples (Entity) -->
               <div class="detail-section" v-if="selectedOntologyItem.examples?.length">
                  <span class="section-label">EXAMPLES</span>
                  <div class="example-list">
                     <span v-for="ex in selectedOntologyItem.examples" :key="ex" class="example-tag">{{ ex }}</span>
                  </div>
               </div>

               <!-- Source/Target (Relation) -->
               <div class="detail-section" v-if="selectedOntologyItem.source_targets?.length">
                  <span class="section-label">CONNECTIONS</span>
                  <div class="conn-list">
                     <div v-for="(conn, idx) in selectedOntologyItem.source_targets" :key="idx" class="conn-item">
                        <span class="conn-node">{{ conn.source }}</span>
                        <span class="conn-arrow">→</span>
                        <span class="conn-node">{{ conn.target }}</span>
                     </div>
                  </div>
               </div>
            </div>
          </div>

          <!-- Generated Entity Tags -->
          <div v-if="projectData?.ontology?.entity_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED ENTITY TYPES</span>
            <div class="tags-list">
              <span 
                v-for="entity in projectData.ontology.entity_types" 
                :key="entity.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(entity, 'entity')"
              >
                {{ entity.name }}
              </span>
            </div>
          </div>

          <!-- Generated Relation Tags -->
          <div v-if="projectData?.ontology?.edge_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED RELATION TYPES</span>
            <div class="tags-list">
              <span 
                v-for="rel in projectData.ontology.edge_types" 
                :key="rel.name" 
                class="entity-tag clickable"
                @click="selectOntologyItem(rel, 'relation')"
              >
                {{ rel.name }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Graph Build -->
      <div class="step-card" :class="{ 'active': currentPhase === 1, 'completed': currentPhase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">{{ $t('step1.graphRagBuild') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 1" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 1" class="badge processing">{{ buildProgress?.progress || 0 }}%</span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/graph/build</p>
          <p class="description">
            {{ $t('step1.graphRagDesc') }}
          </p>
          
          <!-- Stats Cards -->
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.nodes }}</span>
              <span class="stat-label">{{ $t('step1.entityNodes') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.edges }}</span>
              <span class="stat-label">{{ $t('step1.relationEdges') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.types }}</span>
              <span class="stat-label">{{ $t('step1.schemaTypes') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Import from Memory (moved from 04) -->
      <div class="step-card" :class="{ 'active': currentPhase >= 2 && importResult, 'completed': importResult?.success }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">{{ $t('step1.memoryImportTitle') }}</span>
          </div>
          <div class="step-status">
            <span v-if="importResult?.success" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="importingMemories" class="badge processing">{{ $t('step1.memoryImporting') }}</span>
            <span v-else class="badge pending">{{ $t('common.ready') }}</span>
          </div>
        </div>
        <div class="card-content">
          <p class="api-note">POST /api/graph-memory/import-to-graph/:graph_id</p>
          <p class="description">
            {{ $t('step1.memoryImportDesc') }}
          </p>
          <div class="import-form">
            <div class="import-row">
              <label class="import-label">{{ $t('step1.memoryKeywordFilter') }}</label>
              <input v-model="importForm.keyword" class="import-input" :placeholder="$t('step1.memoryKeywordPlaceholder')" :disabled="importingMemories" />
            </div>
            <div class="import-row">
              <label class="import-label">{{ $t('step1.memoryMinImportance') }}: {{ importForm.min_importance }}</label>
              <input type="range" v-model.number="importForm.min_importance" min="0" max="1" step="0.05" class="import-slider" :disabled="importingMemories" />
            </div>
            <div class="import-row">
              <label class="import-label">{{ $t('step1.memoryMaxItems') }}: {{ importForm.limit }}</label>
              <input type="range" v-model.number="importForm.limit" min="10" max="200" step="10" class="import-slider" :disabled="importingMemories" />
            </div>
            <button
              class="action-btn import-btn"
              :disabled="currentPhase < 2 || importingMemories"
              @click="handleImportMemories"
            >
              <span v-if="importingMemories" class="spinner-sm"></span>
              {{ importingMemories ? $t('step1.memoryImportingBtn') : $t('step1.memoryImportBtn') }}
            </button>
          </div>
          <div v-if="importResult" class="import-result" :class="importResult.success ? 'success' : 'error'">
            <span v-if="importResult.success">
              {{ $t('step1.memoryImportResult', { imported: importResult.imported_count || 0, failed: importResult.failed_count || 0 }) }}
            </span>
            <span v-else>{{ $t('step1.memoryImportError', { error: importResult.error }) }}</span>
          </div>
        </div>
      </div>

      <!-- Step 04: Timed Ingestion (new) -->
      <div class="step-card" :class="{ 'active': currentPhase >= 2 && ingestionStatus?.active, 'completed': ingestionStatus?.total_runs > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">04</span>
            <span class="step-title">{{ $t('step2.ingestionTitle') }}</span>
          </div>
          <div class="step-status">
            <span v-if="ingestionStatus?.active" class="badge processing">{{ $t('step2.ingestionRunning') }}</span>
            <span v-else-if="isStartingIngestion || isStoppingIngestion" class="badge processing">{{ $t('step2.ingestionBusy') }}</span>
            <span v-else class="badge pending">{{ $t('step2.ingestionReady') }}</span>
          </div>
        </div>
        <div class="card-content">
          <p class="api-note">POST /api/ingestion/project/:id/extract-keywords | start | stop</p>
          <p class="description">{{ $t('step2.ingestionDesc') }}</p>

          <!-- A: Keyword Extraction -->
          <div class="ingestion-section">
            <div class="ingestion-section-header">
              <span class="ingestion-section-title">{{ $t('step2.ingestionKeywordExtract') }}</span>
            </div>
            <button
              class="action-btn secondary small"
              :disabled="isExtractingKeywords || currentPhase < 2"
              @click="handleExtractKeywords"
            >
              <span v-if="isExtractingKeywords" class="spinner-sm"></span>
              {{ isExtractingKeywords ? $t('step2.ingestionExtracting') : $t('step2.ingestionExtractBtn') }}
            </button>
            <div v-if="keywords.length > 0" class="keywords-display">
              <span v-for="(kw, idx) in keywords" :key="idx" class="keyword-tag">
                {{ kw }}
                <button class="keyword-remove" @click="keywords.splice(idx, 1)">×</button>
              </span>
              <input
                v-model="newKeyword"
                class="keyword-input-inline"
                :placeholder="$t('step2.ingestionAddKeyword')"
                @keyup.enter="addKeyword"
              />
            </div>
            <div v-if="extractError" class="ingestion-error">{{ extractError }}</div>
          </div>

          <!-- B: Interval Config -->
          <div v-if="keywords.length > 0" class="ingestion-section">
            <div class="ingestion-section-header">
              <span class="ingestion-section-title">{{ $t('step2.ingestionInterval') }}</span>
            </div>
            <div class="interval-config">
              <input
                type="range"
                v-model.number="ingestionInterval"
                min="60"
                max="7200"
                step="60"
                class="import-slider"
                :disabled="ingestionStatus?.active"
              />
              <span class="interval-value">{{ formatInterval(ingestionInterval) }}</span>
            </div>
            <div class="ingestion-actions">
              <button
                class="action-btn primary small"
                :disabled="isStartingIngestion || ingestionStatus?.active"
                @click="handleStartIngestion"
              >
                <span v-if="isStartingIngestion" class="spinner-sm"></span>
                {{ isStartingIngestion ? $t('step2.ingestionStarting') : $t('step2.ingestionStartBtn') }}
              </button>
              <button
                class="action-btn secondary small"
                :disabled="isStoppingIngestion || !ingestionStatus?.active"
                @click="handleStopIngestion"
              >
                {{ isStoppingIngestion ? $t('step2.ingestionStopping') : $t('step2.ingestionStopBtn') }}
              </button>
            </div>
          </div>

          <!-- C: Status -->
          <div v-if="ingestionStatus" class="ingestion-section">
            <div class="ingestion-section-header">
              <span class="ingestion-section-title">{{ $t('step2.ingestionStatus') }}</span>
            </div>
            <div class="ingestion-status-grid">
              <div class="status-item">
                <span class="status-label">{{ $t('step2.ingestionStateLabel') }}</span>
                <span class="status-value" :class="ingestionStatus.active ? 'active' : 'inactive'">
                  {{ ingestionStatus.active ? $t('step2.ingestionStateCollecting') : $t('step2.ingestionStateIdle') }}
                </span>
              </div>
              <div class="status-item">
                <span class="status-label">{{ $t('step2.ingestionKeywordsLabel') }}</span>
                <span class="status-value mono">{{ (ingestionStatus.keywords || []).join(', ') || '-' }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">{{ $t('step2.ingestionIntervalLabel') }}</span>
                <span class="status-value mono">{{ formatInterval(ingestionStatus.interval_seconds) }}</span>
              </div>
              <div class="status-item">
                <span class="status-label">{{ $t('step2.ingestionTotalRunsLabel') }}</span>
                <span class="status-value mono">{{ ingestionStatus.total_runs || 0 }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 05: Build Complete (moved from 03) -->
      <div class="step-card" :class="{ 'active': currentPhase === 2, 'completed': currentPhase > 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">05</span>
            <span class="step-title">{{ $t('step1.buildComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 2" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 2" class="badge accent">{{ $t('step1.inProgress') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">{{ $t('step1.buildCompleteDesc') }}</p>
          <button
            class="action-btn"
            :disabled="currentPhase < 2 || creatingSimulation"
            @click="handleEnterEnvSetup"
          >
            <span v-if="creatingSimulation" class="spinner-sm"></span>
            {{ creatingSimulation ? $t('step1.creating') : $t('step1.enterEnvSetup') + ' ➝' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SYSTEM DASHBOARD</span>
        <span class="log-id">{{ projectData?.project_id || 'NO_PROJECT' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createSimulation, extractProjectKeywords, startProjectIngestion, stopProjectIngestion, getProjectIngestionStatus } from '../api/simulation'
import { importMemoriesToGraph } from '../api/graph'
import IngestionStatusStrip from './IngestionStatusStrip.vue'

const router = useRouter()
const { t } = useI18n()

const props = defineProps({
  currentPhase: { type: Number, default: 0 },
  projectData: Object,
  ontologyProgress: Object,
  buildProgress: Object,
  graphData: Object,
  systemLogs: { type: Array, default: () => [] }
})

defineEmits(['next-step'])

const selectedOntologyItem = ref(null)
const logContent = ref(null)
const creatingSimulation = ref(false)

// 记忆导入状态
const importingMemories = ref(false)
const importResult = ref(null)
const importForm = ref({
  keyword: '',
  limit: 50,
  min_importance: 0.3
})

const handleImportMemories = async () => {
  if (!props.projectData?.graph_id) return
  importingMemories.value = true
  importResult.value = null
  try {
    const res = await importMemoriesToGraph(props.projectData.graph_id, {
      keyword: importForm.value.keyword || undefined,
      limit: importForm.value.limit,
      min_importance: importForm.value.min_importance
    })
    importResult.value = res.success ? res : { success: false, error: res.error || 'Unknown error' }
  } catch (err) {
    importResult.value = { success: false, error: err.message }
  } finally {
    importingMemories.value = false
  }
}

// 定时采集信息状态
const keywords = ref([])
const newKeyword = ref('')
const isExtractingKeywords = ref(false)
const extractError = ref('')
const ingestionInterval = ref(1800)
const ingestionStatus = ref(null)
const isStartingIngestion = ref(false)
const isStoppingIngestion = ref(false)
let ingestionPollTimer = null

const addKeyword = () => {
  const kw = newKeyword.value.trim()
  if (kw && !keywords.value.includes(kw)) {
    keywords.value.push(kw)
  }
  newKeyword.value = ''
}

const formatInterval = (seconds) => {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`
  return `${(seconds / 3600).toFixed(1)}h`
}

const handleExtractKeywords = async () => {
  if (!props.projectData?.project_id) return
  isExtractingKeywords.value = true
  extractError.value = ''
  try {
    const res = await extractProjectKeywords(props.projectData.project_id, {
      simulation_requirement: props.projectData.simulation_requirement || ''
    })
    if (res.success && res.keywords) {
      keywords.value = res.keywords
    } else {
      extractError.value = res.error || 'Extraction failed'
    }
  } catch (err) {
    extractError.value = err.message || 'Extraction error'
  } finally {
    isExtractingKeywords.value = false
  }
}

const handleStartIngestion = async () => {
  if (!props.projectData?.project_id || keywords.value.length === 0) return
  isStartingIngestion.value = true
  try {
    const res = await startProjectIngestion(props.projectData.project_id, {
      keywords: keywords.value,
      interval_seconds: ingestionInterval.value
    })
    if (res.success) {
      ingestionStatus.value = { active: true, keywords: keywords.value, interval_seconds: ingestionInterval.value, total_runs: 0 }
      startIngestionPolling()
    }
  } catch (err) {
    console.error('Start ingestion failed:', err)
  } finally {
    isStartingIngestion.value = false
  }
}

const handleStopIngestion = async () => {
  if (!props.projectData?.project_id) return
  isStoppingIngestion.value = true
  try {
    const res = await stopProjectIngestion(props.projectData.project_id)
    if (res.success) {
      ingestionStatus.value = { ...ingestionStatus.value, active: false }
      stopIngestionPolling()
    }
  } catch (err) {
    console.error('Stop ingestion failed:', err)
  } finally {
    isStoppingIngestion.value = false
  }
}

const startIngestionPolling = () => {
  if (ingestionPollTimer) return
  ingestionPollTimer = setInterval(pollIngestionStatus, 30000)
}

const stopIngestionPolling = () => {
  if (ingestionPollTimer) {
    clearInterval(ingestionPollTimer)
    ingestionPollTimer = null
  }
}

const pollIngestionStatus = async () => {
  if (!props.projectData?.project_id) return
  try {
    const res = await getProjectIngestionStatus(props.projectData.project_id)
    if (res.success) {
      ingestionStatus.value = res
    }
  } catch (err) {
    // silent poll failure
  }
}

// 进入环境搭建 - 创建 simulation 并跳转
const handleEnterEnvSetup = async () => {
  if (!props.projectData?.project_id || !props.projectData?.graph_id) {
    console.error('缺少项目或图谱信息')
    return
  }
  
  creatingSimulation.value = true
  
  try {
    const res = await createSimulation({
      project_id: props.projectData.project_id,
      graph_id: props.projectData.graph_id,
      enable_twitter: true,
      enable_reddit: true
    })
    
    if (res.success && res.data?.simulation_id) {
      // 跳转到 simulation 页面
      router.push({
        name: 'Simulation',
        params: { simulationId: res.data.simulation_id }
      })
    } else {
      console.error('创建模拟失败:', res.error)
      alert(t('step1.createSimulationFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    console.error('创建模拟异常:', err)
    alert(t('step1.createSimulationException', { error: err.message }))
  } finally {
    creatingSimulation.value = false
  }
}

const selectOntologyItem = (item, type) => {
  selectedOntologyItem.value = { ...item, itemType: type }
}

const graphStats = computed(() => {
  const nodes = props.graphData?.node_count || props.graphData?.nodes?.length || 0
  const edges = props.graphData?.edge_count || props.graphData?.edges?.length || 0
  const types = props.projectData?.ontology?.entity_types?.length || 0
  return { nodes, edges, types }
})

const formatDate = (dateStr) => {
  if (!dateStr) return '--:--:--'
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + d.getMilliseconds()
}

// Auto-scroll logs
watch(() => props.systemLogs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

onMounted(() => {
  if (props.currentPhase >= 2) {
    pollIngestionStatus()
  }
})

onUnmounted(() => {
  stopIngestionPolling()
})
</script>

<style scoped>
.workbench-panel {
  height: 100%;
  background-color: #FAFAFA;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step-card {
  background: #FFF;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid #EAEAEA;
  transition: all 0.3s ease;
  position: relative; /* For absolute overlay */
}

.step-card.active {
  border-color: #FF5722;
  box-shadow: 0 4px 12px rgba(255, 87, 34, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 700;
  color: #000;
}

.step-card.active .step-num,
.step-card.completed .step-num {
  color: #000;
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.badge {
  font-size: 10px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.success { background: #E8F5E9; color: #2E7D32; }
.badge.processing { background: #FF5722; color: #FFF; }
.badge.accent { background: #FF5722; color: #FFF; }
.badge.pending { background: #F5F5F5; color: #999; }

.api-note {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #999;
  margin-bottom: 8px;
}

.description {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 16px;
}

/* Step 01 Tags */
.tags-container {
  margin-top: 12px;
  transition: opacity 0.3s;
}

.tags-container.dimmed {
    opacity: 0.3;
    pointer-events: none;
}

.tag-label {
  display: block;
  font-size: 10px;
  color: #AAA;
  margin-bottom: 8px;
  font-weight: 600;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  background: #F5F5F5;
  border: 1px solid #EEE;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  color: #333;
  font-family: 'JetBrains Mono', monospace;
  transition: all 0.2s;
}

.entity-tag.clickable {
    cursor: pointer;
}

.entity-tag.clickable:hover {
    background: #E0E0E0;
    border-color: #CCC;
}

/* Ontology Detail Overlay */
.ontology-detail-overlay {
    position: absolute;
    top: 60px; /* Below header roughly */
    left: 20px;
    right: 20px;
    bottom: 20px;
    background: rgba(255, 255, 255, 0.98);
    backdrop-filter: blur(4px);
    z-index: 10;
    border: 1px solid #EAEAEA;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #EAEAEA;
    background: #FAFAFA;
}

.detail-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-type-badge {
    font-size: 9px;
    font-weight: 700;
    color: #FFF;
    background: #000;
    padding: 2px 6px;
    border-radius: 2px;
    text-transform: uppercase;
}

.detail-name {
    font-size: 14px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

.close-btn {
    background: none;
    border: none;
    font-size: 18px;
    color: #999;
    cursor: pointer;
    line-height: 1;
}

.close-btn:hover {
    color: #333;
}

.detail-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}

.detail-desc {
    font-size: 12px;
    color: #444;
    line-height: 1.5;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px dashed #EAEAEA;
}

.detail-section {
    margin-bottom: 16px;
}

.section-label {
    display: block;
    font-size: 10px;
    font-weight: 600;
    color: #AAA;
    margin-bottom: 8px;
}

.attr-list, .conn-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.attr-item {
    font-size: 11px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: baseline;
    padding: 4px;
    background: #F9F9F9;
    border-radius: 4px;
}

.attr-name {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    color: #000;
}

.attr-type {
    color: #999;
    font-size: 10px;
}

.attr-desc {
    color: #555;
    flex: 1;
    min-width: 150px;
}

.example-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.example-tag {
    font-size: 11px;
    background: #FFF;
    border: 1px solid #E0E0E0;
    padding: 3px 8px;
    border-radius: 12px;
    color: #555;
}

.conn-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    padding: 6px;
    background: #F5F5F5;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
}

.conn-node {
    font-weight: 600;
    color: #333;
}

.conn-arrow {
    color: #BBB;
}

/* Step 02 Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  background: #F9F9F9;
  padding: 16px;
  border-radius: 6px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #000;
  font-family: 'JetBrains Mono', monospace;
}

.stat-label {
  font-size: 9px;
  color: #999;
  text-transform: uppercase;
  margin-top: 4px;
  display: block;
}

/* Step 03 Button */
.action-btn {
  width: 100%;
  background: #000;
  color: #FFF;
  border: none;
  padding: 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.action-btn:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn:disabled {
  background: #CCC;
  cursor: not-allowed;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #FF5722;
  margin-bottom: 12px;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid #FFCCBC;
  border-top-color: #FF5722;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

/* Import Form */
.import-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.import-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.import-label {
  font-size: 11px;
  color: #64748B;
  font-weight: 500;
}

.import-input {
  padding: 8px 12px;
  border: 1px solid #E5E5E5;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s;
}

.import-input:focus {
  border-color: #000;
}

.import-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  background: #E2E8F0;
  border-radius: 2px;
  outline: none;
}

.import-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #000;
  cursor: pointer;
}

.import-btn {
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.import-result {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
}

.import-result.success {
  background: #E8F5E9;
  color: #2E7D32;
}

.import-result.error {
  background: #FFEBEE;
  color: #C62828;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Ingestion Section */
.ingestion-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #F0F0F0;
}

.ingestion-section-header {
  margin-bottom: 8px;
}

.ingestion-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  text-transform: uppercase;
}

.action-btn.secondary {
  background: #FFF;
  color: #333;
  border: 1px solid #DDD;
}

.action-btn.secondary:hover:not(:disabled) {
  background: #F5F5F5;
}

.action-btn.small {
  padding: 8px 14px;
  font-size: 11px;
  width: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.action-btn.primary {
  background: #000;
  color: #FFF;
  border: none;
}

.keywords-display {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
}

.keyword-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #F0F0F0;
  border: 1px solid #E0E0E0;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 11px;
  color: #333;
}

.keyword-remove {
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
}

.keyword-remove:hover {
  color: #FF5722;
}

.keyword-input-inline {
  border: 1px dashed #DDD;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 11px;
  outline: none;
  width: 100px;
  transition: border-color 0.2s;
}

.keyword-input-inline:focus {
  border-color: #FF5722;
}

.ingestion-error {
  margin-top: 6px;
  font-size: 11px;
  color: #C62828;
}

.interval-config {
  display: flex;
  align-items: center;
  gap: 12px;
}

.interval-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #333;
  min-width: 50px;
}

.ingestion-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.ingestion-status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: #F9F9F9;
  padding: 10px;
  border-radius: 4px;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-label {
  font-size: 9px;
  color: #999;
  text-transform: uppercase;
}

.status-value {
  font-size: 12px;
  font-weight: 600;
}

.status-value.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

.status-value.active {
  color: #2E7D32;
}

.status-value.inactive {
  color: #999;
}

/* System Logs */
.system-logs {
  background: #000;
  color: #DDD;
  padding: 16px;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid #222;
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #333;
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: #888;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 80px; /* Approx 4 lines visible */
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: #666;
  min-width: 75px;
}

.log-msg {
  color: #CCC;
  word-break: break-all;
}
</style>
