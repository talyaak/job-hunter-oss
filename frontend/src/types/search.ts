import type { ApplicationStatus } from './lead'

export interface LinkedinSearchParams {
  q: string
  location: string
  hours: number
}

export interface LinkedinSearchItem {
  job_title: string
  company: string
  location: string | null
  job_url: string
  date_posted: string | null
  lead_status: ApplicationStatus | null
}

export interface LinkedinSearchResponse {
  query: string
  location: string
  hours: number
  total: number
  items: LinkedinSearchItem[]
}

export interface LinkedinPostedAgoResponse {
  posted_ago: string | null
}

export interface LinkedinSaveParams {
  job_title: string
  company: string
  job_url: string
  date_posted: string | null
  status: 'saved' | 'applied'
}

export interface LinkedinSaveResponse {
  lead_id: number
  application_status: ApplicationStatus
}

export interface LinkedinSearchHistoryEntry {
  term: string
  location: string
  hours: number
  fetched_at: string
  new_urls: string[] | null
  response: LinkedinSearchResponse
}

export interface LinkedinSearchFilters {
  ignore_text: string
  removed_keys: string[]
  updated_at: string | null
}

export interface LinkedinSearchFiltersParams {
  ignore_text: string
  removed_keys: string[]
}
