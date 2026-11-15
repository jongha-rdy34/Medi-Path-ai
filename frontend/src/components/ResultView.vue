<script setup lang="ts">
import type { Likelihood, TriageResult } from '../api/types'
import EmergencyBanner from './EmergencyBanner.vue'
import HospitalFinder from './HospitalFinderPlaceholder.vue'
import MedicalDisclaimer from './MedicalDisclaimer.vue'

const props = defineProps<{ result: TriageResult }>()
// Users see a likelihood label, never a percentage (2026-11-15). The backend picks the label.
const LABELS: Record<Likelihood, string> = {
  high: '가능성 높음',
  medium: '가능성 보통',
  low: '가능성 낮음',
}
const department = props.result.recommended_departments[0]
</script>

<template>
  <div class="result">
    <EmergencyBanner v-if="result.emergency && result.emergency_notice" :notice="result.emergency_notice" />

    <section>
      <h2>가능성 있는 질환</h2>
      <p v-if="result.order_adjusted" class="order-adjusted" data-test="order-adjusted">
        국내 발생 빈도를 반영해 순서를 조정했습니다.
      </p>
      <ul class="predictions">
        <li v-for="p in result.predictions" :key="p.disease_id" data-test="prediction">
          <span class="name">{{ p.disease_name_ko }}</span>
          <span v-if="p.likelihood" :class="['likelihood', p.likelihood]" data-test="likelihood">
            {{ LABELS[p.likelihood] }}
          </span>
          <p v-if="p.note" class="note" data-test="prediction-note">{{ p.note }}</p>
        </li>
      </ul>
    </section>

    <section v-if="department">
      <h2>권장 진료과: {{ department.name_ko }}</h2>
      <p>{{ department.reason }}</p>
    </section>

    <section>
      <h2>설명</h2>
      <p>{{ result.explanation }}</p>
    </section>

    <!-- Emergency (decision A, 2026-11-12): no hospital list; the banner offers 119 and the e-gen ER finder. -->
    <HospitalFinder v-if="department && !result.emergency" :department="department.code" />

    <MedicalDisclaimer :text="result.disclaimer" />
  </div>
</template>

<style scoped>
.result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
h2 {
  font-size: 17px;
  margin: 0 0 8px;
}
.predictions {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 8px;
}
.predictions li {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 8px;
}
.note {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 13px;
  color: #6b4e00;
  background: #fff6db;
  border-radius: 6px;
  padding: 6px 8px;
}
.likelihood {
  justify-self: end;
  font-size: 13px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
}
.likelihood.high {
  color: #fff;
  background: #2f6fde;
}
.likelihood.medium {
  color: #1d4ea3;
  background: #dce8fb;
}
.likelihood.low {
  color: #555;
  background: #eee;
}
.order-adjusted {
  margin: 0 0 8px;
  font-size: 13px;
  color: #555;
}
</style>
