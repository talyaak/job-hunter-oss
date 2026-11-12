export type SyncPhase = 'idle' | 'scraping' | 'enriching' | 'filtering' | 'completed' | 'failed'

export interface SyncLiveState {
  phase: SyncPhase
  run_id: number | null
  raw_count: number
  passed_count: number
  processed: number
  hard_rejected: number
  deduped: number
  llm_rejected: number
  current_job: string | null
  error_message: string | null
  sources?: Record<string, number>
}

export type IngestionTrigger = 'cron' | 'manual'
export type IngestionStatus = 'running' | 'completed' | 'failed'

export interface IngestionRun {
  id: number
  trigger: IngestionTrigger
  started_at: string
  finished_at: string | null
  status: IngestionStatus
  raw_count: number
  passed_count: number
  error_message: string | null
}

export interface SyncStartResponse {
  run_id: number
}

export interface SyncStatusResponse {
  current: IngestionRun | null
  last_completed: IngestionRun | null
}
