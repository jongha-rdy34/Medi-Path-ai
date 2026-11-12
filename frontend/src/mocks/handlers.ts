// MSW handlers that serve the contract examples verbatim (src/mocks/examples.json,
// generated from contracts/openapi.yaml). MSW 3 API: `msw/http` (README "Usage example").
import { http, HttpResponse } from 'msw/http'

import examples from './examples.json'

const EMERGENCY_WORDS = ['가슴', '숨이', '의식', '마비']

export function createHandlers() {
  const turns = new Map<string, number>()
  const ready = new Set<string>()
  const emergencyId = examples.message.emergency.session_id

  return [
    http.post('*/api/triage/sessions', () => HttpResponse.json(examples.session, { status: 201 })),

    http.post('*/api/triage/sessions/:id/messages', async ({ request, params }) => {
      const id = String(params.id)
      const { text } = (await request.json()) as { text: string }
      if (EMERGENCY_WORDS.some((w) => text.includes(w))) {
        ready.add(emergencyId)
        return HttpResponse.json(examples.message.emergency)
      }
      const n = (turns.get(id) ?? 0) + 1
      turns.set(id, n)
      if (n === 1) return HttpResponse.json(examples.message.needsMoreInfo)
      ready.add(id)
      return HttpResponse.json(examples.message.resultReady)
    }),

    http.get('*/api/triage/sessions/:id/result', ({ params }) => {
      const id = String(params.id)
      if (id === emergencyId && ready.has(id)) return HttpResponse.json(examples.result.emergency)
      if (ready.has(id)) return HttpResponse.json(examples.result.normal)
      return HttpResponse.json(examples.resultNotReady, { status: 409 })
    }),
  ]
}
