// Types for contracts/openapi.yaml (triage endpoints). Hospital types belong to
// src/features/hospitals/ (@ley-21, T21) and are not declared here.

export interface SymptomObservation {
  symptom_id: string
  severity?: 'mild' | 'moderate' | 'severe'
  duration_days?: number
}

export interface StructuredSymptoms {
  symptoms: SymptomObservation[]
}

export interface EmergencyNotice {
  reasons: string[]
  message: string
  call_number: '119'
}

export interface Session {
  session_id: string
  status: 'collecting' | 'result_ready'
  created_at: string
}

export interface FollowUpQuestion {
  question_id: string
  text: string
  choices?: string[]
}

interface MessageBase {
  session_id: string
  structured_symptoms: StructuredSymptoms
  emergency: boolean
  emergency_notice: EmergencyNotice | null
}

export type MessageResponse =
  | (MessageBase & { status: 'needs_more_info'; questions: FollowUpQuestion[] })
  | (MessageBase & { status: 'result_ready'; result_url: string })

export interface TriageResult {
  session_id: string
  emergency: boolean
  emergency_notice: EmergencyNotice | null
  predictions: { disease_id: string; disease_name_ko: string; probability: number }[]
  recommended_departments: { code: string; name_ko: string; reason: string }[]
  explanation: string
  structured_symptoms: StructuredSymptoms
  disclaimer: string
  model_version: string
  created_at: string
}

export interface ApiError {
  code: string
  message: string
}
