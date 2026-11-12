# CV optimizer

A skill (`.claude/skills/cv-optimizer`) that turns your CV into a role-specific, defensible CV, plus a prompt pack you
can reuse with any coding agent.

## What it does

1. **Intake**: summarises your background, exact tenure, evidenced vs. listed skills, under-sold strengths, risks.
2. **Role analysis**: must-have vs. nice-to-have, an evidence table per requirement, a three-bucket keyword table
   (documented / needs evidence / do not add), a **five-dimension fit score computed by `scripts/fit_score.py`** and a
   decision (proceed / stretch / caution), plus targeted clarifying questions.
3. **Tailoring**: headline, summary, bullet rewrites with named patterns, skills reordering, honest gap bridging,
   tenure and industry-label handling.
4. **Final CV** (only when you ask): assembled from your original CV + the job + your answers, QC-checked, saved to
   `cv_optimizer/output/` with a changelog.

Principles: truth over exaggeration, evidence beats buzzwords, results over duties, ATS awareness without promises,
transferable skills when real, ask instead of assume. Nothing unverified is written: it is marked `[TO CONFIRM]`.

## Using it

- With Claude Code: ask "optimise my CV for this lead" (the skill can read a lead from `GET /api/leads/{id}`) or
  "should I apply to this job?" and paste the description.
- To regenerate: after Step 3 say "generate the final CV". It writes a new file and never touches your master CV.
- With another agent: paste the prompts from `.claude/skills/cv-optimizer/prompts/` in order (README there explains).

## Helper script

```bash
python .claude/skills/cv-optimizer/scripts/fit_score.py score --dims must_haves=35,keywords=65,experience=40,tools=35,domain=75
python .claude/skills/cv-optimizer/scripts/fit_score.py tenure --start 2023-01
```

## Rules and checklists

[writing rules](../.claude/skills/cv-optimizer/references/writing-rules.md) ·
[QC checklist](../.claude/skills/cv-optimizer/references/qc-checklist.md) ·
[method notes](../.claude/skills/cv-optimizer/references/method.md)
