<script setup lang="ts">
import { ref } from 'vue'

import { useTriageStore } from '../stores/triage'
import ProgressSteps from './ProgressSteps.vue'

const store = useTriageStore()
const draft = ref('')

async function submit(text = draft.value) {
  draft.value = ''
  await store.send(text)
}
</script>

<template>
  <section class="chat">
    <p v-if="store.chat.length === 0" class="hint">
      어디가 어떻게 불편한지 편하게 적어 주세요. 예: "어제부터 열이 나고 기침과 가래가 나와요"
    </p>
    <ol class="lines">
      <li v-for="(line, i) in store.chat" :key="i" :class="line.from">{{ line.text }}</li>
    </ol>
    <div v-if="store.questions.length" class="choices">
      <template v-for="q in store.questions" :key="q.question_id">
        <button v-for="c in q.choices ?? []" :key="c" type="button" :disabled="store.busy" @click="submit(c)">
          {{ c }}
        </button>
      </template>
    </div>
    <form @submit.prevent="submit()">
      <textarea v-model="draft" maxlength="500" rows="3" aria-label="증상 입력" placeholder="증상을 입력하세요" />
      <button type="submit" :disabled="store.busy || !draft.trim()">보내기</button>
    </form>
    <ProgressSteps v-if="store.busy" :step="store.step" />
    <p v-if="store.error" class="error" role="status">
      {{ store.error }}
      <button v-if="store.canRetry" type="button" data-test="retry" @click="store.retry()">다시 시도</button>
    </p>
  </section>
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lines {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.lines li {
  padding: 10px 12px;
  border-radius: 12px;
  max-width: 85%;
}
.user {
  align-self: flex-end;
  background: #2f6fde;
  color: #fff;
}
.assistant {
  align-self: flex-start;
  background: #f1f3f6;
}
.choices {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
form {
  display: flex;
  gap: 8px;
}
textarea {
  flex: 1;
  font: inherit;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid #ccc;
  resize: vertical;
}
button {
  font: inherit;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #2f6fde;
  background: #fff;
  color: #2f6fde;
}
form button {
  background: #2f6fde;
  color: #fff;
}
.hint,
.error {
  color: #555;
  font-size: 14px;
}
</style>
