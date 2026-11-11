<script setup lang="ts">
import type { EmergencyNotice } from '../api/types'

defineProps<{ notice: EmergencyNotice }>()
</script>

<template>
  <section class="emergency" role="alert" data-test="emergency-banner">
    <strong>{{ notice.message }}</strong>
    <ul>
      <li v-for="reason in notice.reasons" :key="reason">{{ reason }}</li>
    </ul>
    <a class="call" :href="`tel:${notice.call_number}`">{{ notice.call_number }}에 전화하기</a>
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
