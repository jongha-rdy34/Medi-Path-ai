import type { ApiError, MessageResponse, Session, TriageResult } from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiRequestError extends Error {
  constructor(
    public status: number,
    public body: ApiError,
  ) {
    super(body.message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await res.json()
  if (!res.ok) throw new ApiRequestError(res.status, body as ApiError)
  return body as T
}

export const api = {
  createSession: () => request<Session>('/api/triage/sessions', { method: 'POST' }),
  sendMessage: (sessionId: string, text: string) =>
    request<MessageResponse>(`/api/triage/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  getResult: (resultUrl: string) => request<TriageResult>(resultUrl),
}
