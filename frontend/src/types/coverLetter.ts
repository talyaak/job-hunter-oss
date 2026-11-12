export interface CoverLetterOptions {
  tone: 'professional' | 'concise' | 'warm'
  length: 'short' | 'medium'
  instructions?: string
}

export interface CoverLetterResponse {
  lead_id: number
  cover_letter: string
}
