import type { ApiErrorBody, HospitalSearchParams, HospitalSearchResponse } from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class HospitalSearchError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
  }
}

/** GET /api/hospitals. Booleans are sent only when true (the contract defaults them to false). */
export async function searchHospitals(
  params: HospitalSearchParams,
  signal?: AbortSignal,
): Promise<HospitalSearchResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === false) continue
    query.set(key, String(value))
  }
  let res: Response
  try {
    res = await fetch(`${BASE}/api/hospitals?${query}`, { signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new HospitalSearchError(0, 'network_error', '네트워크 연결을 확인한 뒤 다시 시도하세요.')
  }
  const body = (await res.json().catch(() => null)) as HospitalSearchResponse | ApiErrorBody | null
  if (!res.ok) {
    const err = body as ApiErrorBody | null
    throw new HospitalSearchError(
      res.status,
      err?.code ?? 'unknown_error',
      err?.message ?? '병원 정보를 불러오지 못했어요. 잠시 후 다시 시도하세요.',
    )
  }
  return body as HospitalSearchResponse
}
