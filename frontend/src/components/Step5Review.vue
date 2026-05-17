<template>
  <div class="review-panel">
    <IngestionStatusStrip :projectId="getWorkflowId('projectId') || ''" />
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
        </div>

        <!-- Section 1: 事件概述 -->
        <div class="report-section section-overview">
          <div class="section-header">
            <div class="section-number">01</div>
            <div class="section-title-group">
              <h2 class="section-title">事件概述</h2>
              <p class="section-subtitle">Event Overview</p>
            </div>
          </div>
          <div v-if="traceableReport.question" class="question-card">
            <div class="question-label">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
              <span>{{ $t('step5.question') }}</span>
            </div>
            <p class="question-text">{{ traceableReport.question }}</p>
          </div>
          <div class="overview-stats">
            <div class="stat-item" v-for="stat in evidenceSourceStats" :key="stat.type">
              <span class="stat-value">{{ stat.count }}</span>
              <span class="stat-label">{{ stat.label }}</span>
            </div>
          </div>
          <!-- Overview extracted from report body -->
          <div v-if="parsedSections[0]" class="section-body" v-html="parsedSections[0]"></div>
        </div>

        <!-- Section 2: 多源证据链 -->
        <div class="report-section section-evidence">
          <div class="section-header">
            <div class="section-number">02</div>
            <div class="section-title-group">
              <h2 class="section-title">多源证据链</h2>
              <p class="section-subtitle">Multi-Source Evidence Chain</p>
            </div>
            <span class="badge-count" v-if="allEvidence.length">{{ allEvidence.length }}</span>
          </div>
          <div v-if="allEvidence.length" class="evidence-grid">
            <div v-for="(ev, idx) in allEvidence" :key="idx" class="evidence-card" :class="ev.source_type">
              <div class="ev-card-header">
                <span class="ev-id">{{ ev.evidence_id || ev.id || ('EV-' + String(idx+1).padStart(3,'0')) }}</span>
                <span class="ev-type-badge" :class="ev.source_type">{{ sourceTypeLabel(ev.source_type) }}</span>
              </div>
              <p class="ev-card-text">{{ ev.evidence_text || ev.content || ev.text || ev.description }}</p>
              <div class="ev-card-footer">
                <span v-if="ev.source" class="ev-source-tag">{{ ev.source }}</span>
                <div v-if="ev.reliability != null" class="reliability-bar-mini">
                  <div class="reliability-fill" :class="getReliabilityClass(ev.reliability)" :style="{ width: ev.reliability + '%' }"></div>
                </div>
                <span v-if="ev.reliability != null" class="ev-reliability-num" :class="getReliabilityClass(ev.reliability)">{{ ev.reliability }}%</span>
              </div>
            </div>
          </div>
          <div v-else-if="parsedSections[1]" class="section-body" v-html="parsedSections[1]"></div>
        </div>

        <!-- Section 3: 分析性预测 -->
        <div class="report-section section-prediction">
          <div class="section-header">
            <div class="section-number">03</div>
            <div class="section-title-group">
              <h2 class="section-title">分析性预测</h2>
              <p class="section-subtitle">Analytical Prediction</p>
            </div>
          </div>
          <div v-if="parsedSections[2]" class="section-body" v-html="parsedSections[2]"></div>
          <div v-else-if="reportBodyHtml" class="section-body" v-html="reportBodyHtml"></div>
        </div>

        <!-- Section 4: 多角色评审与置信度 -->
        <div class="report-section section-review">
          <div class="section-header">
            <div class="section-number">04</div>
            <div class="section-title-group">
              <h2 class="section-title">多角色评审与置信度</h2>
              <p class="section-subtitle">Multi-Role Review & Confidence</p>
            </div>
          </div>
          <!-- Role cards grid -->
          <div v-if="reviewRoles.length" class="role-review-grid">
            <div v-for="role in reviewRoles" :key="role.id" class="role-review-card" :class="role.id">
              <div class="role-review-header">
                <span class="role-review-icon" v-html="role.icon"></span>
                <span class="role-review-name">{{ $t('step5.roles.' + role.id) }}</span>
                <span v-if="getRoleDecision(role.id)" class="role-decision-badge" :class="getRoleDecision(role.id)">
                  {{ getRoleDecisionLabel(role.id) }}
                </span>
              </div>
              <p class="role-review-text">{{ getRoleSummary(role.id) || ($t('step5.pendingReview')) }}</p>
              <div v-if="getRoleConfidence(role.id) > 0" class="role-confidence-bar">
                <div class="role-confidence-fill" :style="{ width: (getRoleConfidence(role.id) * 100) + '%' }"></div>
              </div>
            </div>
          </div>
          <div v-if="parsedSections[3]" class="section-body" v-html="parsedSections[3]"></div>
        </div>

        <!-- Section 5: 不确定性声明 + 置信度椭圆 -->
        <div class="report-section section-uncertainty">
          <div class="section-header">
            <div class="section-number">05</div>
            <div class="section-title-group">
              <h2 class="section-title">不确定性声明</h2>
              <p class="section-subtitle">Uncertainty Statement</p>
            </div>
          </div>
          <div v-if="parsedSections[4]" class="section-body" v-html="parsedSections[4]"></div>

          <!-- Ellipse Confidence Visualization -->
          <div class="confidence-ellipse-wrapper">
            <div class="confidence-ellipse-container">
              <svg viewBox="0 0 300 180" class="confidence-ellipse-svg">
                <!-- Background ellipse -->
                <ellipse cx="150" cy="90" rx="130" ry="70" fill="none" stroke="#E5E7EB" stroke-width="3" />
                <!-- Confidence fill ellipse -->
                <ellipse cx="150" cy="90" :rx="confidenceEllipseRx" :ry="confidenceEllipseRy"
                  :fill="confidenceFillColor" :opacity="0.15" />
                <!-- Confidence stroke ellipse -->
                <ellipse cx="150" cy="90" :rx="confidenceEllipseRx" :ry="confidenceEllipseRy"
                  fill="none" :stroke="confidenceColor" stroke-width="3" stroke-dasharray="8 4" />
                <!-- Center text -->
                <text x="150" y="82" text-anchor="middle" class="ellipse-value-text">{{ overallConfidence }}%</text>
                <text x="150" y="105" text-anchor="middle" class="ellipse-label-text">{{ confidenceDescription }}</text>
                <!-- Tick marks -->
                <line x1="20" y1="90" x2="30" y2="90" stroke="#D1D5DB" stroke-width="1.5" />
                <line x1="270" y1="90" x2="280" y2="90" stroke="#D1D5DB" stroke-width="1.5" />
                <line x1="150" y1="15" x2="150" y2="25" stroke="#D1D5DB" stroke-width="1.5" />
                <line x1="150" y1="155" x2="150" y2="165" stroke="#D1D5DB" stroke-width="1.5" />
                <!-- Labels -->
                <text x="15" y="86" text-anchor="end" class="ellipse-tick-label">0</text>
                <text x="285" y="86" text-anchor="start" class="ellipse-tick-label">100</text>
              </svg>
            </div>
          </div>
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
import { listReviewClaims, evaluateClaim, runTraceableReport, getTraceableReport, getTraceableStatus, getReport } from '../api/report'
import { getWorkflowId } from '../store/workflow'
import IngestionStatusStrip from './IngestionStatusStrip.vue'

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
  { label: 'Memory Recall', done: false, active: false },
  { label: 'Graph Retrieve', done: false, active: false },
  { label: 'Active Search', done: false, active: false },
  { label: 'Agent Interview', done: false, active: false },
  { label: 'Evidence Trace', done: false, active: false },
  { label: 'Draft Report', done: false, active: false },
  { label: 'Confidence Review', done: false, active: false },
  { label: 'Revise Report', done: false, active: false }
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

