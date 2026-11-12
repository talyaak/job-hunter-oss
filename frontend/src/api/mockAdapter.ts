import type { Lead, LeadFilters, LeadListResponse, LeadPatch } from '../types/lead'
import type { RejectFilters, RejectListResponse, UnscoredProcessResult } from '../types/reject'
import type { SyncStartResponse, SyncStatusResponse, IngestionRun } from '../types/sync'
import type { CoverLetterOptions, CoverLetterResponse } from '../types/coverLetter'
import type { UserProfile, ApplyProfile } from '../types/profile'
import type {
  LinkedinPostedAgoResponse,
  LinkedinSaveParams,
  LinkedinSaveResponse,
  LinkedinSearchFilters,
  LinkedinSearchFiltersParams,
  LinkedinSearchItem,
  LinkedinSearchHistoryEntry,
  LinkedinSearchParams,
  LinkedinSearchResponse,
} from '../types/search'

const sampleLeads: Lead[] = [
  {
    id: 1,
    date_posted: '2026-06-10',
    job_title: 'Full Stack Developer',
    company: 'PayFlow',
    platform_source: 'glassdoor',
    submission_method: 'Glassdoor Fast Apply',
    recruiter_type: 'direct',
    workplace_type: 'hybrid',
    company_size: '51-200',
    product_vertical: 'Fintech',
    contact_name: null,
    contact_linkedin_url: null,
    contact_email: 'careers@payflow.io',
    match_reason: 'Recruiter score 91% — hard reqs 92, domain 88, seniority 90. Strong TypeScript/Vue stack fit for a Berlin fintech.',
    match_evaluation: {
      final_score: 91,
      scores: {
        hard_requirements_score: { value: 92, explanation: 'Meets mid-level IC and location requirements.' },
        domain_similarity_score: { value: 88, explanation: 'Fintech payments domain aligns with prior experience.' },
        seniority_score: { value: 90, explanation: '3-5 year band matches demonstrated tenure.' },
        technology_score: { value: 85, explanation: 'TypeScript, Vue, Node proven on CV.' },
        signal_score: { value: 78, explanation: 'Ownership and CI/CD mentioned in profile.' },
      },
      strengths: ['Strong TypeScript/Vue stack fit', 'Fintech domain overlap'],
      gaps: ['No explicit Kubernetes experience'],
      deal_breakers: [],
    },
    stack_match: ['TypeScript', 'Vue.js', 'Node.js'],
    relevance_score: 91,
    application_status: 'saved',
    job_url: 'https://www.glassdoor.com/job-listing/full-stack-developer',
    description: 'Build payment APIs with TypeScript and Vue.',
    created_at: '2026-06-11T10:00:00Z',
  },
  {
    id: 2,
    date_posted: '2026-06-09',
    job_title: 'Software Engineer',
    company: 'GameLab',
    platform_source: 'linkedin',
    submission_method: 'LinkedIn Easy Apply',
    recruiter_type: 'direct',
    workplace_type: 'remote',
    company_size: '11-50',
    product_vertical: 'Gaming',
    contact_name: 'Dana Cohen',
    contact_linkedin_url: 'https://linkedin.com/in/danacohen',
    contact_email: null,
    match_reason: 'Remote mid-level engineer role aligned with Node.js backend experience.',
    stack_match: ['Node.js', 'TypeScript'],
    relevance_score: 88,
    application_status: 'saved',
    job_url: 'https://www.linkedin.com/jobs/view/123456',
    description: 'Node.js game services team.',
    created_at: '2026-06-11T10:05:00Z',
  },
  {
    id: 3,
    date_posted: '2026-06-08',
    job_title: 'TypeScript Developer',
    company: 'HealthBridge',
    platform_source: 'google',
    submission_method: 'Company Website',
    recruiter_type: 'third_party',
    workplace_type: 'onsite',
    company_size: '201-500',
    product_vertical: 'Health',
    contact_name: null,
    contact_linkedin_url: null,
    contact_email: 'hr@healthbridge.com',
    match_reason: 'TypeScript-heavy product team in Berlin; healthcare vertical match.',
    stack_match: ['TypeScript', 'Vue.js'],
    relevance_score: 86,
    application_status: 'saved',
    job_url: 'https://boards.greenhouse.io/healthbridge/jobs/123',
    description: 'Greenhouse posting for TS developer.',
    created_at: '2026-06-11T10:10:00Z',
  },
]

