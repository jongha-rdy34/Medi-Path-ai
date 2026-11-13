<script setup lang="ts">
// Progress shown right after sending (SPEC 1: results p95 < 10 s, progress immediately).
// The backend answers in one request, so steps advance on a timer (stores/triage.ts).
import type { Step } from '../stores/triage'

defineProps<{ step: Step }>()

const steps: { id: Step; label: string }[] = [
  { id: 'extract', label: '증상 정리 중' },
  { id: 'analyze', label: '질환 분석 중' },
  { id: 'done', label: '결과' },
]
</script>

<template>
  <ol class="progress" aria-live="polite" data-test="progress">
    <li v-for="s in steps" :key="s.id" :aria-current="s.id === step ? 'step' : undefined" :class="{ active: s.id === step }">
      {{ s.label }}
    </li>
  </ol>
</template>

<style scoped>
.progress {
  list-style: none;
  display: flex;
  gap: 8px;
  padding: 0;
  margin: 0;
  font-size: 14px;
  color: #777;
}
.progress li::after {
  content: '›';
  margin-left: 8px;
  color: #bbb;
}
.progress li:last-child::after {
  content: '';
}
.active {
  color: #2f6fde;
  font-weight: 700;
}
</style>