// Evidence chain from report result
const allEvidence = computed(() => {
  const report = traceableReport.value
  return report.evidence_chain || report.evidence_trace || []
})

// Evidence source statistics
const evidenceSourceStats = computed(() => {
  const evidence = allEvidence.value
  const typeMap = {}
  evidence.forEach(ev => {
    const type = ev.source_type || 'unknown'
    typeMap[type] = (typeMap[type] || 0) + 1
  })
  const labelMap = {
    graph: 'Graph',
    memory: 'Memory',
    agent_interview: 'Interview',
    active_search: 'Search',
  }
  const stats = Object.entries(typeMap).map(([type, count]) => ({
    type,
    count,
    label: labelMap[type] || type,
  }))
  if (stats.length === 0) {
    return [
      { type: 'graph', count: 0, label: 'Graph' },
      { type: 'memory', count: 0, label: 'Memory' },
      { type: 'agent_interview', count: 0, label: 'Interview' },
      { type: 'active_search', count: 0, label: 'Search' },
    ]
  }
  return stats
})

// Parse report content into 5 sections
const parsedSections = computed(() => {
  const content = traceableReport.value.content || traceableReport.value.report_content || ''
  if (!content) return {}

  // Split by ## headings that match our 5 sections
  const sectionPatterns = [
    /##\s*1\.\s*(?:事件概述|Event Overview)/i,
    /##\s*2\.\s*(?:多源证据链|Multi-Source Evidence Chain)/i,
    /##\s*3\.\s*(?:分析性预测|Analytical Prediction)/i,
    /##\s*4\.\s*(?:多角色评审与置信度|Multi-Role Review)/i,
    /##\s*5\.\s*(?:不确定性声明|Uncertainty Statement)/i,
  ]

  const sections = {}
  let remaining = content

  for (let i = 0; i < sectionPatterns.length; i++) {
    const match = remaining.match(sectionPatterns[i])
    if (match) {
      const startIdx = match.index
      // Find the next section
      let endIdx = remaining.length
      for (let j = i + 1; j < sectionPatterns.length; j++) {
        const nextMatch = remaining.substring(startIdx + match[0].length).match(sectionPatterns[j])
        if (nextMatch) {
          endIdx = startIdx + match[0].length + nextMatch.index
          break
        }
      }
      const sectionContent = remaining.substring(startIdx + match[0].length, endIdx).trim()
      sections[i] = renderReport(sectionContent)
    }
  }
  return sections
})

