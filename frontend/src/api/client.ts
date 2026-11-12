import type { Lead, LeadFilters, LeadListResponse, LeadPatch } from '../types/lead'
import type { RejectFilters, RejectListResponse, UnscoredProcessResult } from '../types/reject'
import type { SyncStartResponse, SyncStatusResponse } from '../types/sync'
import type { UserProfile, ApplyProfile } from '../types/profile'
import type {
  LinkedinPostedAgoResponse,
  LinkedinSaveParams,
  LinkedinSaveResponse,
  LinkedinSearchFilters,
  LinkedinSearchFiltersParams,
  LinkedinSearchHistoryEntry,
  LinkedinSearchParams,
  LinkedinSearchResponse,
} from '../types/search'
import type { CoverLetterOptions, CoverLetterResponse } from '../types/coverLetter'
import type {
  AuthStatus,
  DeepHealth,
  OnboardingStatus,
  Preferences,
  ValidateResult,
} from '../types/preferences'
import { mockApi } from './mockAdapter'

// Real API by default; set VITE_USE_MOCK=true for demos/screenshots with synthetic data.
const defaultPreferences: Preferences = {
  target_titles: ['Software Engineer'],
  search_location: 'Remote',
  country: '',
  hours_old: null,
  allowed_location_signals: [],
  blocked_location_markers: [],
  blocked_title_keywords: [],
  blocked_description_keywords: [],
  blocked_companies: [],
  reject_contract_roles: true,
  score_threshold: 80,
  high_score_threshold: 90,
  weights: {},
  ignore_education_deal_breakers: true,
  ignore_tenure_deal_breakers: true,
  candidate_notes: '',
  extra_scoring_rules: '',
  cron_hours: [10, 15, 19],
  timezone: '',
  onboarding_complete: true,
}

const useMock = import.meta.env.VITE_USE_MOCK === 'true'

function parseApiError(body: string): string {
  try {
    const data = JSON.parse(body) as { detail?: string | { msg?: string }[] }
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg
  } catch {
    /* plain text */
  }
  return body || 'Request failed'
}

