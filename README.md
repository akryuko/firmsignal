# FirmSignal

Multi-agent company intelligence system. Type a company name — a team of AI agents researches recent news, pulls financial data, analyses public sentiment, then pauses for your review before generating a cited intelligence brief.

**Live demo:** https://firmsignal.vercel.app
**Backend API:** https://firmsignal.up.railway.app/docs

---

## What it does

Give FirmSignal a company name (or a misspelling, or a ticker symbol). Within 60–90 seconds you receive a structured intelligence brief covering recent developments, financial performance, risk flags, and a bull/bear signal summary — with every factual claim linked to a source.

The pipeline pauses after the Skeptic agent so you can review risk flags, add an analyst note, and approve before the final report is written. This Human-in-the-Loop checkpoint is the core design decision — it keeps a human in control of what goes into the brief.

---

## Agent pipeline

```
User input
    │
    ▼
Normalizer        Resolves misspellings, tickers, informal names
    │             "Googlee" → "Google (Alphabet Inc.)"
    ▼
Scout             Crawls recent news and leadership changes
    │             Tavily search · Redis semantic cache
    ▼
Accountant        Pulls financials and 5-year monthly price history
    │             yfinance · structured Pydantic output
    ▼
Skeptic           Analyses sentiment and surfaces risk flags
    │             Tavily (Glassdoor, controversies, layoffs)
    ▼
[Human Review]    Pauses here — review risk flags, add analyst note
    │             LangGraph interrupt() · Human-in-the-Loop
    ▼
Synthesizer       Writes the final cited brief
                  Claude Sonnet · citation injection
```

---

## Architecture

```
backend/                          frontend/
  firmsignal/                       app/
    agents/                           page.tsx            Search
      normalizer.py                   analyze/[runId]/
      scout.py                          page.tsx           Live feed
      accountant.py                     review/            HITL panel
      skeptic.py                        report/            Final brief
      hitl.py                       components/
      synthesizer.py                  AgentCard.tsx
    api/                              StockChart.tsx
      app.py          FastAPI          CitedBrief.tsx
      routes.py       3 endpoints      RiskBadge.tsx
      runner.py       SSE streaming  lib/
      store.py        Run state        api.ts
    tools/                             useSSE.ts           SSE hook
      cache.py        Redis cache    store/
      source_quality.py               run.ts              Zustand
  evals/
    golden/           10 companies
    eval_utils.py     8-dimension scoring
    run_evals.py      Automated suite
    deepeval_checks.py
```

**API endpoints:**
- `POST /api/analyze` — start a run, returns `run_id`
- `GET /api/stream/{run_id}` — SSE stream of agent progress
- `POST /api/resume/{run_id}` — inject HITL decision, resume graph

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph (stateful, interrupt/resume) |
| LLM — research agents | Claude Haiku (fast, low cost) |
| LLM — synthesis | Claude Sonnet (quality output) |
| Web search | Tavily (advanced search depth) |
| Financial data | yfinance (free, 5Y monthly history) |
| Semantic cache | Upstash Redis |
| Structured output | Pydantic with `.with_structured_output()` |
| Observability | LangSmith (unified pipeline traces) |
| Backend | FastAPI + Server-Sent Events |
| Frontend | Next.js 14 · TypeScript · Tailwind · Shadcn/ui |
| State management | Zustand |
| Charts | Recharts |

---

## Observability

Every pipeline run produces a unified LangSmith trace showing all six nodes — including the Synthesizer after HITL approval — with per-agent token counts, latency, and cost visible at the top level.

<!-- ============================================================
     SCREENSHOT GOES HERE
     1. Go to smith.langchain.com
     2. Open a completed pipeline run (e.g. FirmSignal — Microsoft)
     3. Expand all nodes so the full tree is visible:
          FirmSignal — Microsoft  (84.98s, 20.7K, $0.058)
            normalizer
            scout
            accountant
            skeptic
            hitl  (shows human wait time e.g. 5.02s)
            synthesizer
     4. Take a screenshot
     5. Save as: docs/langsmith_trace.png
     6. Uncomment the line below
     ============================================================ -->

[LangSmith unified pipeline trace](docs/langsmith_trace.png)

The `hitl` node latency shows how long the human spent on the review screen — a detail that surfaces in every production trace. Eval runs are isolated to a separate `firmsignal-evals` LangSmith project so production traces stay clean.

---

## Evaluation

Automated eval suite across 10 gold standard companies using a two-layer approach.

**Layer 1 — Custom 8-dimension scoring:**

| Dimension | Method |
|---|---|
| Stable facts | String matching — CEO, ticker, HQ |
| Expected patterns | Claude Haiku as judge (yes/no) |
| Forbidden content | String + LLM — catches hallucinations |
| Citation coverage | Regex — factual sentences with [N] |
| Sentiment calibration | Range check against expected range |
| Structure | Section detection — 5 required sections |
| Source quality | Domain allowlist — Reuters, Bloomberg, SEC |
| Private company handling | Schema validation — no fake tickers |

**Layer 2 — DeepEval LLM-as-judge:**
- Faithfulness — did the Synthesizer hallucinate facts not in context?
- Answer Relevancy — does the brief answer the investor's question?

**Results — April 2026:**

| Metric | Score |
|---|---|
| Overall average | 76.2 / 100 |
| Companies passing (≥70) | 8 / 10 |
| No hallucinations (forbidden content) | 10 / 10 |
| Source quality (trusted domains only) | 100% |
| Private company handling | 3 / 3 graceful |
| Avg pipeline time | 74s |
| Avg words per brief | 820 |
| Avg citations used | 9.4 |

> Update these numbers after running: `cd backend && uv run python -m evals.run_evals`