// Fallback: render entire report body if section parsing fails
const reportBodyHtml = computed(() => {
  const content = traceableReport.value.content || traceableReport.value.report_content || ''
  if (!content) return ''
  // If sections were parsed, don't show full body
  if (Object.keys(parsedSections.value).length > 0) return ''
  return renderReport(content)
})

// Ellipse dimensions based on confidence
const confidenceEllipseRx = computed(() => {
  // Scale from 40 (0%) to 130 (100%)
  return 40 + (overallConfidence.value / 100) * 90
})

const confidenceEllipseRy = computed(() => {
  // Scale from 22 (0%) to 70 (100%)
  return 22 + (overallConfidence.value / 100) * 48
})

const confidenceFillColor = computed(() => {
  if (overallConfidence.value >= 80) return '#10B981'
  if (overallConfidence.value >= 60) return '#F59E0B'
  return '#EF4444'
})

// Source type label helper
const sourceTypeLabel = (type) => {
  const labels = {
    graph: 'Graph',
    memory: 'Memory',
    agent_interview: 'Interview',
    active_search: 'Search',
  }
  return labels[type] || type
}

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
  if (!results || !Array.isArray(results)) return ''

  // Backend structure: results[].role_reviews[] with {role, reason, support_decision}
  for (const claimResult of results) {
    const roleReviews = claimResult.role_reviews
    if (Array.isArray(roleReviews)) {
      const found = roleReviews.find(r => r.role === roleId)
      if (found) {
        return found.reason || found.analysis || found.summary || ''
      }
    }
  }

  // Fallback: flat array with {role, summary, analysis}
  const found = results.find(r => r.role === roleId)
  return found?.summary || found?.analysis || ''
}

