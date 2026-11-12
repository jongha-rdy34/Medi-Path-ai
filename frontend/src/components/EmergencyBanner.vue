<script setup lang="ts">
import type { EmergencyNotice } from '../api/types'

defineProps<{ notice: EmergencyNotice }>()

const EGEN_URL = 'https://www.e-gen.or.kr/'
</script>

<template>
  <section class="emergency" role="alert" data-test="emergency-banner">
    <strong>{{ notice.message }}</strong>
    <ul>
      <li v-for="reason in notice.reasons" :key="reason">{{ reason }}</li>
    </ul>
    <div class="actions">
      <a class="call" :href="`tel:${notice.call_number}`">{{ notice.call_number }}에 전화하기</a>
      <!-- 응급의료포털(e-gen). 응급실 찾기 상세 주소는 이 세션에서 확인하지 못해 메인 주소를 씁니다(미검증). -->
      <a class="call" data-test="egen-link" :href="EGEN_URL" target="_blank" rel="noopener">가까운 응급실 찾기</a>
    </div>
  </section>
</template>

<style scoped>
.emergency {
  background: #b00020;
  color: #fff;
  padding: 16px;
  border-radius: 12px;
}
.emergency ul {
  margin: 8px 0;
  padding-left: 20px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.call {
  display: inline-block;
  margin-top: 4px;
  padding: 10px 16px;
  background: #fff;
  color: #b00020;
  border-radius: 8px;
  font-weight: 700;
  text-decoration: none;
}
</style>
