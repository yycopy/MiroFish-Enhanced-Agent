<template>
  <div class="review-panel">
    <!-- Phase 1: Report Claim Extraction -->
    <div v-if="phase === 'extracting'" class="phase-container">
      <div class="phase-header">
        <div class="phase-icon extracting">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
          </svg>
        </div>
        <div class="phase-text">
          <h2>{{ $t('step5.extractingClaims') }}</h2>
          <p>{{ $t('step5.extractingDesc') }}</p>
        </div>
      </div>
      <div class="extraction-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: extractionProgress + '%' }"></div>
        </div>
        <span class="progress-text">{{ extractionProgress }}%</span>
      </div>
    </div>

    <!-- Phase 2: Review Claims -->
    <div v-else-if="phase === 'reviewing'" class="phase-container">
      <div class="claims-header">
        <h2>{{ $t('step5.claimsReview') }}</h2>
        <div class="claims-header-right">
          <span class="claim-count">{{ reviewedCount }}/{{ claims.length }} {{ $t('step5.reviewed') }}</span>
          <button class="review-all-btn" @click="reviewAllClaims" :disabled="isReviewingAll">
            <svg v-if="isReviewingAll" class="spin" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
            </svg>
            <span>{{ isReviewingAll ? $t('step5.reviewingAll') : $t('step5.reviewAll') }}</span>
          </button>
        </div>
      </div>

      <!-- Review Progress Bar -->
      <div v-if="isReviewingAll" class="review-progress-bar">
        <div class="review-progress-info">
          <span class="review-progress-text">{{ $t('step5.reviewingClaimProgress', { current: reviewingClaimNum, total: claims.length }) }}</span>
          <span class="review-progress-percent">{{ reviewProgress }}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill review-fill" :style="{ width: reviewProgress + '%' }"></div>
        </div>
      </div>

      <!-- Claims List -->
      <div class="claims-list">
        <div
          v-for="(claim, idx) in claims"
          :key="idx"
          class="claim-card"
          :class="{ 'is-active': activeClaimIndex === idx, 'is-reviewed': claim.reviewed }"
          @click="activeClaimIndex = idx"
        >
          <div class="claim-header">
            <span class="claim-number">{{ String(idx + 1).padStart(2, '0') }}</span>
            <span class="claim-confidence" :class="getConfidenceClass(claim.confidence)">
              {{ claim.confidence != null ? claim.confidence + '%' : '—' }}
            </span>
          </div>
          <p class="claim-text">{{ claim.text }}</p>
          <div class="claim-meta" v-if="claim.category">
            <span class="claim-category">{{ claim.category }}</span>
            <span v-if="claim.reviewed" class="claim-status reviewed">{{ $t('step5.reviewed') }}</span>
          </div>
        </div>
      </div>

      <!-- Active Claim Review Panel -->
      <div v-if="activeClaim" class="review-detail-panel">
        <div class="detail-header">
          <h3>{{ $t('step5.reviewDetail') }}</h3>
          <button class="run-review-btn" @click="runReview(activeClaimIndex)" :disabled="activeClaim.reviewing">
            <svg v-if="!activeClaim.reviewing" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            <svg v-else class="spin" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
            </svg>
            <span>{{ activeClaim.reviewing ? $t('step5.reviewing') : $t('step5.startReview') }}</span>
          </button>
        </div>

        <!-- 5-Role Review Grid -->
        <div v-if="activeClaim.reviews" class="review-grid">
          <div
            v-for="role in reviewRoles"
            :key="role.id"
            class="role-card"
            :class="role.id"
          >
            <div class="role-header">
              <div class="role-icon" :class="role.id" v-html="role.icon"></div>
              <span class="role-name">{{ $t('step5.roles.' + role.id) }}</span>
            </div>
            <div class="role-content">
              <p v-if="activeClaim.reviews[role.id]">{{ activeClaim.reviews[role.id].analysis }}</p>
              <div v-else-if="activeClaim.reviewing" class="role-loading">
                <div class="loading-dots"><span></span><span></span><span></span></div>
              </div>
              <p v-else class="role-pending">{{ $t('step5.pendingReview') }}</p>
            </div>
            <div v-if="activeClaim.reviews[role.id]?.score != null" class="role-score">
              <span class="score-label">{{ $t('step5.score') }}</span>
              <div class="score-bar">
                <div class="score-fill" :class="role.id" :style="{ width: activeClaim.reviews[role.id].score + '%' }"></div>
              </div>
              <span class="score-value">{{ activeClaim.reviews[role.id].score }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Phase 2.5: Review Complete - Show Summary + Generate Button -->
    <div v-else-if="phase === 'reviewed'" class="phase-container">
      <div class="reviewed-header">
        <div class="phase-icon reviewed">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        </div>
        <div class="phase-text">
          <h2>{{ $t('step5.reviewComplete') }}</h2>
          <p>{{ $t('step5.reviewCompleteDesc', { count: claims.length }) }}</p>
        </div>
      </div>

      <!-- Confidence Overview -->
      <div class="reviewed-confidence-overview">
        <div class="confidence-mini-ring">
          <svg viewBox="0 0 80 80">
            <circle cx="40" cy="40" r="34" fill="none" stroke="#E5E7EB" stroke-width="6"/>
            <circle cx="40" cy="40" r="34" fill="none" :stroke="reviewedConfidenceColor" stroke-width="6"
              stroke-linecap="round" :stroke-dasharray="reviewedConfidenceDash" transform="rotate(-90 40 40)"/>
          </svg>
          <div class="confidence-mini-value">
            <span>{{ reviewedOverallConfidence }}</span>
            <span class="conf-mini-unit">%</span>
          </div>
        </div>
        <div class="confidence-mini-meta">
          <span class="conf-mini-label">{{ $t('step5.avgConfidenceAfterReview') }}</span>
          <span class="conf-mini-desc">{{ reviewedConfidenceDesc }}</span>
        </div>
      </div>

      <!-- Reviewed Claims Summary -->
      <div class="reviewed-claims-summary">
        <div v-for="(claim, idx) in claims" :key="idx" class="reviewed-claim-item">
          <div class="reviewed-claim-left">
            <span class="reviewed-claim-num">{{ String(idx + 1).padStart(2, '0') }}</span>
            <span class="reviewed-claim-text">{{ claim.text }}</span>
          </div>
          <span class="reviewed-claim-confidence" :class="getConfidenceClass(claim.confidence)">
            {{ claim.confidence != null ? claim.confidence + '%' : '—' }}
          </span>
        </div>
      </div>

      <!-- Generate Button -->
      <div class="reviewed-actions">
        <button class="nav-btn secondary" @click="phase = 'reviewing'">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="1 4 1 10 7 10"></polyline>
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
          </svg>
          <span>{{ $t('step5.backToReview') }}</span>
        </button>
        <button class="generate-report-btn" @click="generateTraceableReport" :disabled="generatingReport">
          <svg v-if="generatingReport" class="spin" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
          </svg>
          <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            <path d="M9 12l2 2 4-4"></path>
          </svg>
          <span>{{ generatingReport ? $t('step5.generating') : $t('step5.generateTraceableBtn') }}</span>
        </button>
      </div>
    </div>

    <!-- Phase 3: Generate Traceable Report -->
    <div v-else-if="phase === 'generating'" class="phase-container">
      <div class="phase-header">
        <div class="phase-icon generating">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          </svg>
        </div>
        <div class="phase-text">
          <h2>{{ $t('step5.generatingReport') }}</h2>
          <p>{{ $t('step5.generatingDesc') }}</p>
        </div>
      </div>
      <div class="agent-steps">
        <div v-for="(step, idx) in agentSteps" :key="idx" class="agent-step" :class="{ done: step.done, active: step.active }">
          <div class="step-dot"></div>
          <span class="step-label">{{ step.label }}</span>
        </div>
      </div>
    </div>

    <!-- Phase 4: Traceable Report Display -->
    <div v-else-if="phase === 'report'" class="phase-container report-phase">
      <div class="report-wrapper">
        <!-- Report Header -->
        <div class="traceable-header">
          <div class="report-badge">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <span>{{ $t('step5.traceableReport') }}</span>
          </div>
          <h1 class="traceable-title">{{ $t('step5.enhReportTitle') }}</h1>
          <div class="confidence-display">
            <div class="confidence-ring">
              <svg viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="52" fill="none" stroke="#E5E7EB" stroke-width="8"/>
                <circle cx="60" cy="60" r="52" fill="none" :stroke="confidenceColor" stroke-width="8"
                  stroke-linecap="round" :stroke-dasharray="confidenceDash" transform="rotate(-90 60 60)"/>
              </svg>
              <div class="confidence-value">
                <span class="conf-num">{{ overallConfidence }}</span>
                <span class="conf-unit">%</span>
              </div>
            </div>
            <div class="confidence-meta">
              <span class="conf-label">{{ $t('step5.overallConfidence') }}</span>
              <span class="conf-desc">{{ confidenceDescription }}</span>
            </div>
          </div>
        </div>

        <!-- Question -->
        <div v-if="traceableReport.question" class="report-section question-section">
          <div class="section-label">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
            <span>{{ $t('step5.question') }}</span>
          </div>
          <p class="question-text">{{ traceableReport.question }}</p>
        </div>

        <!-- Evidence Chain -->
        <div v-if="traceableReport.evidence_chain?.length" class="report-section evidence-section">
          <div class="section-label">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
            </svg>
            <span>{{ $t('step5.evidenceChain') }}</span>
            <span class="badge-count">{{ traceableReport.evidence_chain.length }}</span>
          </div>
          <div class="evidence-chain">
            <div v-for="(ev, idx) in traceableReport.evidence_chain" :key="idx" class="evidence-item">
              <div class="ev-marker">
                <span class="ev-id">{{ ev.id || ('EV-' + String(idx+1).padStart(3,'0')) }}</span>
                <div class="ev-line" v-if="idx < traceableReport.evidence_chain.length - 1"></div>
              </div>
              <div class="ev-body">
                <p class="ev-text">{{ ev.content || ev.text || ev.description }}</p>
                <div class="ev-meta">
                  <span v-if="ev.source" class="ev-source">{{ ev.source }}</span>
                  <span v-if="ev.reliability != null" class="ev-reliability" :class="getReliabilityClass(ev.reliability)">
                    {{ $t('step5.reliability') }}: {{ ev.reliability }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Review Summary -->
        <div v-if="reviewSummary.length" class="report-section review-summary-section">
          <div class="section-label">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
            <span>{{ $t('step5.reviewSummary') }}</span>
          </div>
          <div class="review-summary-grid">
            <div v-for="role in reviewRoles" :key="role.id" class="summary-role-card" :class="role.id">
              <div class="summary-role-header">
                <span class="summary-role-icon" v-html="role.icon"></span>
                <span class="summary-role-name">{{ $t('step5.roles.' + role.id) }}</span>
              </div>
              <p class="summary-role-text">{{ getRoleSummary(role.id) }}</p>
            </div>
          </div>
        </div>

        <!-- Report Body -->
        <div v-if="traceableReport.content || traceableReport.report_content" class="report-section body-section">
          <div class="section-label">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <span>{{ $t('step5.reportContent') }}</span>
          </div>
          <div class="report-body" v-html="renderReport(traceableReport.content || traceableReport.report_content)"></div>
        </div>
      </div>
    </div>

    <!-- Initial State -->
    <div v-else class="phase-container init-phase">
      <!-- Original Report Preview -->
      <div v-if="originalReport" class="original-report-section">
        <div class="section-label">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span>{{ $t('step5.originalReport') }}</span>
        </div>
        <div class="original-report-content" v-html="renderReport(originalReport)"></div>
      </div>
      <div v-else-if="originalReportLoading" class="original-report-loading">
        <div class="loading-icon">
          <svg class="spin" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
          </svg>
        </div>
        <span>{{ $t('step5.loadingOriginalReport') }}</span>
      </div>
      <div class="init-content">
        <div class="init-icon">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            <path d="M9 12l2 2 4-4"></path>
          </svg>
        </div>
        <h2>{{ $t('step5.reviewTitle') }}</h2>
        <p>{{ $t('step5.reviewDesc') }}</p>
        <button class="start-btn" @click="startExtraction" :disabled="loading">
          <svg v-if="loading" class="spin" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
          </svg>
          <span>{{ loading ? $t('common.processing') : $t('step5.startReviewBtn') }}</span>
        </button>
      </div>
    </div>

    <!-- Bottom Navigation -->
    <div v-if="phase === 'report'" class="bottom-nav">
      <button class="nav-btn secondary" @click="resetReview">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="1 4 1 10 7 10"></polyline>
          <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
        </svg>
        <span>{{ $t('step5.reReview') }}</span>
      </button>
      <button class="nav-btn primary" @click="goToInteraction">
        <span>{{ $t('step5.goToInteraction') }}</span>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="5" y1="12" x2="19" y2="12"></line>
          <polyline points="12 5 19 12 12 19"></polyline>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listReviewClaims, evaluateClaim, runTraceableReport, getTraceableReport, getReport } from '../api/report'

const router = useRouter()
const { t } = useI18n()

const props = defineProps({
  reportId: String,
  simulationId: String
})

const emit = defineEmits(['add-log', 'update-status'])

// Phases: init -> extracting -> reviewing -> generating -> report
const phase = ref('init')
const loading = ref(false)
const extractionProgress = ref(0)

// Original Step4 report content
const originalReport = ref(null)
const originalReportLoading = ref(false)

// Claims
const claims = ref([])
const activeClaimIndex = ref(0)
const activeClaim = computed(() => claims.value[activeClaimIndex.value] || null)
const reviewedCount = computed(() => claims.value.filter(c => c.reviewed).length)
const isReviewingAll = ref(false)
const reviewingClaimNum = ref(0)
const generatingReport = ref(false)
const reviewProgress = computed(() => {
  if (claims.value.length === 0) return 0
  return Math.round((reviewedCount.value / claims.value.length) * 100)
})

// Reviewed phase computed
const reviewedOverallConfidence = computed(() => {
  const reviewed = claims.value.filter(c => c.reviewed && c.confidence != null)
  if (reviewed.length === 0) return 0
  return Math.round(reviewed.reduce((sum, c) => sum + c.confidence, 0) / reviewed.length)
})
const reviewedConfidenceColor = computed(() => {
  if (reviewedOverallConfidence.value >= 80) return '#10B981'
  if (reviewedOverallConfidence.value >= 60) return '#F59E0B'
  return '#EF4444'
})
const reviewedConfidenceDash = computed(() => {
  const circumference = 2 * Math.PI * 34
  const filled = (reviewedOverallConfidence.value / 100) * circumference
  return `${filled} ${circumference - filled}`
})
const reviewedConfidenceDesc = computed(() => {
  if (reviewedOverallConfidence.value >= 80) return t('step5.highConfidence')
  if (reviewedOverallConfidence.value >= 60) return t('step5.mediumConfidence')
  return t('step5.lowConfidence')
})

// Review roles
const reviewRoles = [
  { id: 'fact_checker', icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>' },
  { id: 'supporter', icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>' },
  { id: 'opponent', icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path></svg>' },
  { id: 'risk_reviewer', icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>' },
  { id: 'evidence_organizer', icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>' }
]

// Traceable report
const traceableReport = ref({})
const overallConfidence = ref(0)
const agentSteps = ref([
  { label: 'Memory Retrieval', done: false, active: false },
  { label: 'Graph Search', done: false, active: false },
  { label: 'Active Search', done: false, active: false },
  { label: 'Agent Interview', done: false, active: false },
  { label: 'Review Integration', done: false, active: false },
  { label: 'Report Generation', done: false, active: false }
])

const confidenceColor = computed(() => {
  if (overallConfidence.value >= 80) return '#10B981'
  if (overallConfidence.value >= 60) return '#F59E0B'
  return '#EF4444'
})

const confidenceDash = computed(() => {
  const circumference = 2 * Math.PI * 52
  const filled = (overallConfidence.value / 100) * circumference
  return `${filled} ${circumference - filled}`
})

const confidenceDescription = computed(() => {
  if (overallConfidence.value >= 80) return t('step5.highConfidence')
  if (overallConfidence.value >= 60) return t('step5.mediumConfidence')
  return t('step5.lowConfidence')
})

const reviewSummary = computed(() => {
  if (!traceableReport.value.review_results) return []
  return traceableReport.value.review_results
})

// Methods
const getConfidenceClass = (confidence) => {
  if (confidence == null) return 'unknown'
  if (confidence >= 80) return 'high'
  if (confidence >= 60) return 'medium'
  return 'low'
}

const getReliabilityClass = (reliability) => {
  if (reliability >= 80) return 'high'
  if (reliability >= 60) return 'medium'
  return 'low'
}

const getRoleSummary = (roleId) => {
  const results = traceableReport.value.review_results
  if (!results) return ''
  if (Array.isArray(results)) {
    const found = results.find(r => r.role === roleId)
    return found?.summary || found?.analysis || ''
  }
  return results[roleId]?.summary || results[roleId]?.analysis || ''
}

const startExtraction = async () => {
  loading.value = true
  emit('add-log', t('step5.extractingClaims'))

  try {
    const res = await listReviewClaims(props.reportId)
    if (res.success && res.data?.claims) {
      claims.value = res.data.claims.map(c => ({
        ...c,
        reviewed: false,
        reviewing: false,
        reviews: null
      }))
      phase.value = 'reviewing'
      emit('add-log', t('step5.claimsExtracted', { count: claims.value.length }))
    } else {
      // Fallback: generate sample claims from report
      claims.value = generateSampleClaims()
      phase.value = 'reviewing'
    }
  } catch (err) {
    emit('add-log', t('step5.extractionFailed', { error: err.message }))
    claims.value = generateSampleClaims()
    phase.value = 'reviewing'
  } finally {
    loading.value = false
  }
}

const generateSampleClaims = () => {
  return [
    { text: t('step5.sampleClaim1'), category: 'prediction', confidence: null, reviewed: false, reviewing: false, reviews: null },
    { text: t('step5.sampleClaim2'), category: 'analysis', confidence: null, reviewed: false, reviewing: false, reviews: null },
    { text: t('step5.sampleClaim3'), category: 'conclusion', confidence: null, reviewed: false, reviewing: false, reviews: null }
  ]
}

const runReview = async (claimIdx) => {
  const claim = claims.value[claimIdx]
  claim.reviewing = true
  emit('add-log', t('step5.reviewingClaim', { num: claimIdx + 1 }))

  try {
    const res = await evaluateClaim({
      claim: claim.text,
      evidence_context: claim.evidence || '',
      report_id: props.reportId
    })

    if (res.success && res.data) {
      claim.reviews = res.data.reviews || res.data
      claim.confidence = res.data.confidence || calculateConfidence(claim.reviews)
      claim.reviewed = true
      emit('add-log', t('step5.claimReviewed', { num: claimIdx + 1, confidence: claim.confidence }))
    }
  } catch (err) {
    emit('add-log', t('step5.reviewFailed', { error: err.message }))
  } finally {
    claim.reviewing = false
  }
}

const reviewAllClaims = async () => {
  isReviewingAll.value = true
  emit('add-log', t('step5.reviewingAllStart', { count: claims.value.length }))

  for (let i = 0; i < claims.value.length; i++) {
    if (claims.value[i].reviewed) continue
    reviewingClaimNum.value = i + 1
    activeClaimIndex.value = i
    await runReview(i)
  }

  isReviewingAll.value = false
  reviewingClaimNum.value = 0
  emit('add-log', t('step5.reviewingAllDone'))

  // Move to reviewed phase
  phase.value = 'reviewed'
}

const calculateConfidence = (reviews) => {
  if (!reviews) return 0
  const scores = Object.values(reviews)
    .map(r => r?.score)
    .filter(s => s != null)
  if (scores.length === 0) return 0
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
}

const generateTraceableReport = async () => {
  generatingReport.value = true
  emit('add-log', t('step5.generatingReport'))

  // Small delay to show loading state before transitioning
  await new Promise(resolve => setTimeout(resolve, 300))

  phase.value = 'generating'

  // Animate agent steps
  for (let i = 0; i < agentSteps.value.length; i++) {
    agentSteps.value[i].active = true
    await new Promise(resolve => setTimeout(resolve, 800))
    agentSteps.value[i].active = false
    agentSteps.value[i].done = true
  }

  try {
    const res = await runTraceableReport({
      report_id: props.reportId,
      simulation_id: props.simulationId,
      claims: claims.value.map(c => ({ text: c.text, confidence: c.confidence, reviews: c.reviews }))
    })

    if (res.success && res.data) {
      traceableReport.value = res.data
      overallConfidence.value = res.data.confidence || res.data.overall_confidence || calculateOverallConfidence()
      phase.value = 'report'
      emit('update-status', 'completed')
      emit('add-log', t('step5.reportGenerated'))
    }
  } catch (err) {
    emit('add-log', t('step5.reportFailed', { error: err.message }))
    // Show a basic report even on error
    overallConfidence.value = calculateOverallConfidence()
    traceableReport.value = {
      question: props.simulationId,
      content: t('step5.reportFallback'),
      confidence: overallConfidence.value
    }
    phase.value = 'report'
  }
}

const calculateOverallConfidence = () => {
  const reviewed = claims.value.filter(c => c.reviewed && c.confidence != null)
  if (reviewed.length === 0) return 0
  return Math.round(reviewed.reduce((sum, c) => sum + c.confidence, 0) / reviewed.length)
}

const renderReport = (content) => {
  if (!content) return ''
  let html = content
  // Basic markdown rendering
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/`(.+?)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/\[(ev_\d+)\]/g, '<span class="ev-ref">$1</span>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  return '<p>' + html + '</p>'
}

const resetReview = () => {
  phase.value = 'init'
  claims.value = []
  activeClaimIndex.value = 0
  traceableReport.value = {}
  overallConfidence.value = 0
  isReviewingAll.value = false
  reviewingClaimNum.value = 0
  generatingReport.value = false
  agentSteps.value.forEach(s => { s.done = false; s.active = false })
}

const goToInteraction = () => {
  router.push({ name: 'Interaction', params: { reportId: props.reportId } })
}

const loadOriginalReport = async () => {
  if (!props.reportId) return
  originalReportLoading.value = true
  try {
    const res = await getReport(props.reportId)
    if (res.success && res.data) {
      const data = res.data
      // Collect all section content from the original report
      const sections = data.sections || data.outline?.sections || []
      if (sections.length > 0) {
        originalReport.value = sections.map(s => `## ${s.title}\n\n${s.content || ''}`).join('\n\n')
      } else if (data.content || data.markdown) {
        originalReport.value = data.content || data.markdown
      }
      emit('add-log', t('step5.originalReportLoaded'))
    }
  } catch (err) {
    emit('add-log', t('step5.originalReportFailed', { error: err.message }))
  } finally {
    originalReportLoading.value = false
  }
}

onMounted(() => {
  // Load the original Step4 report for reference
  loadOriginalReport()
  if (props.reportId) {
    emit('add-log', t('step5.reviewReady'))
  }
})
</script>

<style scoped>
.review-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #F8FAFC;
  overflow-y: auto;
  font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif;
}

/* ========== Phase Container ========== */
.phase-container {
  flex: 1;
  padding: 32px;
  display: flex;
  flex-direction: column;
}

.phase-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.phase-icon {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.phase-icon.extracting {
  background: linear-gradient(135deg, #DBEAFE, #BFDBFE);
  color: #2563EB;
}

.phase-icon.generating {
  background: linear-gradient(135deg, #D1FAE5, #A7F3D0);
  color: #059669;
}

.phase-text h2 {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 4px 0;
}

.phase-text p {
  font-size: 14px;
  color: #6B7280;
  margin: 0;
}

/* ========== Extraction Progress ========== */
.extraction-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: #E5E7EB;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3B82F6, #2563EB);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  color: #2563EB;
}

/* ========== Claims Header ========== */
.claims-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.claims-header h2 {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}

.claim-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #6B7280;
  background: #F3F4F6;
  padding: 4px 12px;
  border-radius: 20px;
}

/* ========== Claims List ========== */
.claims-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.claim-card {
  padding: 16px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.claim-card:hover {
  border-color: #93C5FD;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.08);
}

.claim-card.is-active {
  border-color: #3B82F6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.claim-card.is-reviewed {
  border-left: 3px solid #10B981;
}

.claim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.claim-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  color: #9CA3AF;
}

.claim-confidence {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 12px;
}

.claim-confidence.high { background: #D1FAE5; color: #059669; }
.claim-confidence.medium { background: #FEF3C7; color: #D97706; }
.claim-confidence.low { background: #FEE2E2; color: #DC2626; }
.claim-confidence.unknown { background: #F3F4F6; color: #9CA3AF; }

.claim-text {
  font-size: 14px;
  color: #374151;
  line-height: 1.6;
  margin: 0 0 8px 0;
}

.claim-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.claim-category {
  font-size: 11px;
  color: #6B7280;
  background: #F3F4F6;
  padding: 2px 8px;
  border-radius: 4px;
}

.claim-status.reviewed {
  font-size: 11px;
  color: #059669;
  background: #D1FAE5;
  padding: 2px 8px;
  border-radius: 4px;
}

/* ========== Review Detail Panel ========== */
.review-detail-panel {
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 16px;
  padding: 24px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.detail-header h3 {
  font-size: 16px;
  font-weight: 700;
  color: #111827;
  margin: 0;
}

.run-review-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #3B82F6, #2563EB);
  color: #FFF;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.run-review-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

.run-review-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ========== 5-Role Review Grid ========== */
.review-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.role-card {
  background: #FAFAFA;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.2s ease;
}

.role-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.role-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.role-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.role-icon.fact_checker { background: #DBEAFE; color: #2563EB; }
.role-icon.supporter { background: #D1FAE5; color: #059669; }
.role-icon.opponent { background: #FEE2E2; color: #DC2626; }
.role-icon.risk_reviewer { background: #FEF3C7; color: #D97706; }
.role-icon.evidence_organizer { background: #EDE9FE; color: #7C3AED; }

.role-card.fact_checker { border-top: 3px solid #3B82F6; }
.role-card.supporter { border-top: 3px solid #10B981; }
.role-card.opponent { border-top: 3px solid #EF4444; }
.role-card.risk_reviewer { border-top: 3px solid #F59E0B; }
.role-card.evidence_organizer { border-top: 3px solid #8B5CF6; }

.role-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.role-content p {
  font-size: 13px;
  color: #6B7280;
  line-height: 1.6;
  margin: 0;
}

.role-pending {
  color: #D1D5DB !important;
  font-style: italic;
}

.role-loading {
  display: flex;
  justify-content: center;
  padding: 12px 0;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  background: #9CA3AF;
  border-radius: 50%;
  animation: dot-pulse 1.2s ease-in-out infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

.role-score {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #F3F4F6;
}

.score-label {
  font-size: 11px;
  color: #9CA3AF;
  white-space: nowrap;
}

.score-bar {
  flex: 1;
  height: 4px;
  background: #E5E7EB;
  border-radius: 2px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}

.score-fill.fact_checker { background: #3B82F6; }
.score-fill.supporter { background: #10B981; }
.score-fill.opponent { background: #EF4444; }
.score-fill.risk_reviewer { background: #F59E0B; }
.score-fill.evidence_organizer { background: #8B5CF6; }

.score-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  min-width: 24px;
  text-align: right;
}

/* ========== Claims Header Right ========== */
.claims-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.review-all-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: linear-gradient(135deg, #3B82F6, #2563EB);
  color: #FFF;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.review-all-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.3);
}

.review-all-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ========== Review Progress Bar ========== */
.review-progress-bar {
  margin-bottom: 20px;
  padding: 12px 16px;
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  border-radius: 10px;
}

.review-progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.review-progress-text {
  font-size: 13px;
  font-weight: 600;
  color: #1D4ED8;
}

.review-progress-percent {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  color: #2563EB;
}

.review-fill {
  background: linear-gradient(90deg, #3B82F6, #1D4ED8) !important;
}

/* ========== Reviewed Phase ========== */
.reviewed-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.phase-icon.reviewed {
  background: linear-gradient(135deg, #D1FAE5, #A7F3D0);
  color: #059669;
}

.reviewed-confidence-overview {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px 24px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  margin-bottom: 20px;
}

.confidence-mini-ring {
  position: relative;
  width: 70px;
  height: 70px;
}

.confidence-mini-ring svg {
  width: 100%;
  height: 100%;
}

.confidence-mini-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 800;
  color: #111827;
}

.conf-mini-unit {
  font-size: 11px;
  color: #9CA3AF;
}

.conf-mini-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conf-mini-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.conf-mini-desc {
  font-size: 13px;
  color: #6B7280;
}

/* Reviewed Claims Summary */
.reviewed-claims-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 24px;
  max-height: 300px;
  overflow-y: auto;
}

.reviewed-claim-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  gap: 12px;
}

.reviewed-claim-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.reviewed-claim-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #9CA3AF;
  flex-shrink: 0;
}

.reviewed-claim-text {
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.reviewed-claim-confidence {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 12px;
  flex-shrink: 0;
}

/* Reviewed Actions */
.reviewed-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.generate-report-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #059669, #047857);
  color: #FFF;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 14px rgba(5, 150, 105, 0.3);
}

.generate-report-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(5, 150, 105, 0.4);
}

.generate-report-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ========== Agent Steps ========== */
.agent-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: 24px;
}

.agent-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  position: relative;
}

.agent-step::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 32px;
  bottom: -4px;
  width: 2px;
  background: #E5E7EB;
}

.agent-step:last-child::before { display: none; }
.agent-step.done::before { background: #10B981; }

.step-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #E5E7EB;
  border: 2px solid #FFF;
  box-shadow: 0 0 0 2px #E5E7EB;
  z-index: 1;
  transition: all 0.3s ease;
}

.agent-step.active .step-dot {
  background: #3B82F6;
  box-shadow: 0 0 0 2px #3B82F6, 0 0 0 4px rgba(59, 130, 246, 0.2);
  animation: pulse-dot 1.5s ease-in-out infinite;
}

.agent-step.done .step-dot {
  background: #10B981;
  box-shadow: 0 0 0 2px #10B981;
}

@keyframes pulse-dot {
  0%, 100% { box-shadow: 0 0 0 2px #3B82F6; }
  50% { box-shadow: 0 0 0 2px #3B82F6, 0 0 0 6px rgba(59, 130, 246, 0.15); }
}

.step-label {
  font-size: 14px;
  color: #9CA3AF;
  transition: color 0.3s ease;
}

.agent-step.active .step-label { color: #2563EB; font-weight: 600; }
.agent-step.done .step-label { color: #059669; }

/* ========== Report Phase ========== */
.report-phase {
  padding: 0 !important;
}

.report-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 32px;
}

/* Traceable Header */
.traceable-header {
  text-align: center;
  margin-bottom: 40px;
  padding-bottom: 32px;
  border-bottom: 1px solid #E5E7EB;
}

.report-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: linear-gradient(135deg, #DBEAFE, #BFDBFE);
  color: #1D4ED8;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 16px;
}

.traceable-title {
  font-size: 26px;
  font-weight: 800;
  color: #111827;
  margin: 0 0 24px 0;
  line-height: 1.3;
}

/* Confidence Display */
.confidence-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
}

.confidence-ring {
  position: relative;
  width: 100px;
  height: 100px;
}

.confidence-ring svg {
  width: 100%;
  height: 100%;
}

.confidence-value {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: baseline;
}

.conf-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 28px;
  font-weight: 800;
  color: #111827;
}

.conf-unit {
  font-size: 14px;
  color: #9CA3AF;
  margin-left: 2px;
}

.confidence-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conf-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.conf-desc {
  font-size: 13px;
  color: #6B7280;
}

/* Report Sections */
.report-section {
  margin-bottom: 32px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 16px;
  padding: 24px;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 700;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.badge-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  background: #EFF6FF;
  color: #2563EB;
  padding: 2px 8px;
  border-radius: 10px;
}

.question-text {
  font-size: 16px;
  color: #1F2937;
  line-height: 1.7;
  margin: 0;
  padding: 16px;
  background: #F9FAFB;
  border-radius: 8px;
  border-left: 4px solid #3B82F6;
}

/* Evidence Chain */
.evidence-chain {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.evidence-item {
  display: flex;
  gap: 16px;
}

.ev-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.ev-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  color: #2563EB;
  background: #EFF6FF;
  padding: 3px 8px;
  border-radius: 6px;
  white-space: nowrap;
}

.ev-line {
  width: 2px;
  flex: 1;
  background: linear-gradient(180deg, #93C5FD, #DBEAFE);
  margin: 4px 0;
}

.ev-body {
  flex: 1;
  padding-bottom: 20px;
}

.ev-text {
  font-size: 14px;
  color: #374151;
  line-height: 1.7;
  margin: 0 0 8px 0;
}

.ev-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.ev-source {
  font-size: 12px;
  color: #6B7280;
  background: #F3F4F6;
  padding: 2px 8px;
  border-radius: 4px;
}

.ev-reliability {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.ev-reliability.high { background: #D1FAE5; color: #059669; }
.ev-reliability.medium { background: #FEF3C7; color: #D97706; }
.ev-reliability.low { background: #FEE2E2; color: #DC2626; }

/* Review Summary Grid */
.review-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.summary-role-card {
  padding: 14px;
  border-radius: 10px;
  background: #FAFAFA;
  border: 1px solid #E5E7EB;
}

.summary-role-card.fact_checker { border-left: 3px solid #3B82F6; }
.summary-role-card.supporter { border-left: 3px solid #10B981; }
.summary-role-card.opponent { border-left: 3px solid #EF4444; }
.summary-role-card.risk_reviewer { border-left: 3px solid #F59E0B; }
.summary-role-card.evidence_organizer { border-left: 3px solid #8B5CF6; }

.summary-role-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.summary-role-icon { font-size: 14px; }

.summary-role-name {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.summary-role-text {
  font-size: 12px;
  color: #6B7280;
  line-height: 1.5;
  margin: 0;
}

/* Report Body */
.report-body {
  font-size: 14.5px;
  line-height: 1.85;
  color: #1F2937;
}

.report-body :deep(.md-h1) {
  font-size: 24px;
  font-weight: 800;
  color: #111827;
  margin: 24px 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #E5E7EB;
}

.report-body :deep(.md-h2) {
  font-size: 20px;
  font-weight: 700;
  color: #1F2937;
  margin: 20px 0 12px 0;
  padding-bottom: 6px;
  border-bottom: 2px solid #E5E7EB;
}

.report-body :deep(.md-h3) {
  font-size: 16px;
  font-weight: 700;
  color: #374151;
  margin: 16px 0 8px 0;
  padding-left: 12px;
  border-left: 3px solid #3B82F6;
}

.report-body :deep(strong) {
  font-weight: 600;
  color: #111827;
}

.report-body :deep(.inline-code) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  background: #F3F4F6;
  padding: 2px 6px;
  border-radius: 4px;
  color: #E11D48;
}

.report-body :deep(.ev-ref) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #2563EB;
  background: #EFF6FF;
  padding: 1px 6px;
  border-radius: 4px;
  cursor: pointer;
}

/* ========== Original Report Section ========== */
.original-report-section {
  max-width: 900px;
  width: 100%;
  margin-bottom: 32px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 16px;
  padding: 24px;
}

.original-report-section .section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 700;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.original-report-content {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
  max-height: 500px;
  overflow-y: auto;
  padding: 16px;
  background: #F9FAFB;
  border-radius: 8px;
}

.original-report-content :deep(h1) {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  margin: 16px 0 8px 0;
}

.original-report-content :deep(h2) {
  font-size: 17px;
  font-weight: 700;
  color: #1F2937;
  margin: 14px 0 6px 0;
  padding-bottom: 4px;
  border-bottom: 1px solid #E5E7EB;
}

.original-report-content :deep(h3) {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
  margin: 12px 0 4px 0;
  padding-left: 10px;
  border-left: 3px solid #3B82F6;
}

.original-report-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 32px;
  color: #6B7280;
  font-size: 14px;
}

.original-report-loading .loading-icon {
  color: #3B82F6;
}

/* ========== Init Phase ========== */
.init-phase {
  align-items: flex-start;
  justify-content: flex-start;
  overflow-y: auto;
}

.init-content {
  text-align: center;
  max-width: 480px;
  width: 100%;
  margin: 0 auto;
}

.init-icon {
  margin-bottom: 24px;
  color: #93C5FD;
}

.init-content h2 {
  font-size: 24px;
  font-weight: 800;
  color: #111827;
  margin: 0 0 12px 0;
}

.init-content p {
  font-size: 15px;
  color: #6B7280;
  line-height: 1.7;
  margin: 0 0 32px 0;
}

.start-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 32px;
  background: linear-gradient(135deg, #3B82F6, #1D4ED8);
  color: #FFF;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
}

.start-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
}

.start-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ========== Bottom Navigation ========== */
.bottom-nav {
  display: flex;
  justify-content: space-between;
  padding: 16px 32px;
  border-top: 1px solid #E5E7EB;
  background: #FFF;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-btn.secondary {
  background: #F3F4F6;
  color: #6B7280;
}

.nav-btn.secondary:hover {
  background: #E5E7EB;
  color: #374151;
}

.nav-btn.primary {
  background: linear-gradient(135deg, #3B82F6, #1D4ED8);
  color: #FFF;
}

.nav-btn.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

/* ========== Spin Animation ========== */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ========== Scrollbar ========== */
.review-panel::-webkit-scrollbar {
  width: 6px;
}

.review-panel::-webkit-scrollbar-track {
  background: transparent;
}

.review-panel::-webkit-scrollbar-thumb {
  background: #D1D5DB;
  border-radius: 3px;
}

.review-panel::-webkit-scrollbar-thumb:hover {
  background: #9CA3AF;
}
</style>