const _findRoleReview = (roleId) => {
  const results = traceableReport.value.review_results
  if (!results || !Array.isArray(results)) return null
  for (const claimResult of results) {
    const roleReviews = claimResult.role_reviews
    if (Array.isArray(roleReviews)) {
      const found = roleReviews.find(r => r.role === roleId)
      if (found) return found
    }
  }
  return results.find(r => r.role === roleId) || null
}

const getRoleDecision = (roleId) => {
  return _findRoleReview(roleId)?.support_decision || ''
}

const getRoleDecisionLabel = (roleId) => {
  const decision = getRoleDecision(roleId)
  if (decision === 'support') return '支持'
  if (decision === 'oppose') return '反对'
  if (decision === 'uncertain') return '不确定'
  return ''
}

const getRoleConfidence = (roleId) => {
  return _findRoleReview(roleId)?.confidence || 0
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

const STEP_KEYS = ['memory_recall', 'graph_retrieve', 'active_search', 'interview',
  'evidence_trace', 'draft_report', 'confidence_review', 'revise_report']

const generateTraceableReport = async () => {
  generatingReport.value = true
  emit('add-log', t('step5.generatingReport'))

  // Reset agent steps
  agentSteps.value.forEach(s => { s.done = false; s.active = false })

  phase.value = 'generating'

  try {
    // Start async task
    const res = await runTraceableReport({
      report_id: props.reportId,
      simulation_id: props.simulationId,
      claims: claims.value.map(c => ({ text: c.text, confidence: c.confidence, reviews: c.reviews }))
    })

    if (!res.success || !res.data?.task_id) {
      throw new Error(res.error || 'Failed to start traceable report')
    }

    const taskId = res.data.task_id

    // Poll for progress
    let pollTimer = null
    await new Promise((resolve, reject) => {
      pollTimer = setInterval(async () => {
        try {
          const statusRes = await getTraceableStatus(taskId)
          if (!statusRes.success || !statusRes.data) return

          const task = statusRes.data
          const msg = task.message || ''

          // Map backend message to agent step highlighting
          for (let i = 0; i < STEP_KEYS.length; i++) {
            if (msg.includes(STEP_KEYS[i]) || msg.includes(agentSteps.value[i].label)) {
              // Mark all previous steps as done
              for (let j = 0; j < i; j++) {
                agentSteps.value[j].active = false
                agentSteps.value[j].done = true
              }
              // Mark current as active
              agentSteps.value[i].active = true
              agentSteps.value[i].done = false
              break
            }
          }

          if (task.status === 'completed') {
            clearInterval(pollTimer)
            // Mark all steps done
            agentSteps.value.forEach(s => { s.active = false; s.done = true })

            const result = task.result || {}
            traceableReport.value = {
              content: result.report || result.content || '',
              report_content: result.report || result.content || '',
              question: result.question || '',
              evidence_chain: result.evidence_trace || result.evidence_chain || [],
              review_results: result.review_result?.results || result.review_results || [],
              confidence: result.review_result?.summary?.average_confidence || result.confidence || result.overall_confidence || 0,
              overall_confidence: result.review_result?.summary?.average_confidence || result.overall_confidence || 0,
            }
            overallConfidence.value = Math.round((traceableReport.value.confidence || 0) * 100) || calculateOverallConfidence()
            resolve()
          } else if (task.status === 'failed') {
            clearInterval(pollTimer)
            reject(new Error(task.error || 'Traceable report generation failed'))
          }
        } catch (pollErr) {
          clearInterval(pollTimer)
          reject(pollErr)
        }
      }, 1000)
    })

    phase.value = 'report'
    emit('update-status', 'completed')
    emit('add-log', t('step5.reportGenerated'))

  } catch (err) {
    emit('add-log', t('step5.reportFailed', { error: err.message }))
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

      // Check if a traceable report already exists
      const enhanced = data.enhanced_trace
      if (enhanced && enhanced.report) {
        traceableReport.value = {
          content: enhanced.report,
          report_content: enhanced.report,
          question: enhanced.question || data.simulation_requirement || '',
          evidence_chain: enhanced.evidence_trace || [],
          review_results: enhanced.review_result?.results || [],
          confidence: enhanced.review_result?.summary?.average_confidence || 0,
          overall_confidence: enhanced.review_result?.summary?.average_confidence || 0,
        }
        overallConfidence.value = Math.round((traceableReport.value.confidence || 0) * 100) || calculateOverallConfidence()
        agentSteps.value.forEach(s => { s.active = false; s.done = true })
        phase.value = 'report'
        emit('update-status', 'completed')
        emit('add-log', t('step5.reportLoaded') || 'Traceable report loaded')
        originalReportLoading.value = false
        return
      }

      // Otherwise load the original Step4 report
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
  background: linear-gradient(180deg, #F8FAFC 0%, #EFF6FF 100%);
}

.report-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 32px 60px;
}

/* Traceable Header */
.traceable-header {
  text-align: center;
  margin-bottom: 40px;
  padding: 40px 32px;
  background: linear-gradient(135deg, #1E3A5F 0%, #2563EB 100%);
  border-radius: 20px;
  color: #FFF;
}

.report-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: rgba(255,255,255,0.15);
  color: #FFF;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 16px;
  backdrop-filter: blur(4px);
}

.traceable-title {
  font-size: 28px;
  font-weight: 800;
  color: #FFF;
  margin: 0;
  line-height: 1.3;
}

/* ========== 5-Section Report Layout ========== */
.report-section {
  margin-bottom: 24px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 16px;
  padding: 28px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: box-shadow 0.2s;
}

.report-section:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #F3F4F6;
}

.section-number {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 800;
  color: #CBD5E1;
  line-height: 1;
  min-width: 36px;
}

.section-title-group {
  flex: 1;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  margin: 0;
  line-height: 1.3;
}

.section-subtitle {
  font-size: 12px;
  color: #9CA3AF;
  margin: 2px 0 0 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-body {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
}

.section-body :deep(h2) {
  font-size: 16px;
  font-weight: 700;
  color: #1F2937;
  margin: 20px 0 10px 0;
  padding-bottom: 6px;
  border-bottom: 1px solid #F3F4F6;
}

.section-body :deep(h3) {
  font-size: 14px;
  font-weight: 700;
  color: #374151;
  margin: 16px 0 8px 0;
  padding-left: 10px;
  border-left: 3px solid #3B82F6;
}

.section-body :deep(strong) {
  font-weight: 600;
  color: #111827;
}

.section-body :deep(.ev-ref) {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #2563EB;
  background: #EFF6FF;
  padding: 1px 6px;
  border-radius: 4px;
}

.badge-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  background: #EFF6FF;
  color: #2563EB;
  padding: 4px 10px;
  border-radius: 12px;
}

/* Section 1: Overview */
.question-card {
  background: linear-gradient(135deg, #EFF6FF, #DBEAFE);
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 16px;
}

.question-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #2563EB;
  margin-bottom: 8px;
}

.question-text {
  font-size: 16px;
  color: #1E3A5F;
  line-height: 1.6;
  margin: 0;
  font-weight: 500;
}

.overview-stats {
  display: flex;
  gap: 16px;
  margin-top: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 20px;
  background: #F9FAFB;
  border-radius: 10px;
  border: 1px solid #F3F4F6;
  min-width: 72px;
}

.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 22px;
  font-weight: 800;
  color: #111827;
}

