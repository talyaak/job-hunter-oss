export type PlatformSource = 'linkedin' | 'indeed' | 'glassdoor' | 'google'
export type RecruiterType = 'direct' | 'third_party'
export type WorkplaceType = 'remote' | 'hybrid' | 'onsite' | 'unknown'
import type { MatchEvaluation } from './evaluation'

export type ApplicationStatus = 'hidden' | 'saved' | 'applied'

export interface Lead {
  id: number
  date_posted: string | null
  job_title: string
  company: string
  platform_source: PlatformSource
  submission_method: string
  recruiter_type: RecruiterType
  workplace_type: WorkplaceType
  company_size: string
  product_vertical: string
  contact_name: string | null
  contact_linkedin_url: string | null
  contact_email: string | null
  match_reason: string
  match_evaluation?: MatchEvaluation
  stack_match: string[]
  relevance_score: number | null
  application_status: ApplicationStatus
  job_url: string
  description: string
  created_at: string
}

export interface LeadCounts {
  total: number
  saved: number
  applied: number
  hidden: number
}

export interface LeadListResponse {
  items: Lead[]
  total: number
  counts?: LeadCounts
}

export interface LeadPatch {
  application_status: ApplicationStatus
}

export interface LeadFilters {
  status?: string
  offset?: number
  limit?: number
}
