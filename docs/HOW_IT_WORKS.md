# How Job Hunter works (a short learning guide)

Read this once, or let your assistant teach you the relevant part at each onboarding step. Each section ends with a
"Try it" so you learn by looking at your own data.

## 1. The big picture
Every few hours the app **collects** job postings, **throws out** the obvious mismatches cheaply, then asks an AI to
**score** the rest against *your* CV. Jobs above your threshold become **leads**; everything else is kept in
**Rejected** with the reason, so you can see and tune what is happening.

```
collect -> cheap filters -> dedupe -> (AI pre-filters, shadow) -> examples from your past choices -> AI scores -> your threshold -> lead
```
*Try it:* press **Sync Now**, then compare the **Leads** and **Rejected** tabs.

## 2. Why filters come before the AI
AI calls cost time and quota. Rules are free: blocked title words (`Manager`), contractor roles, wrong location,
duplicates. They run first, so the AI only sees jobs worth reading. The price: a rule is blunt. If a good job is
rejected by a keyword you set too broadly, you lose it silently, which is why every rejection records its reason.
*Try it:* in **Rejected**, filter by stage `hard_title` and read the reasons. Any keyword rejecting jobs you like?

## 3. What "scoring" means
The AI reads the job and your CV and rates five things from 0-100: **hard requirements** (do you meet the must-haves),
**domain fit**, **seniority fit**, **technology fit**, and **positive signals** (ownership, scale, impact). It also
writes strengths, gaps and interview risks.

**The final percentage is computed by code, not by the AI**, as a weighted average using *your* weights. This matters:
language models are fluent but can slip on arithmetic (we saw one mis-add its own total), and a deterministic formula
makes scores comparable and tunable.
*Try it:* open a lead and hover the score; change the weights in preferences and see future scores shift.

## 4. Your preferences vs your secrets
- **Preferences** (in the app): what you want: titles, location, blocked words, threshold, weights, schedule, and a
  plain-language "wants and avoids" note the AI reads. They live in the local database.
- **Secrets** (`.env`): the Gemini key, optional LinkedIn cookie, ntfy topic, access token. Never committed, never shown
  in full by the app.
The plain-language note is the most powerful single setting: the AI follows it when judging fit.

## 5. Embeddings and "learning from your choices" (RAG)
An **embedding** turns text into numbers so similar meaning means nearby numbers. The app embeds your CV and each job.
Two uses:
1. **Similarity pre-filter**: skip jobs nowhere near your profile. It runs in **shadow mode** first: it only counts
   what it *would* reject, so you can check it before trusting it.
2. **Calibration examples (RAG = retrieval-augmented generation)**: before scoring a job, the app finds the most similar
   jobs you already have scores/decisions for and shows them to the AI as context. Your past choices steer future scores.
*Try it:* keep marking leads Saved / Hidden / Applied; the examples get better with use.

## 6. The cost of being wrong
Two errors exist: **missing a good job** (threshold too high, filters too broad) and **drowning in bad ones**
(threshold too low). You tune with evidence: the **Rejected** tab, `GET /api/insights/summary`, and the `tips` and
`calibrate` skills. Change one thing at a time and check after two sweeps.

## 7. LinkedIn and being a good citizen
Guest scraping reads public job pages. An optional `li_at` cookie lets the app fetch the full description of each job.
Scraping can violate site terms and get rate limited, so volumes are capped, requests are spaced with jitter, and you
can switch LinkedIn off. See [LINKEDIN.md](LINKEDIN.md).

## 8. The private tunnel and why there is a token
`cloudflared` makes your local dashboard reachable on a random public URL. Anyone who guesses it would reach your CV
and leads, so the **backend refuses every API call without your access token**. Requests from your own machine are
trusted automatically; anything arriving through the tunnel needs the token (delivered as a link, then swapped for a
cookie). The API and dev server only listen on `127.0.0.1`. See [TUNNEL.md](TUNNEL.md).
*Try it:* `npm run doctor -- --sweep --tunnel` shows 401 without the token and 200 with it.

## 9. Privacy: what leaves your machine
Job text and CV excerpts go to Google Gemini for scoring. Nothing else about you is sent, except scraping requests,
optional ntfy pushes, and tunnel traffic while the tunnel runs. See [PRIVACY.md](PRIVACY.md).

## 10. Where to look when you are curious
| Question | Look at |
|---|---|
| What happened in the last sweep? | **Rejected** tab; `GET /api/insights/summary` |
| Is everything healthy? | `npm run doctor:full` |
| What does the AI actually see? | `backend/app/llm/prompts/score.md` |
| How is the score computed? | `backend/app/filter/evaluation.py` |
| What do the filters do? | `backend/app/filter/hard_reject.py`, `location_reject.py` |
| The whole flow | [ARCHITECTURE.md](ARCHITECTURE.md) |