.stat-label {
  font-size: 11px;
  color: #9CA3AF;
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

/* Section 2: Evidence Grid */
.evidence-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.evidence-card {
  padding: 14px 16px;
  background: #FAFAFA;
  border: 1px solid #F3F4F6;
  border-radius: 10px;
  transition: all 0.2s;
}

.evidence-card:hover {
  border-color: #D1D5DB;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.evidence-card.graph { border-left: 3px solid #3B82F6; }
.evidence-card.memory { border-left: 3px solid #8B5CF6; }
.evidence-card.agent_interview { border-left: 3px solid #F59E0B; }
.evidence-card.active_search { border-left: 3px solid #10B981; }

.ev-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.ev-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  color: #2563EB;
  background: #EFF6FF;
  padding: 2px 8px;
  border-radius: 6px;
}

.ev-type-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

.ev-type-badge.graph { background: #DBEAFE; color: #1D4ED8; }
.ev-type-badge.memory { background: #EDE9FE; color: #6D28D9; }
.ev-type-badge.agent_interview { background: #FEF3C7; color: #B45309; }
.ev-type-badge.active_search { background: #D1FAE5; color: #047857; }

.ev-card-text {
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
  margin: 0 0 10px 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ev-card-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ev-source-tag {
  font-size: 11px;
  color: #6B7280;
  background: #F3F4F6;
  padding: 2px 8px;
  border-radius: 4px;
}

.reliability-bar-mini {
  flex: 1;
  height: 3px;
  background: #E5E7EB;
  border-radius: 2px;
  overflow: hidden;
}

.reliability-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}

.reliability-fill.high { background: #10B981; }
.reliability-fill.medium { background: #F59E0B; }
.reliability-fill.low { background: #EF4444; }

.ev-reliability-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
}

.ev-reliability-num.high { color: #059669; }
.ev-reliability-num.medium { color: #D97706; }
.ev-reliability-num.low { color: #DC2626; }

/* Section 4: Role Review Grid */
.role-review-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.role-review-card {
  padding: 14px;
  background: #FAFAFA;
  border: 1px solid #F3F4F6;
  border-radius: 10px;
  transition: all 0.2s;
}

.role-review-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.role-review-card.fact_checker { border-left: 3px solid #3B82F6; }
.role-review-card.supporter { border-left: 3px solid #10B981; }
.role-review-card.opponent { border-left: 3px solid #EF4444; }
.role-review-card.risk_reviewer { border-left: 3px solid #F59E0B; }
.role-review-card.evidence_organizer { border-left: 3px solid #8B5CF6; }

.role-review-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.role-review-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.role-review-card.fact_checker .role-review-icon { background: #DBEAFE; color: #2563EB; }
.role-review-card.supporter .role-review-icon { background: #D1FAE5; color: #059669; }
.role-review-card.opponent .role-review-icon { background: #FEE2E2; color: #DC2626; }
.role-review-card.risk_reviewer .role-review-icon { background: #FEF3C7; color: #D97706; }
.role-review-card.evidence_organizer .role-review-icon { background: #EDE9FE; color: #7C3AED; }

.role-review-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.role-review-text {
  font-size: 12px;
  color: #6B7280;
  line-height: 1.5;
  margin: 0;
}

.role-decision-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  margin-left: auto;
  white-space: nowrap;
}
.role-decision-badge.support { background: #D1FAE5; color: #059669; }
.role-decision-badge.oppose { background: #FEE2E2; color: #DC2626; }
.role-decision-badge.uncertain { background: #FEF3C7; color: #D97706; }

.role-confidence-bar {
  height: 4px;
  background: #E5E7EB;
  border-radius: 2px;
  margin-top: 8px;
  overflow: hidden;
}
.role-confidence-fill {
  height: 100%;
  background: linear-gradient(90deg, #3B82F6, #10B981);
  border-radius: 2px;
  transition: width 0.6s ease;
}

/* Section 5: Ellipse Confidence */
.confidence-ellipse-wrapper {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

.confidence-ellipse-container {
  width: 100%;
  max-width: 380px;
  background: linear-gradient(135deg, #F8FAFC, #EFF6FF);
  border-radius: 16px;
  padding: 16px;
  border: 1px solid #E5E7EB;
}

.confidence-ellipse-svg {
  width: 100%;
  height: auto;
}

.ellipse-value-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 32px;
  font-weight: 800;
  fill: #111827;
}

.ellipse-label-text {
  font-size: 13px;
  fill: #6B7280;
  font-weight: 500;
}

.ellipse-tick-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  fill: #9CA3AF;
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
