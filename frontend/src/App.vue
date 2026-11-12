<script setup lang="ts">
import EmergencyBanner from './components/EmergencyBanner.vue'
import MedicalDisclaimer from './components/MedicalDisclaimer.vue'
import ResultView from './components/ResultView.vue'
import SymptomChat from './components/SymptomChat.vue'
import { useTriageStore } from './stores/triage'

const store = useTriageStore()
</script>

<template>
  <header>
    <h1>MediPath</h1>
    <p>증상에서 진료까지, 더 나은 의료 선택의 시작</p>
  </header>
  <main>
    <template v-if="store.stage === 'result' && store.result">
      <ResultView :result="store.result" />
      <button type="button" class="restart" @click="store.reset()">처음부터 다시</button>
    </template>
    <template v-else>
      <EmergencyBanner v-if="store.emergency && store.emergencyNotice" :notice="store.emergencyNotice" />
      <SymptomChat />
      <MedicalDisclaimer />
    </template>
  </main>
</template>

<style>
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  color: #1b1f24;
  background: #fff;
}
#app {
  max-width: 640px;
  margin: 0 auto;
  padding: 16px;
  box-sizing: border-box;
}
header h1 {
  margin: 0;
  font-size: 24px;
}
header p {
  margin: 4px 0 16px;
  color: #555;
}
main {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.restart {
  font: inherit;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid #ccc;
  background: #fff;
}
</style>