export const UNAUTHORIZED_EVENT = 'jh:unauthorized'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: 'same-origin', ...init })
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  }
  if (!res.ok) {
    const body = await res.text()
    throw new Error(parseApiError(body) || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  getLeads(filters: LeadFilters = {}): Promise<LeadListResponse> {
    if (useMock) return mockApi.getLeads(filters)
    const params = new URLSearchParams()
    if (filters.status) params.set('status', filters.status)
    if (filters.offset != null) params.set('offset', String(filters.offset))
    if (filters.limit != null) params.set('limit', String(filters.limit))
    const q = params.toString() ? `?${params}` : ''
    return request(`/api/leads${q}`)
  },

  getRejects(filters: RejectFilters = {}): Promise<RejectListResponse> {
    if (useMock) return mockApi.getRejects(filters)
    const params = new URLSearchParams()
    if (filters.min_score != null) params.set('min_score', String(filters.min_score))
    if (filters.max_score != null) params.set('max_score', String(filters.max_score))
    if (filters.stage) params.set('stage', filters.stage)
    if (filters.scored === false) params.set('scored', 'false')
    const q = params.toString() ? `?${params}` : ''
    return request(`/api/rejects${q}`)
  },

  processUnscored(mode: 'auto' | 'score' | 'dismiss' = 'auto', limit = 50): Promise<UnscoredProcessResult> {
    if (useMock) return mockApi.processUnscored(mode, limit)
    const params = new URLSearchParams({ mode, limit: String(limit) })
    return request(`/api/rejects/unscored/process?${params}`, { method: 'POST' })
  },

  getLead(id: number): Promise<Lead> {
    if (useMock) return mockApi.getLead(id)
    return request(`/api/leads/${id}`)
  },

  patchLead(id: number, body: LeadPatch): Promise<Lead> {
    if (useMock) return mockApi.patchLead(id, body)
    return request(`/api/leads/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  generateCoverLetter(id: number, options: CoverLetterOptions): Promise<CoverLetterResponse> {
    if (useMock) return mockApi.generateCoverLetter(id, options)
    return request(`/api/leads/${id}/cover-letter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options),
    })
  },

  startSync(): Promise<SyncStartResponse> {
    if (useMock) return mockApi.startSync()
    return request('/api/sync', { method: 'POST' })
  },

  getSyncStatus(): Promise<SyncStatusResponse> {
    if (useMock) return mockApi.getSyncStatus()
    return request('/api/sync/status')
  },

  getProfile(): Promise<UserProfile> {
    if (useMock) return mockApi.getProfile()
    return request('/api/profile')
  },

  getApplyProfile(): Promise<ApplyProfile> {
    if (useMock) return mockApi.getApplyProfile()
    return request('/api/profile/apply')
  },

  uploadProfile(cv: File | null, profileMd: File | null): Promise<UserProfile> {
    if (useMock) return mockApi.uploadProfile(cv, profileMd)
    const form = new FormData()
    if (cv) form.append('cv', cv)
    if (profileMd) form.append('profile', profileMd)
    return request('/api/profile', { method: 'POST', body: form })
  },

  searchLinkedin(params: LinkedinSearchParams): Promise<LinkedinSearchResponse> {
    if (useMock) return mockApi.searchLinkedin(params)
    const query = new URLSearchParams({
      q: params.q,
      location: params.location,
      hours: String(params.hours),
    })
    return request(`/api/search/linkedin?${query}`)
  },

  linkedinPostedAgo(jobUrl: string): Promise<LinkedinPostedAgoResponse> {
    if (useMock) return mockApi.linkedinPostedAgo(jobUrl)
    const query = new URLSearchParams({ job_url: jobUrl })
    return request(`/api/search/linkedin/posted-ago?${query}`)
  },

  saveLinkedinJob(body: LinkedinSaveParams): Promise<LinkedinSaveResponse> {
    if (useMock) return mockApi.saveLinkedinJob(body)
    return request('/api/search/linkedin/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  getLinkedinSearchHistory(): Promise<LinkedinSearchHistoryEntry[]> {
    if (useMock) return mockApi.getLinkedinSearchHistory()
    return request('/api/search/linkedin/history')
  },

  recordLinkedinSearch(search: LinkedinSearchResponse): Promise<LinkedinSearchHistoryEntry[]> {
    if (useMock) return mockApi.recordLinkedinSearch(search)
    return request('/api/search/linkedin/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(search),
    })
  },

  clearLinkedinSearchHistory(): Promise<void> {
    if (useMock) return mockApi.clearLinkedinSearchHistory()
    return request('/api/search/linkedin/history', { method: 'DELETE' })
  },

  getLinkedinSearchFilters(): Promise<LinkedinSearchFilters> {
    if (useMock) return mockApi.getLinkedinSearchFilters()
    return request('/api/search/linkedin/filters')
  },

  saveLinkedinSearchFilters(body: LinkedinSearchFiltersParams): Promise<LinkedinSearchFilters> {
    if (useMock) return mockApi.saveLinkedinSearchFilters(body)
    return request('/api/search/linkedin/filters', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  // --- access gate -------------------------------------------------------
  getAuthStatus(): Promise<AuthStatus> {
    if (useMock) return Promise.resolve({ authenticated: true, token_required: false, token_configured: true })
    return request('/api/auth/status')
  },

  createSession(token: string): Promise<{ authenticated: boolean }> {
    return request('/api/auth/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
  },

  // --- preferences & onboarding -------------------------------------------
  getPreferences(): Promise<Preferences> {
    if (useMock) return Promise.resolve({ ...defaultPreferences })
    return request('/api/preferences')
  },

  savePreferences(body: Preferences): Promise<Preferences> {
    if (useMock) return Promise.resolve(body)
    return request('/api/preferences', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  getOnboardingStatus(): Promise<OnboardingStatus> {
    if (useMock) return Promise.resolve({ complete: true, steps: [], secrets: {} })
    return request('/api/onboarding/status')
  },

  setOnboardingEnv(body: Partial<Record<'gemini_api_key' | 'linkedin_cookie_string' | 'ntfy_topic' | 'serp_api_key', string>>): Promise<OnboardingStatus> {
    return request('/api/onboarding/env', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },

  generateNtfyTopic(): Promise<{ topic: string } & OnboardingStatus> {
    return request('/api/onboarding/ntfy-topic', { method: 'POST' })
  },

  validateOnboarding(kind: 'gemini' | 'linkedin'): Promise<ValidateResult> {
    return request(`/api/onboarding/validate/${kind}`, { method: 'POST' })
  },

  completeOnboarding(): Promise<OnboardingStatus> {
    return request('/api/onboarding/complete', { method: 'POST' })
  },

  getDeepHealth(probe = false): Promise<DeepHealth> {
    if (useMock) return Promise.resolve({ status: 'pass', checks: [] })
    return request(`/api/health/deep?probe=${probe}`)
  },
}
