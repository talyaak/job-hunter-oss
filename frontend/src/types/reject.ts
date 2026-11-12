export type RejectStage = 'location' | 'hard_title' | 'dedupe' | 'embedding_filter' | 'gemma_filter' | 'llm_score'

export interface Reject {
  id: number
  job_title: string | null
  company: string | null
  job_url: string
  reject_stage: RejectStage
  reject_reason: string
  relevance_score: number | null
  stack_match: string[]
  created_at: string
}

export interface RejectListResponse {
  items: Reject[]
  total: number
}

export interface RejectFilters {
  min_score?: number
  max_score?: number
  stage?: RejectStage | ''
  scored?: boolean
}

export interface UnscoredProcessResult {
  pending: number
  processed: number
  leads_created: number
  scored_rejected: number
  hard_filtered: number
  dismissed: number
  deduped: number
  quota_stopped: boolean
  remaining: number
}
