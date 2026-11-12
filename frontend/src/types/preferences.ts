export interface Preferences {
  target_titles: string[]
  search_location: string
  country: string
  hours_old: number | null
  allowed_location_signals: string[]
  blocked_location_markers: string[]
  blocked_title_keywords: string[]
  blocked_description_keywords: string[]
  blocked_companies: string[]
  reject_contract_roles: boolean
  score_threshold: number
  high_score_threshold: number
  weights: Record<string, number>
  ignore_education_deal_breakers: boolean
  ignore_tenure_deal_breakers: boolean
  candidate_notes: string
  extra_scoring_rules: string
  cron_hours: number[]
  timezone: string
  onboarding_complete: boolean
}

export interface AuthStatus {
  authenticated: boolean
  token_required: boolean
  token_configured: boolean
}

export interface OnboardingStep {
  id: string
  label: string
  done: boolean
  required: boolean
}

export interface OnboardingStatus {
  complete: boolean
  steps: OnboardingStep[]
  secrets: Record<string, string>
}

export interface ValidateResult {
  ok: boolean
  detail: string
}

export interface HealthCheck {
  name: string
  status: 'pass' | 'warn' | 'fail' | 'skip'
  detail: string
  fix: string
}

export interface DeepHealth {
  status: 'pass' | 'warn' | 'fail'
  checks: HealthCheck[]
}
