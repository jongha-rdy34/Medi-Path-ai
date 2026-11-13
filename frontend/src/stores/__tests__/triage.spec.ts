import { delay } from 'msw'
import { http, HttpResponse } from 'msw/http'
import { setupServer } from 'msw/node'
import { createPinia, setActivePinia } from 'pinia'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { createHandlers } from '../../mocks/handlers'
import examples from '../../mocks/examples.json'
import { useTriageStore } from '../triage'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
beforeEach(() => {
  server.use(...createHandlers())
  setActivePinia(createPinia())
})
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('triage store', () => {
  it('asks follow-up questions, then shows the result', async () => {
    const store = useTriageStore()

    await store.send('어제부터 열이 나요')
    expect(store.stage).toBe('chat')
    expect(store.questions.length).toBeGreaterThan(0)

    await store.send('설사도 해요')
    expect(store.stage).toBe('result')
    expect(store.result?.predictions).toHaveLength(3)
    expect(store.result?.emergency).toBe(false)
  })

  it('shows the emergency notice as soon as it is detected', async () => {
    const store = useTriageStore()

    await store.send('가슴이 아프고 숨이 차요')

    expect(store.emergency).toBe(true)
    expect(store.emergencyNotice?.call_number).toBe('119')
    expect(store.result?.emergency).toBe(true)
  })

  it('keeps the typed text only in memory and clears it on reset', async () => {
    const store = useTriageStore()
    await store.send('어제부터 열이 나요')

    store.reset()

    expect(store.chat).toEqual([])
    expect(store.sessionId).toBeNull()
  })

  it('shows the first progress step right after sending', async () => {
    server.use(
      http.post('*/api/triage/sessions/:id/messages', async () => {
        await delay(50)
        return HttpResponse.json(examples.message.resultReady)
      }),
      http.get('*/api/triage/sessions/:id/result', () => HttpResponse.json(examples.result.normal)),
    )
    const store = useTriageStore()

    const pending = store.send('열이 나요')
    await Promise.resolve()
    expect(store.step).toBe('extract')
    await pending
    expect(store.step).toBe('done')
  })

  it('offers a retry when the service is temporarily unavailable', async () => {
    let calls = 0
    server.use(
      http.post('*/api/triage/sessions/:id/messages', () => {
        calls += 1
        if (calls === 1) {
          return HttpResponse.json(
            { code: 'llm_unavailable', message: '증상 분석이 잠시 어렵습니다. 잠시 후 다시 시도해 주세요.' },
            { status: 503 },
          )
        }
        return HttpResponse.json(examples.message.resultReady)
      }),
      http.get('*/api/triage/sessions/:id/result', () => HttpResponse.json(examples.result.normal)),
    )
    const store = useTriageStore()

    await store.send('열이 나요')
    expect(store.error).toContain('다시 시도')
    expect(store.canRetry).toBe(true)

    await store.retry()
    expect(store.error).toBeNull()
    expect(store.stage).toBe('result')
    expect(calls).toBe(2)
  })
})

