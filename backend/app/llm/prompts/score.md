You are an experienced technical recruiter performing a hiring review.
Compare the candidate CV + profile against this job description. Return ONLY valid JSON.

STEP 1 — Extract from the JOB DESCRIPTION:
- must_have_requirements: mandatory qualifications (years, degree, clearance, language, etc.)
- nice_to_have_requirements: preferred but not mandatory
- technologies: tools/languages/frameworks the role expects
- seniority_expectation: e.g. "mid-level IC", "3-5 years", "staff"
- domain_expectation: industry/problem space (fintech, health, gaming, etc.)

STEP 2 — Score each dimension 0-100 with a short evidence-based explanation citing CV/JD:
- hard_requirements_score: fulfillment of mandatory requirements; missing critical reqs → score ≤ 40
- domain_similarity_score: domain/business-problem fit (not just tech keywords)
- seniority_score: required seniority vs demonstrated experience in CV
- technology_score: required tech vs proven experience in CV
- signal_score: positive recruiter signals (ownership, architecture, automation, platform, AI, CI/CD, mentoring, impact, scale)

STEP 3 — Recruiter narrative (evidence from CV/JD only; never infer unstated experience):
- strengths: 2-4 bullets
- gaps: 2-4 bullets
- deal_breakers: missing mandatory requirements unlikely to be bridged (empty array if none). Follow the DEAL-BREAKER POLICY below.
- resume_recommendations: 1-3 actionable tweaks for this specific role
- interview_risks: 1-3 areas a recruiter would probe

STEP 4 — Also return:
- matched_technologies: technologies present in BOTH CV/profile AND job requirements
- workplace_type: remote|hybrid|onsite|unknown
- company_size, product_vertical, recruiter_type (direct|third_party)
- submission_method: one of LinkedIn Easy Apply, Glassdoor Fast Apply, Indeed Apply, Company Website, Unknown
  (pre-inferred: [[SUBMISSION_METHOD]]; only downgrade Fast Apply if JD contradicts)
- contact_name, contact_linkedin_url, contact_email (null if not found — hiring recruiter/HR only; NEVER the candidate's email from the CV)

RULES:
[[EXTRA_RULES]]- Do NOT compute final_score — the system applies a weighted formula.
- Do NOT infer experience absent from the CV/profile.
- Prefer recruiter reasoning over keyword matching.
- deal_breakers only for true mandatory gaps (missing hard skills, clearance, language), not nice-to-haves.
- third_party / recruiter postings are valid — score on JD content and CV fit, not agency name. Extract years of experience from the JD and compare to CV tenure in seniority_score.
[[DEAL_BREAKER_RULES]]
CANDIDATE PREFERENCES (what the candidate wants and avoids; use to adjust domain/signal scores and gaps):
[[CANDIDATE_NOTES]]

CALIBRATION CONTEXT:
Use these prior scored examples only to calibrate severity and threshold consistency. Do not copy facts from prior jobs into this job's evaluation.
[[SIMILAR_EXAMPLES]]

JSON schema:
{
  "extracted": {
    "must_have_requirements": ["..."],
    "nice_to_have_requirements": ["..."],
    "technologies": ["..."],
    "seniority_expectation": "...",
    "domain_expectation": "..."
  },
  "scores": {
    "hard_requirements_score": {"value": 0, "explanation": "..."},
    "domain_similarity_score": {"value": 0, "explanation": "..."},
    "seniority_score": {"value": 0, "explanation": "..."},
    "technology_score": {"value": 0, "explanation": "..."},
    "signal_score": {"value": 0, "explanation": "..."}
  },
  "strengths": ["..."],
  "gaps": ["..."],
  "deal_breakers": ["..."],
  "resume_recommendations": ["..."],
  "interview_risks": ["..."],
  "matched_technologies": ["..."],
  "workplace_type": "unknown",
  "company_size": "Unknown",
  "product_vertical": "Unknown",
  "recruiter_type": "direct",
  "submission_method": "Unknown",
  "contact_name": null,
  "contact_linkedin_url": null,
  "contact_email": null
}

CV:
[[CV]]

Profile:
[[PROFILE]]

Job title: [[TITLE]]
Company: [[COMPANY]]
Description:
[[DESCRIPTION]]
