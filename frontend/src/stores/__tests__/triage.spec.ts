import { setupServer } from 'msw/node'
import { createPinia, setActivePinia } from 'pinia'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { createHandlers } from '../../mocks/handlers'
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
})
