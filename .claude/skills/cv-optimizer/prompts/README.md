# Prompt pack

Reusable prompts for any coding agent (Claude Code, Cursor, etc.). Paste a prompt, replace the `<...>` slots, and
attach your CV text. Run them in order; each one builds on the previous output.

Shared preamble (put it at the top of every session):

> Use ONLY facts from my CV text and my answers. Never invent employers, dates, titles, tools, metrics or
> certifications. Mark anything unverified as `[TO CONFIRM]` and ask me. Compute totals with
> `python .claude/skills/cv-optimizer/scripts/fit_score.py` instead of by hand. Do not overwrite my master CV;
> write new files under `cv_optimizer/output/`.

| # | Prompt | Purpose |
|---|---|---|
| 1 | [01-intake.md](01-intake.md) | Understand the candidate before any rewriting |
| 2 | [02-role-analysis.md](02-role-analysis.md) | Requirements, keywords, evidence table, fit score |
| 3 | [03-bullet-rewrite.md](03-bullet-rewrite.md) | Rewrite experience bullets honestly |
| 4 | [04-summary-skills.md](04-summary-skills.md) | Headline, summary and skills section |
| 5 | [05-gap-bridging.md](05-gap-bridging.md) | Handle missing requirements truthfully |
| 6 | [06-qc.md](06-qc.md) | Quality-control audit |
| 7 | [07-final-cv.md](07-final-cv.md) | Assemble the final tailored CV |
