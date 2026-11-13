// Conversation state. The typed text lives only in memory for display and is
// never written to storage (SPEC section 6: raw symptoms are not stored).
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api } from '../api/client'
import type { EmergencyNotice, FollowUpQuestion, TriageResult } from '../api/types'

export type Step = 'idle' | 'extract' | 'analyze' | 'done'

// After this long without an answer, the progress moves from 'extract' to 'analyze'.
const ANALYZE_AFTER_MS = 1500

export interface ChatLine {
  from: 'user' | 'assistant'
  text: string
}

export const useTriageStore = defineStore('triage', () => {
  const sessionId = ref<string | null>(null)
  const stage = ref<'chat' | 'result'>('chat')
  const chat = ref<ChatLine[]>([])
  const questions = ref<FollowUpQuestion[]>([])
  const emergency = ref(false)
  const emergencyNotice = ref<EmergencyNotice | null>(null)
  const result = ref<TriageResult | null>(null)
  const busy = ref(false)
  const error = ref<string | null>(null)
  const step = ref<Step>('idle')
  // Last sent text, kept in memory only so a failed send can be retried.
  const lastText = ref<string | null>(null)
  const canRetry = computed(() => error.value !== null && lastText.value !== null)

  async function send(text: string, isRetry = false) {
    const trimmed = text.trim()
    if (!trimmed || busy.value) return
    busy.value = true
    error.value = null
    lastText.value = trimmed
    step.value = 'extract'
    const timer = setTimeout(() => {
      if (busy.value) step.value = 'analyze'
    }, ANALYZE_AFTER_MS)
    if (!isRetry) chat.value.push({ from: 'user', text: trimmed })
    try {
      if (!sessionId.value) sessionId.value = (await api.createSession()).session_id
      const res = await api.sendMessage(sessionId.value, trimmed)
      emergency.value = res.emergency
      emergencyNotice.value = res.emergency_notice
      if (res.status === 'needs_more_info') {
        questions.value = res.questions
        res.questions.forEach((q) => chat.value.push({ from: 'assistant', text: q.text }))
      } else {
        questions.value = []
        result.value = await api.getResult(res.result_url)
        stage.value = 'result'
      }
      step.value = 'done'
      lastText.value = null
    } catch (e) {
      error.value = e instanceof Error ? e.message : '요청을 처리하지 못했습니다.'
      step.value = 'idle'
    } finally {
      clearTimeout(timer)
      busy.value = false
    }
  }

  async function retry() {
    if (lastText.value) await send(lastText.value, true)
  }

  function reset() {
    sessionId.value = null
    stage.value = 'chat'
    chat.value = []
    questions.value = []
    emergency.value = false
    emergencyNotice.value = null
    result.value = null
    error.value = null
    step.value = 'idle'
    lastText.value = null
  }

  return {
    sessionId,
    stage,
    chat,
    questions,
    emergency,
    emergencyNotice,
    result,
    busy,
    error,
    step,
    canRetry,
    send,
    retry,
    reset,
  }
})
