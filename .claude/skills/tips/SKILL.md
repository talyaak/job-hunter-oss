---
name: tips
description: Coach the user on getting better leads from Job Hunter by analysing score distribution, rejects and run history, then proposing concrete changes to preferences, scorer rules, filters and search strategy. Use when the user asks for tips, tuning, "why am I getting bad/few leads", or wants to improve results.
---

# LLM tips and tuning

You analyse the user's own data and recommend changes. You **propose diffs and apply them only after the user agrees**.

## Gather
- `GET /api/insights/summary`: threshold, lead score histogram, reject counts by stage, near-miss count, top hard-filter
  reasons, sources, recent runs, current preferences. (Local requests need no token; otherwise send
  `Authorization: Bearer $ACCESS_TOKEN` read from `.env` without printing it.)
- `GET /api/rejects?stage=llm_score&min_score=<threshold-10>` for near misses; `GET /api/leads` for what passed.
- Skim 5-10 leads (`match_evaluation.gaps`, `deal_breakers`, `resume_recommendations`) and 5-10 near-miss rejects (their `reject_reason` and score; rejects have no dimension breakdown).

## Diagnose with these heuristics
| Signal | Likely cause | Suggestion |
|---|---|---|
| < 3 leads per sweep, many near misses (threshold-10 .. threshold-1) | threshold too high | lower by 5 and re-check after two sweeps |
| Many leads, user hides most | threshold too low or vague preferences | raise by 5; add "avoid" lines to `candidate_notes` |
| Top hard-filter reasons dominate rejects | blocked keywords too broad (they hide good roles) | narrow or remove the keyword |
| Wrong-seniority leads | no seniority signal | add to `candidate_notes` and `extra_scoring_rules` ("Prefer mid-level; penalise Principal/Staff") |
| Same company/role repeats | dedupe handles URL/fingerprint, check agencies | add to `blocked_companies` |
| raw_count tiny | titles/location too narrow | add 2-3 synonym titles; widen location or `hours_old` |
| Scores cluster 40-60 | CV lacks detail the scorer needs | add a profile PDF/notes; run the `cv-optimizer` skill |
| All scores 85+ | scorer too generous | add stricter `extra_scoring_rules`; raise threshold |
| Backend log line `[RAG Filter] ... shadow=N` is high while you like the leads that scored well | pre-filters not calibrated | keep shadow mode on; only enable filtering after reviewing |

## Tips for the user (share the relevant ones)
- Vague preferences make vague scores. Write concrete "wants/avoids" in plain language.
- Set a status on leads (saved / hidden / applied) consistently: calibration retrieves your previous decisions as examples.
- Start with a lower threshold for the first week, then tighten using the Rejected tab.
- Keep title keywords specific; blocklists should reject classes of roles, not single words that appear in good titles.
- Sweeps cost Gemini calls per job: fewer, sharper searches beat many broad ones.
- Re-run `cv-optimizer` for a specific lead before applying; its gap list is the same one the scorer found.
- Treat LinkedIn gently: low volumes, a fresh cookie only when needed.

## Output format
1. **What I see** (3-5 data points with numbers).
2. **Recommended changes** as a diff over `GET /api/preferences` (only changed fields), each with the reason and the
   expected effect.
3. Ask: "Apply these?" On yes, `PUT /api/preferences` with the full object (modify only the agreed fields), then say
   what to check after the next sweep.
Never change `ACCESS_TOKEN`, keys or the tunnel settings from this skill.