let leads = [...sampleLeads]
let syncRun: IngestionRun | null = null
let syncTimer: ReturnType<typeof setTimeout> | null = null

function profileFromStorage(): UserProfile {
  const raw = sessionStorage.getItem('jh_profile')
  if (!raw) {
    return { id: 1, cv_filename: null, has_cv: false, has_profile: false, has_resume_file: false, updated_at: null }
  }
  return JSON.parse(raw)
}

const mockApplyProfile: ApplyProfile = {
  full_name: 'Alex Morgan',
  first_name: 'Alex',
  last_name: 'Morgan',
  email: 'alex@example.com',
  phone: '+1-555-000-0000',
  location: 'Berlin, Germany',
  linkedin_url: 'https://www.linkedin.com/in/example',
  github_url: 'https://github.com/example',
  portfolio_url: 'https://github.com/example',
  has_resume_file: true,
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

let mockHistory: LinkedinSearchHistoryEntry[] = []
let mockFilters: LinkedinSearchFilters = { ignore_text: '', removed_keys: [], updated_at: null }

export const mockApi = {
  async getLeads(filters: LeadFilters = {}): Promise<LeadListResponse> {
    await delay(100)
    const filtered = filters.status
      ? leads.filter((l) => l.application_status === filters.status)
      : leads
    const offset = filters.offset ?? 0
    const limit = filters.limit ?? filtered.length
    const items = filtered.slice(offset, offset + limit)
    const counts = {
      total: leads.length,
      saved: leads.filter((l) => l.application_status === 'saved').length,
      applied: leads.filter((l) => l.application_status === 'applied').length,
      hidden: leads.filter((l) => l.application_status === 'hidden').length,
    }
    return { items, total: filtered.length, counts }
  },

  async getRejects(_filters: RejectFilters = {}): Promise<RejectListResponse> {
    await delay(100)
    if (_filters.scored === false) {
      return { items: [], total: 0 }
    }
    return {
      items: [
        {
          id: 101,
          job_title: 'Senior Backend Engineer',
          company: 'BigCorp',
          job_url: 'https://example.com/job/1',
          reject_stage: 'llm_score',
          reject_reason: 'Recruiter score 72% — below 85% threshold',
          relevance_score: 72,
          stack_match: ['Python', 'AWS'],
          created_at: new Date().toISOString(),
        },
        {
          id: 102,
          job_title: 'WordPress Developer',
          company: 'ContentWorks',
          job_url: 'https://example.com/job/2',
          reject_stage: 'embedding_filter',
          reject_reason: 'Embedding similarity 0.221 < threshold 0.350',
          relevance_score: 22,
          stack_match: [],
          created_at: new Date().toISOString(),
        },
      ],
      total: 2,
    }
  },

  async processUnscored(_mode: string, _limit: number): Promise<UnscoredProcessResult> {
    await delay(200)
    return {
      pending: 0,
      processed: 0,
      leads_created: 0,
      scored_rejected: 0,
      hard_filtered: 0,
      dismissed: 0,
      deduped: 0,
      quota_stopped: false,
      remaining: 0,
    }
  },

  async getLead(id: number): Promise<Lead> {
    const lead = leads.find((l) => l.id === id)
    if (!lead) throw new Error('Not found')
    return lead
  },

  async patchLead(id: number, body: LeadPatch): Promise<Lead> {
    const idx = leads.findIndex((l) => l.id === id)
    if (idx < 0) throw new Error('Not found')
    leads[idx] = { ...leads[idx], application_status: body.application_status }
    return leads[idx]
  },

  async generateCoverLetter(id: number, options: CoverLetterOptions): Promise<CoverLetterResponse> {
    await delay(400)
    const lead = leads.find((l) => l.id === id)
    if (!lead) throw new Error('Not found')
    const extra = options.instructions ? `\n\n[Instructions: ${options.instructions}]` : ''
    return {
      lead_id: id,
      cover_letter: `Dear Hiring Team at ${lead.company},\n\nI am excited to apply for the ${lead.job_title} role. My background aligns with your stack (${lead.stack_match.slice(0, 3).join(', ')}) and the strengths identified in my profile.${extra}\n\n[${options.tone} / ${options.length} mock draft — connect API for live generation.]`,
    }
  },

  async startSync(): Promise<SyncStartResponse> {
    if (syncRun?.status === 'running') throw new Error('Sync already running')
    syncRun = {
      id: Date.now(),
      trigger: 'manual',
      started_at: new Date().toISOString(),
      finished_at: null,
      status: 'running',
      raw_count: 0,
      passed_count: 0,
      error_message: null,
    }
    if (syncTimer) clearTimeout(syncTimer)
    syncTimer = setTimeout(() => {
      if (!syncRun) return
      syncRun = {
        ...syncRun,
        status: 'completed',
        finished_at: new Date().toISOString(),
        raw_count: 47,
        passed_count: 3,
      }
    }, 3000)
    return { run_id: syncRun.id }
  },

  async getSyncStatus(): Promise<SyncStatusResponse> {
    const last =
      syncRun?.status === 'completed'
        ? syncRun
        : syncRun?.status === 'failed'
          ? syncRun
          : null
    return {
      current: syncRun?.status === 'running' ? syncRun : null,
      last_completed: last,
    }
  },

  async getProfile(): Promise<UserProfile> {
    return profileFromStorage()
  },

  async getApplyProfile(): Promise<ApplyProfile> {
    await delay(80)
    return mockApplyProfile
  },

  async uploadProfile(cv: File | null, profileMd: File | null): Promise<UserProfile> {
    const p: UserProfile = {
      id: 1,
      cv_filename: cv?.name ?? null,
      has_cv: !!cv,
      has_profile: !!profileMd,
      has_resume_file: !!cv,
      updated_at: new Date().toISOString(),
    }
    sessionStorage.setItem('jh_profile', JSON.stringify(p))
    return p
  },

  async searchLinkedin(params: LinkedinSearchParams): Promise<LinkedinSearchResponse> {
    await delay(400)
    const items: LinkedinSearchItem[] = [
      { job_title: `${params.q} Engineer`, company: 'PayFlow', location: params.location, job_url: 'https://www.linkedin.com/jobs/view/1001', date_posted: '2026-10-09', lead_status: 'saved' },
      { job_title: `Senior ${params.q}`, company: 'GameLab', location: null, job_url: 'https://www.linkedin.com/jobs/view/1002', date_posted: '2026-10-07', lead_status: 'applied' },
      { job_title: `${params.q} Lead`, company: 'HealthBridge', location: 'Herzliya', job_url: 'https://www.linkedin.com/jobs/view/1003', date_posted: null, lead_status: null },
    ]
    return { query: params.q, location: params.location, hours: params.hours, total: items.length, items }
  },

  async linkedinPostedAgo(jobUrl: string): Promise<LinkedinPostedAgoResponse> {
    await delay(300)
    return { posted_ago: jobUrl.endsWith('/1001') ? '21 hours ago' : null }
  },

  async saveLinkedinJob(body: LinkedinSaveParams): Promise<LinkedinSaveResponse> {
    await delay(300)
    return { lead_id: 1000, application_status: body.status }
  },

  async getLinkedinSearchHistory(): Promise<LinkedinSearchHistoryEntry[]> {
    await delay(100)
    return mockHistory
  },

  async recordLinkedinSearch(search: LinkedinSearchResponse): Promise<LinkedinSearchHistoryEntry[]> {
    await delay(100)
    const entry: LinkedinSearchHistoryEntry = {
      term: search.query,
      location: search.location,
      hours: search.hours,
      fetched_at: new Date().toISOString(),
      new_urls: null,
      response: search,
    }
    const sameSearch = (e: LinkedinSearchHistoryEntry) =>
      e.term.toLowerCase() === entry.term.toLowerCase() &&
      e.location.toLowerCase() === entry.location.toLowerCase() &&
      e.hours === entry.hours
    mockHistory = [entry, ...mockHistory.filter((e) => !sameSearch(e))].slice(0, 10)
    return mockHistory
  },

  async clearLinkedinSearchHistory(): Promise<void> {
    await delay(100)
    mockHistory = []
  },

  async getLinkedinSearchFilters(): Promise<LinkedinSearchFilters> {
    await delay(100)
    return mockFilters
  },

  async saveLinkedinSearchFilters(body: LinkedinSearchFiltersParams): Promise<LinkedinSearchFilters> {
    await delay(100)
    mockFilters = { ignore_text: body.ignore_text, removed_keys: body.removed_keys, updated_at: new Date().toISOString() }
    return mockFilters
  },
}
