export interface ScoreDimension {
  value: number
  explanation: string
}

export interface MatchEvaluation {
  extracted?: {
    must_have_requirements: string[]
    nice_to_have_requirements: string[]
    technologies: string[]
    seniority_expectation: string
    domain_expectation: string
  }
  scores?: Record<string, ScoreDimension>
  final_score?: number
  strengths?: string[]
  gaps?: string[]
  deal_breakers?: string[]
  resume_recommendations?: string[]
  interview_risks?: string[]
}