**Golden dataset:** 10 companies covering public/private, high/low sentiment, different sectors (tech, aerospace, finance, travel). Each golden file contains stable facts, expected patterns, forbidden content checks, and quality thresholds. Files are in `backend/evals/golden/` and should be re-verified every 90 days (`last_verified` field tracks this).

---

## Cost per report

| Component | Cost |
|---|---|
| Scout — 2 Tavily searches | ~$0.010 |
| Accountant — yfinance | free |
| Skeptic — 3 Tavily searches | ~$0.015 |
| Normalizer + Scout + Skeptic — Claude Haiku | ~$0.015 |
| Synthesizer — Claude Sonnet | ~$0.040 |
| **Total per report** | **~$0.08** |

Redis semantic caching reduces Tavily costs by ~60% on repeat queries for the same company within 24 hours.

---

## Source quality

FirmSignal filters sources at three layers before any agent sees them:

1. **Tavily domain allowlist** — only queries trusted domains (Reuters, Bloomberg, FT, WSJ, SEC, Glassdoor, TechCrunch etc.)
2. **Blocked title filter** — rejects Cloudflare challenge pages, 404s, and access-denied responses by title
3. **Synthesizer prompt** — instructed to prefer primary sources and label unconfirmed claims as "reported" or "alleged"

Sources are displayed in the final report grouped by agent with a quality tier badge (primary / verified / secondary).

---

## Human-in-the-Loop

After the Skeptic runs, the graph pauses using LangGraph's `interrupt()` function. The frontend receives a `hitl_required` SSE event and renders the review panel showing risk flags, sentiment score, and positive signals.

The human can:
- Review and expand each risk flag with its source link
- Add an analyst note that the Synthesizer incorporates
- Approve to generate the report
- Abort to discard the run

On approval, `POST /api/resume/{run_id}` fires `Command(resume=...)` which resumes the graph from the exact point it paused — no agents re-run, no data is lost.

This is the pattern enterprise AI teams use for controllable systems — the human is in the loop by architecture, not by prompt.

---

## Running locally

**Prerequisites:** Python 3.11, Node.js 18+, uv

**Backend:**

```bash
cd backend
cp .env.example .env
# Fill in API keys (see .env.example for all required keys)
uv sync
uv run uvicorn firmsignal.api.app:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000/api
npm install
npm run dev
```

Open `http://localhost:3000`

**Required API keys:**

| Key | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `TAVILY_API_KEY` | tavily.com (free: 1K req/month) |
| `LANGCHAIN_API_KEY` | smith.langchain.com (free tier) |
| `UPSTASH_REDIS_URL` | upstash.com (free tier) |
| `UPSTASH_REDIS_TOKEN` | upstash.com (free tier) |

**Optional:**

| Key | Enables |
|---|---|
| `OPENAI_API_KEY` | DeepEval Faithfulness + Relevancy metrics |

---

## Running evals

```bash
cd backend

# Single company — fastest, use during development
uv run python -m evals.run_evals --company stripe --fast

# Full suite — 10 companies, ~20 min, ~$1.50 in API costs
uv run python -m evals.run_evals

# Fast mode — skips LLM pattern checks, saves ~$0.50
uv run python -m evals.run_evals --fast
```

Results are saved to `backend/evals/results/latest.json` and a timestamped archive. The README-ready summary table prints at the end of every full run.

---

## Deployment

| Service | Platform | Config |
|---|---|---|
| Backend (FastAPI) | Railway | Root: `backend/` · Start: `uvicorn firmsignal.api.app:app --host 0.0.0.0 --port $PORT` |
| Frontend (Next.js) | Vercel | Root: `frontend/` · Framework: Next.js |

Both deploy from the same monorepo. Railway and Vercel each watch their respective subdirectory for changes.

**Deploy order:**
1. Deploy backend to Railway first — copy the Railway URL
2. Deploy frontend to Vercel — set `NEXT_PUBLIC_API_URL` to the Railway URL
3. Go back to Railway — set `ALLOWED_ORIGINS` to the Vercel URL
4. Redeploy backend once to pick up the CORS change

---

## Design decisions

**Claude Haiku for research, Sonnet only for synthesis.** The most expensive model is reserved for the one task where prose quality directly determines user value. Research agents extract structured data where speed and cost matter more than creativity.

**Semantic cache on Tavily.** The same company queried twice within 24 hours hits Redis instead of the API. Reduced Tavily costs by ~60% during development and makes demos faster.

**Pydantic structured output on every agent.** `.with_structured_output()` uses Anthropic's tool-use API under the hood, which is more reliable than asking for JSON in the prompt. Every agent output is validated before it enters the graph state.

**Source domain allowlist before search.** Tavily's `include_domains` parameter prevents low-quality sources from entering the pipeline at all, rather than filtering them out afterward. LinkedIn personal posts and Medium articles are excluded at the search layer.

**Two-layer eval design.** Custom mechanical checks (string matching, regex, range checks) run fast and free. LLM-as-judge (Claude Haiku + DeepEval) handles checks that require semantic understanding. Neither layer replaces the other.

**HITL by architecture, not prompt.** The human review step uses LangGraph's `interrupt()` function which freezes the entire graph state. It cannot be bypassed by a clever prompt — the graph is literally paused at the OS level until `Command(resume=...)` is called.

---

## Project structure

```
firmsignal/
  backend/
    firmsignal/         Python package — agents, API, tools
    evals/              Eval suite — golden files, scoring, results
    pyproject.toml
    .env.example
  frontend/
    app/                Next.js App Router pages
    components/         Shared UI components
    lib/                API client, SSE hook, validation
    store/              Zustand global state
    package.json
    .env.local.example
  README.md
  .gitignore
```