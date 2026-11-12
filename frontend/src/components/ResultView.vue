<script setup lang="ts">
import type { TriageResult } from '../api/types'
import EmergencyBanner from './EmergencyBanner.vue'
import HospitalFinder from './HospitalFinderPlaceholder.vue'
import MedicalDisclaimer from './MedicalDisclaimer.vue'

const props = defineProps<{ result: TriageResult }>()
const percent = (p: number) => `${Math.round(p * 100)}%`
const department = props.result.recommended_departments[0]
</script>

<template>
  <div class="result">
    <EmergencyBanner v-if="result.emergency && result.emergency_notice" :notice="result.emergency_notice" />

    <section>
      <h2>가능성 있는 질환</h2>
      <ul class="predictions">
        <li v-for="p in result.predictions" :key="p.disease_id" data-test="prediction">
          <span class="name">{{ p.disease_name_ko }}</span>
          <span class="bar"><span class="fill" :style="{ width: percent(p.probability) }" /></span>
          <span class="pct">{{ percent(p.probability) }}</span>
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

    <HospitalFinder v-if="department" :department="department.code" />

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
  grid-template-columns: 7em 1fr 3em;
  align-items: center;
  gap: 8px;
}
.bar {
  height: 10px;
  background: #eee;
  border-radius: 5px;
  overflow: hidden;
}
.fill {
  display: block;
  height: 100%;
  background: #2f6fde;
}
.pct {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
