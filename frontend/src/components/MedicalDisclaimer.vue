<script setup lang="ts">
defineProps<{ text?: string }>()
</script>

<template>
  <p class="disclaimer" data-test="disclaimer">
    {{ text ?? '이 결과는 의학적 진단이 아니며 참고용 안내입니다. 정확한 진단과 치료는 의료진에게 받으세요.' }}
  </p>
</template>

<style scoped>
.disclaimer {
  font-size: 13px;
  color: #555;
  border-top: 1px solid #ddd;
  padding-top: 12px;
}
</style>
