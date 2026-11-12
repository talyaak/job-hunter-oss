---
name: calibrate
description: Calibrate the score threshold and dimension weights by walking the user through a sample of scored leads and near-miss rejects, recording their judgement and suggesting settings. Use when the user says the scores feel off, after the first week of use, or when changing the scoring rules.
---

# Calibrate

Turn the user's taste into numbers. Work with real data; keep each question short.

1. Fetch about 20 items: 10 leads spread across the score range (`GET /api/leads`) and 10 rejects scored within 15
   points below the threshold (`GET /api/rejects?stage=llm_score&min_score=<threshold-15>&max_score=<threshold-1>`).
   Show for each lead: title, company, score, the five dimension scores, strengths and gaps (from `match_evaluation`). For rejects only the score, reason and stack are stored (no dimension breakdown), so show those.
2. Ask for a one-word verdict per item: **good**, **maybe**, **bad**. Do not argue; ask "why" only when the verdict
   contradicts a high or low score.
3. Compute: the score below which almost every verdict is bad/maybe -> proposed threshold; which dimension best
   separates good from bad (leads only, since rejects have no breakdown) -> propose raising its weight (weights are normalised to sum to 1, change by at most 0.10
   at a time); recurring complaints (seniority, domain, stack) -> proposed `candidate_notes` / `extra_scoring_rules`
   sentences.
4. Show the proposed `Preferences` diff (`score_threshold`, `high_score_threshold`, `weights`, notes) and the expected
   effect ("would have kept 6 of 8 good, dropped 5 of 6 bad"). Apply with `PUT /api/preferences` only after approval.
5. Tell the user to set lead statuses (saved / hidden / applied): those decisions are retrieved as calibration examples by the
   scorer.
