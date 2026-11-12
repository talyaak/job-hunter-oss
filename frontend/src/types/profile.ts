export interface UserProfile {
  id: number
  cv_filename: string | null
  has_cv: boolean
  has_profile: boolean
  has_resume_file: boolean
  updated_at: string | null
}

export interface ApplyProfile {
  full_name: string
  first_name: string
  last_name: string
  email: string
  phone: string
  location: string
  linkedin_url: string
  github_url: string
  portfolio_url: string
  has_resume_file: boolean
}
