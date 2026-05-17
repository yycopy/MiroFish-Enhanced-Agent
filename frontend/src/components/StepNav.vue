<template>
  <div class="step-nav">
    <template v-for="n in 6" :key="n">
      <div
        class="step-node"
        :class="{
          active: n === currentStep,
          completed: fullyCompleted || n < currentStep,
          clickable: isClickable(n)
        }"
        :title="stepNames[n - 1]"
        @click="navigateTo(n)"
      >
        <span v-if="fullyCompleted || n < currentStep" class="check-icon">&#10003;</span>
        <span v-else class="node-num">{{ n }}</span>
      </div>
      <div v-if="n < 6" class="step-line" :class="{ filled: fullyCompleted || n < currentStep }" />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getWorkflowId } from '../store/workflow'

const props = defineProps({
  currentStep: { type: Number, required: true },
  fullyCompleted: { type: Boolean, default: false }
})

const router = useRouter()
const { tm } = useI18n()

const stepNames = computed(() => {
  try { return tm('main.stepNames') }
  catch { return ['Step 1', 'Step 2', 'Step 3', 'Step 4', 'Step 5', 'Step 6'] }
})

function isClickable(n) {
  if (props.fullyCompleted) return routeForStep(n) !== null
  if (n >= props.currentStep) return false
  return routeForStep(n) !== null
}

function navigateTo(n) {
  if (!isClickable(n)) return
  const route = routeForStep(n)
  if (route) router.push(route)
}

function routeForStep(n) {
  switch (n) {
    case 1: {
      const id = getWorkflowId('projectId')
      return id ? { name: 'Process', params: { projectId: id } } : null
    }
    case 2: {
      const id = getWorkflowId('simulationId')
      return id ? { name: 'Simulation', params: { simulationId: id } } : null
    }
    case 3: {
      const id = getWorkflowId('simulationId')
      return id ? { name: 'SimulationRun', params: { simulationId: id } } : null
    }
    case 4:
    case 5:
    case 6: {
      const id = getWorkflowId('reportId')
      if (!id) return null
      const names = { 4: 'Report', 5: 'Review', 6: 'Interaction' }
      return { name: names[n], params: { reportId: id } }
    }
    default: return null
  }
}
</script>

<style scoped>
.step-nav {
  display: flex;
  align-items: center;
}

.step-node {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  border: 2px solid #E0E0E0;
  color: #CCC;
  background: #FFF;
  transition: all 0.2s;
  user-select: none;
}

.step-node.active {
  border-color: #000;
  background: #000;
  color: #FFF;
}

.step-node.completed {
  border-color: #4CAF50;
  color: #4CAF50;
  background: #E8F5E9;
}

.step-node.clickable {
  cursor: pointer;
}

.step-node.clickable:hover {
  transform: scale(1.2);
}

.check-icon {
  font-size: 12px;
  line-height: 1;
}

.node-num {
  line-height: 1;
}

.step-line {
  width: 14px;
  height: 2px;
  background: #E0E0E0;
  transition: background 0.2s;
}

.step-line.filled {
  background: #4CAF50;
}
</style>
