// Types for GET /api/hospitals (contracts/openapi.yaml, searchHospitals, contract 0.2.3).

export type Day = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun' | 'holiday'

export interface OpeningHours {
  day: Day
  open: string // HH:MM, Korea time
  close: string
  crosses_midnight: boolean
}

export interface Hospital {
  hospital_id: string
  name: string
  type: string
  address: string
  phone: string | null
  location: { lat: number; lng: number }
  distance_m: number
  department: string | null
  opening_hours: OpeningHours[]
  is_open_now: boolean | null
  has_night_hours: boolean
  has_weekend_hours: boolean
  has_emergency_room: boolean | null
}

export interface HospitalSearchResponse {
  total: number
  items: Hospital[]
  region: { sido: string; sigungu: string | null }
  department: { code: string; name: string; filter_applied: boolean; message: string | null }
  evaluated_at: string
  notice: string
}

export interface HospitalSearchParams {
  lat: number
  lng: number
  department: string
  radius?: number
  open_now?: boolean
  night?: boolean
  weekend?: boolean
  limit?: number
}

export interface ApiErrorBody {
  code: string
  message: string
  details?: { field: string; message: string }[]
}
