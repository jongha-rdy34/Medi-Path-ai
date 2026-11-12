<script setup lang="ts">
// Temporary stand-in with the same props as <HospitalFinder> from
// src/features/hospitals/ (@ley-21, T21 PR 4). When it lands, only the import
// in ResultView.vue changes (AGENTS.md section 2).
defineProps<{ department: string }>()
</script>

<template>
  <section class="hospital-finder" data-test="hospital-finder" :data-department="department">
    <h3>주변 병원</h3>
    <p>병원 찾기 화면이 이 자리에 들어옵니다(진료과 코드 {{ department }}).</p>
  </section>
</template>

<style scoped>
.hospital-finder {
  border: 1px dashed #aaa;
  border-radius: 12px;
  padding: 12px;
}
</style>
