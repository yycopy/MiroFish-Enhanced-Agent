<template>
  <div v-if="status" class="ingestion-strip" :class="{ active: status.active }">
    <span class="ingestion-strip-icon">{{ status.active ? '⬤' : '○' }}</span>
    <span class="ingestion-strip-label">{{ $t('step3.ingestionStripLabel') }}</span>
    <span class="ingestion-strip-state">{{ status.active ? $t('step3.ingestionCollecting') : $t('step3.ingestionIdle') }}</span>
    <span v-if="status.active" class="ingestion-strip-detail">
      {{ $t('step3.ingestionRunN', { n: status.total_runs || 0 }) }}
      &middot;
      {{ formatInterval(status.interval_seconds) }}
      &middot;
      {{ (status.keywords || []).slice(0, 3).join(', ') }}
      <span v-if="(status.keywords || []).length > 3">+{{ status.keywords.length - 3 }}</span>
    </span>
    <button
      v-if="!status.active"
      class="ingestion-strip-btn"
      @click="refresh"
    >{{ $t('common.refresh') }}</button>
  </div>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { getProjectIngestionStatus } from '../api/simulation'

const props = defineProps({
  projectId: { type: String, default: '' }
})

const status = ref(null)
let pollTimer = null

const formatInterval = (seconds) => {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`
  return `${(seconds / 3600).toFixed(1)}h`
}

const fetchStatus = async () => {
  if (!props.projectId) return
  try {
    const res = await getProjectIngestionStatus(props.projectId)
    if (res.success) {
      status.value = res
    }
  } catch { /* silent */ }
}

const startPolling = () => {
  if (pollTimer) return
  pollTimer = setInterval(fetchStatus, 30000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const refresh = () => {
  fetchStatus()
  startPolling()
}

watch(() => props.projectId, (id) => {
  if (id) {
    fetchStatus()
    startPolling()
  } else {
    stopPolling()
    status.value = null
  }
}, { immediate: true })

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.ingestion-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 16px;
  background: #F8FAFC;
  border-bottom: 1px solid #E2E8F0;
  font-size: 11px;
  flex-shrink: 0;
}

.ingestion-strip.active {
  background: #ECFDF5;
  border-bottom-color: #A7F3D0;
}

.ingestion-strip-icon {
  font-size: 8px;
  color: #94A3B8;
}

.ingestion-strip.active .ingestion-strip-icon {
  color: #059669;
}

.ingestion-strip-label {
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.ingestion-strip-state {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #94A3B8;
}

.ingestion-strip.active .ingestion-strip-state {
  color: #059669;
}

.ingestion-strip-detail {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
  color: #64748B;
  font-size: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ingestion-strip-btn {
  background: none;
  border: 1px solid #E2E8F0;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 10px;
  color: #64748B;
  cursor: pointer;
}

.ingestion-strip-btn:hover {
  border-color: #94A3B8;
  color: #333;
}
</style>
