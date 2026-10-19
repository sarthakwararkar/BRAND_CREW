# Iterative Marketing & Brand Ecosystem — Project Spec

> Hand this file to your coding assistant. Build phase by phase (see Section 12). Verify every CrewAI API call against the **current CrewAI docs** before using it — memory APIs (scopes, slices, storage) have changed between versions. Pin the CrewAI version in `requirements.txt` once you confirm what works.

---

## 1. Overview

A multi-agent content crew built with **CrewAI** that produces landing pages, blog posts, and social campaigns every week while keeping strict brand consistency. The system gets better each run because it remembers what was approved, what performed, and what the editor keeps correcting.

**Core idea:** value comes from memory. Week 4 output must be measurably more on-brand and better-targeted than week 1.

### Goals
- Weekly run produces: 1 landing page (React/HTML), 1 blog post, a social campaign (LinkedIn, X, Instagram captions)
- Brand rules live in a **read-only shared memory scope** that agents cannot overwrite
- Human approves outputs, rates them, and logs performance; the system learns from that
- Visual consistency checked by a vision-capable agent (logo, palette, past posts)

### Non-goals (v1)
- Auto-publishing to social platforms
- Multi-tenant / multi-brand support (design scopes so it can be added later)
- Real-time analytics ingestion (manual entry first, API later)

---

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Agent framework | CrewAI (Python 3.11+) |
| Backend API | FastAPI + Uvicorn |
| Frontend dashboard | React + Vite + Tailwind |
| App database | MongoDB (runs, outputs, ratings, metrics) |
| Agent memory storage | CrewAI memory backend (default local storage; configurable embedder) |
| LLMs | Cheap/fast model for research + strategy; stronger model for Copywriter + Brand Editor; vision-capable model for Visual Brand Agent |
| Observability | Logfire (optional) or CrewAI verbose logs |
| Search tool | Serper / Tavily / similar (configurable via env) |

---

## 3. Architecture

```
React Dashboard  ──►  FastAPI  ──►  Crew Runner (CrewAI)
                         │               │
                         ▼               ▼
                     MongoDB        Memory (scoped)
              (runs, ratings,     /company/knowledge  (read-only)
               metrics, assets)   /marketing/seo
                                  /marketing/campaigns
                                  /editor/private
                                  /visual/brand
```

### Weekly flow

```
1. Strategist          reads past campaign lessons → proposes this week's plan
2. SEO Researcher      keyword research + gaps → writes to /marketing/seo
3. Copywriter          drafts landing copy, blog, social posts
4. Visual Brand Agent  checks assets/layout vs brand visuals (vision model)
5. Brand Editor        enforces tone + guidelines, returns corrected drafts
6. Landing Page Builder turns approved copy into React/HTML page
7. ── HUMAN APPROVAL GATE (dashboard) ──
8. Performance Analyst reads ratings/metrics → writes distilled lessons to /marketing/campaigns
```

Steps 1–6 run in one crew kickoff. Step 7 is manual. Step 8 runs as a **second, separate crew** triggered after the user submits ratings/metrics.

---

## 4. Folder Structure

```
brand-crew/
├── README.md
├── BRAND_CREW_SPEC.md
├── .env.example
├── .gitignore
├── docker-compose.yml              # optional: mongo + backend + frontend
│
├── backend/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint
│   │   ├── config.py               # env + settings (models, keys, paths)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── runs.py             # start run, get run, list runs
│   │   │   ├── approvals.py        # approve/reject outputs
│   │   │   ├── feedback.py         # ratings + metrics submission
│   │   │   ├── brand.py            # view/seed brand knowledge
│   │   │   └── memory.py           # inspect memory entries (read-only debug)
│   │   ├── db/
│   │   │   ├── client.py           # Mongo connection
│   │   │   └── models.py           # Pydantic models (Run, Output, Rating, Metric)
│   │   ├── crew/
│   │   │   ├── __init__.py
│   │   │   ├── weekly_crew.py      # builds + kicks off the weekly content crew
│   │   │   ├── analysis_crew.py    # builds + kicks off the performance crew
│   │   │   ├── agents.py           # agent factory functions
│   │   │   ├── tasks.py            # task factory functions
│   │   │   ├── llms.py             # per-agent LLM selection
│   │   │   ├── config/
│   │   │   │   ├── agents.yaml     # role, goal, backstory per agent
│   │   │   │   └── tasks.yaml      # description, expected_output per task
│   │   │   └── schemas.py          # Pydantic output schemas for tasks
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── setup.py            # create Memory, scopes, slices
│   │   │   ├── scopes.py           # scope path constants
│   │   │   ├── seed.py             # one-time seed of /company/knowledge
│   │   │   └── lessons.py          # helpers to store distilled lessons w/ dates
│   │   ├── tools/
│   │   │   ├── search_tool.py      # web/SEO keyword search wrapper
│   │   │   ├── image_tool.py       # loads/describes brand images for vision agent
│   │   │   ├── brand_checker.py    # banned-phrase + tone rule checks (deterministic)
│   │   │   └── page_export.py      # writes generated landing page files
│   │   └── services/
│   │       ├── run_service.py      # orchestrates run lifecycle + status
│   │       └── scoring.py          # computes brand-consistency score per output
│   ├── data/
│   │   ├── brand/
│   │   │   ├── brand_guidelines.md     # voice, tone, do/don't, audience
│   │   │   ├── banned_phrases.txt
│   │   │   ├── product_facts.md
│   │   │   └── visual/
│   │   │       ├── logo.png
│   │   │       ├── palette.json
│   │   │       └── sample_posts/        # past post screenshots
│   │   ├── outputs/                     # generated artifacts per run
│   │   │   └── <run_id>/
│   │   │       ├── landing/index.html
│   │   │       ├── blog.md
│   │   │       ├── social.json
│   │   │       └── editor_report.md
│   │   └── memory_store/                # CrewAI local memory storage (gitignored)
│   └── tests/
│       ├── test_scopes.py              # read-only enforcement, slice behavior
│       ├── test_brand_checker.py
│       ├── test_weekly_crew.py         # mocked-LLM smoke test
│       └── test_lessons.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/client.js
│       ├── pages/
│       │   ├── Dashboard.jsx           # list of weekly runs + scores
│       │   ├── RunDetail.jsx           # outputs, editor report, approve/reject
│       │   ├── Feedback.jsx            # rating + metrics form
│       │   ├── BrandKnowledge.jsx      # view brand guidelines (edit = deliberate action)
│       │   └── MemoryExplorer.jsx      # browse memory per scope (read-only)
│       ├── components/
│       │   ├── RunStatus.jsx
│       │   ├── OutputPreview.jsx       # blog / social / landing iframe preview
│       │   ├── RatingWidget.jsx        # 👍/👎 + notes
│       │   ├── MetricsForm.jsx
│       │   ├── ScoreTrend.jsx          # brand-consistency score across weeks
│       │   └── ScopeBadge.jsx
│       └── styles/
│
└── docs/
    ├── memory-design.md
    └── weekly-runbook.md
```

---

## 5. Agents

Define in `crew/config/agents.yaml`. Each agent gets its own LLM via `llms.py`.

| # | Agent | Role | LLM tier | Tools | Memory access |
|---|---|---|---|---|---|
| 1 | **Strategist** | Plans the week's campaign angle from past lessons | Cheap/fast | — | Reads `/marketing/campaigns`, `/marketing/seo`, `/company/knowledge` |
| 2 | **SEO Researcher** | Keyword analysis, search intent, content gaps | Cheap/fast | search_tool | Reads/writes `/marketing/seo` |
| 3 | **Copywriter** | Drafts landing copy, blog, social posts | Strong | — | Reads `/marketing/campaigns` + `/company/knowledge` (slice) |
| 4 | **Visual Brand Agent** | Checks logo, palette, imagery, layout vs brand | Vision-capable | image_tool | Reads `/visual/brand` + `/company/knowledge` (slice) |
| 5 | **Brand Editor** | Enforces tone/guidelines, returns corrected drafts + report | Strong | brand_checker | Reads `/editor/private` + `/company/knowledge` (slice); writes only `/editor/private` |
| 6 | **Landing Page Builder** | Converts approved copy into React/HTML page | Strong (code) | page_export | Reads `/company/knowledge`, `/visual/brand` |
| 7 | **Performance Analyst** *(analysis crew)* | Turns ratings + metrics into "what worked and why" | Cheap/fast or mid | — | Writes `/marketing/campaigns` |

### Agent notes
- **Strategist** must output a structured weekly plan (`WeeklyPlan` schema): theme, target audience segment, primary keyword, 2–3 angles to try, 1 angle to avoid (from past failures), channels.
- **Brand Editor** must output both corrected content *and* an `EditorReport` (list of violations, severity, fixes applied, brand score 0–100).
- **Visual Brand Agent** must be a no-op if no visual assets exist, and say so in its output.
- Set `allow_delegation=False` on all agents in v1 to keep behavior predictable.

---

## 6. Tasks

Define in `crew/config/tasks.yaml`. Use Pydantic `output_pydantic` for structured tasks.

| Task | Agent | Context (depends on) | Output |
|---|---|---|---|
| `plan_week` | Strategist | — | `WeeklyPlan` |
| `research_keywords` | SEO Researcher | plan_week | `SEOBrief` (keywords, intent, outline suggestions, gaps) |
| `draft_content` | Copywriter | plan_week, research_keywords | `ContentDraft` (landing copy, blog md, social posts) |
| `check_visuals` | Visual Brand Agent | draft_content | `VisualReport` (pass/fail, issues, suggested fixes) |
| `edit_for_brand` | Brand Editor | draft_content, check_visuals | `EditedContent` + `EditorReport` |
| `build_landing_page` | Landing Page Builder | edit_for_brand | HTML/React files written to `data/outputs/<run_id>/landing/` |
| `analyze_performance` *(analysis crew)* | Performance Analyst | ratings + metrics payload | `Lessons` list → stored in memory |

Run the weekly crew with `Process.sequential`.

---

## 7. Memory Design (core of the project)

### Scope layout

| Scope path | Writer | Readers | Contents |
|---|---|---|---|
| `/company/knowledge` | **Human only** (seeded via `memory/seed.py`) | All agents, **read-only** | Brand voice, banned phrases, audience, product facts |
| `/marketing/seo` | SEO Researcher | Researcher, Strategist, Copywriter | Keywords tried, rankings, gaps |
| `/marketing/campaigns` | Performance Analyst | Strategist, Copywriter | Distilled lessons: angles that worked/flopped + reasons |
| `/editor/private` | Brand Editor | Brand Editor | Recurring corrections it makes to the Copywriter |
| `/visual/brand` | Human (seed) | Visual Brand Agent, Landing Page Builder | Palette, logo rules, layout patterns, sample-post descriptions |

### Slices (read combinations)
- **Copywriter slice:** `/marketing/campaigns` + `/company/knowledge`
- **Brand Editor slice:** `/editor/private` + `/company/knowledge` (the shared scope is read-only)
- **Strategist slice:** `/marketing/campaigns` + `/marketing/seo` + `/company/knowledge`
- **Visual slice:** `/visual/brand` + `/company/knowledge`

### Implementation requirements
1. `memory/scopes.py` holds scope paths as constants — never hardcode strings elsewhere.
2. `memory/setup.py` builds the Memory object and exposes `get_slice(agent_name)` returning the right read scopes and write scope per agent.
3. Enforce read-only on `/company/knowledge` for every agent slice. Add a test that attempting to write to it from an agent slice fails or is blocked.
4. `seed.py` loads `data/brand/*` into `/company/knowledge` and `/visual/brand`. It is idempotent and only run deliberately (CLI command), never by a crew.
5. Configure the embedder via env (OpenAI / Gemini / Ollama) in `config.py`.

### What gets stored (to prevent memory pollution)
- ✅ Approved outputs (short summary + key angle, not full drafts)
- ✅ Distilled lessons from the Performance Analyst
- ✅ Recurring editor corrections (deduplicated)
- ✅ Keyword research results
- ❌ Raw rejected drafts
- ❌ Intermediate agent chatter

### Lesson format (stored via `memory/lessons.py`)
Every stored lesson includes structured text with metadata so recall can weigh recency:
```
date: 2026-10-18
week_id: 2026-W42
channel: blog | landing | linkedin | x | instagram
angle: "<short description>"
outcome: worked | flopped | mixed
evidence: "<rating / metric summary>"
why: "<analyst's reasoning>"
recommendation: "<what to repeat or avoid>"
```
The Strategist prompt must instruct: *prefer recent lessons; treat lessons older than ~8 weeks as weaker evidence.*

---

## 8. Feedback Loop (defines "success")

Memory can only recall what was stored, so success must be captured explicitly.

**Per output (blog, landing, each social post):**
- Rating: 👍 / 👎
- Free-text note (optional)
- Approval status: approved / needs changes / rejected

**Metrics (manual entry in v1):**
- Impressions, clicks, CTR, engagement, conversions (all optional)
- Source: manual form → stored in MongoDB

**Flow:** user submits feedback → backend triggers `analysis_crew` → Performance Analyst writes lessons to `/marketing/campaigns` → next week's Strategist reads them.

---

## 9. Data Models (MongoDB / Pydantic)

```python
class Run:
    id, week_id, status        # queued | running | awaiting_approval | approved | analyzed | failed
    plan: WeeklyPlan
    created_at, completed_at

class Output:
    id, run_id, type           # landing | blog | social_linkedin | social_x | social_instagram
    content_path / content
    editor_report: EditorReport
    brand_score: int           # 0-100
    visual_report: VisualReport | None
    approval: pending | approved | needs_changes | rejected

class Rating:
    output_id, thumbs: up|down, note

class Metric:
    output_id, impressions, clicks, ctr, engagement, conversions, recorded_at

class LessonRef:
    run_id, memory_scope, summary, created_at
```

---

## 10. API Endpoints (FastAPI)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/runs` | Start a weekly run (optional: theme override) |
| GET | `/api/runs` | List runs with status + brand scores |
| GET | `/api/runs/{id}` | Run detail with outputs and reports |
| POST | `/api/runs/{id}/approve` | Approve / reject / request changes per output |
| POST | `/api/runs/{id}/feedback` | Submit ratings + metrics; triggers analysis crew |
| GET | `/api/brand` | View current brand knowledge (read-only) |
| POST | `/api/brand/reseed` | Deliberate re-seed of `/company/knowledge` (protected) |
| GET | `/api/memory/{scope}` | Inspect stored entries for a scope (debug, read-only) |

Run crews in a background task and poll `GET /api/runs/{id}` for status (or use SSE for progress).

---

## 11. Frontend Dashboard

- **Dashboard:** table of weekly runs, status, average brand score; `ScoreTrend` chart showing score per week (this is the demo graph)
- **RunDetail:** tabs for Landing (iframe preview), Blog (markdown render), Social (cards per channel); shows Editor Report and Visual Report beside each; approve/reject buttons
- **Feedback:** rating widget + metrics form per output
- **BrandKnowledge:** read-only view of guidelines; edit requires an explicit "Update brand knowledge" action calling the reseed endpoint
- **MemoryExplorer:** browse entries by scope so you can see what the system learned

---

## 12. Build Phases

**Phase 1 — Skeleton (day 1)**
- Repo structure, env config, FastAPI hello, Mongo connection
- Seed brand files; implement `memory/setup.py` and scopes; test read-only enforcement

**Phase 2 — Core crew (days 2–3)**
- Strategist, SEO Researcher, Copywriter, Brand Editor with YAML configs
- `weekly_crew.py` running sequentially, outputs saved to `data/outputs/<run_id>/`
- `brand_checker.py` deterministic checks (banned phrases, length, required terms)

**Phase 3 — Memory loop (days 4–5)**
- Feedback endpoints, `analysis_crew.py`, Performance Analyst, `lessons.py`
- Verify week-2 run actually recalls week-1 lessons (log recalled entries)

**Phase 4 — Multimodal + builder (days 6–7)**
- Visual Brand Agent with vision model + `image_tool.py`
- Landing Page Builder + page export

**Phase 5 — Dashboard (days 8–10)**
- React pages, approval flow, score trend, memory explorer

**Phase 6 — Polish**
- Tests, logging, cost tracking per run, README + demo script

---

## 13. Acceptance Criteria

- [ ] A weekly run completes end-to-end and produces landing page, blog, and social posts
- [ ] No agent can write to `/company/knowledge` (test proves it)
- [ ] After submitting feedback for run N, run N+1's Strategist output references at least one lesson from run N
- [ ] Brand Editor output includes a violations list and a 0–100 score; scores are stored per output
- [ ] Brand score trend over 4 simulated weeks is visible in the dashboard
- [ ] Rejected drafts are not stored in long-term memory
- [ ] Stored lessons carry dates; Strategist prompt weighs recency
- [ ] Each agent uses its configured LLM tier (verify in logs)
- [ ] Run cost (tokens or $) is logged per run

---

## 14. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Memory pollution (noisy recall) | Store only approved outputs and distilled lessons; dedupe editor corrections |
| Brand drift | Guidelines in read-only scope; edits only via deliberate reseed |
| Stale lessons dominate | Date every lesson; recency instruction in Strategist prompt; periodic pruning script |
| Cost growth with weekly runs | Cheap models for research/strategy/analysis; strong models only for Copywriter and Editor; cap max iterations |
| LLM ignores brand rules | Add deterministic `brand_checker` tool + fail the task if banned phrases remain |
| CrewAI API changes | Pin version; wrap CrewAI memory calls in `memory/setup.py` so changes stay in one file |
| Weak evidence for "what worked" | Require evidence field in every lesson; mark low-data lessons as `mixed` |

---

## 15. Environment Variables (`.env.example`)

```
# LLMs
OPENAI_API_KEY=
GEMINI_API_KEY=
FAST_MODEL=
STRONG_MODEL=
VISION_MODEL=

# Embeddings for memory
EMBEDDER_PROVIDER=
EMBEDDER_MODEL=

# Tools
SEARCH_API_KEY=

# Infra
MONGODB_URI=mongodb://localhost:27017/brandcrew
MEMORY_STORAGE_PATH=./backend/data/memory_store
ADMIN_TOKEN=            # protects /api/brand/reseed
```

---

## 16. Instructions for the Coding Assistant

1. Read this whole spec first, then check the **current CrewAI docs** for memory scopes, slices, and read-only options. If a method named here doesn't exist, adapt and note the change in `docs/memory-design.md`.
2. Build in the phase order above; stop and summarize after each phase.
3. Keep all CrewAI memory calls inside `backend/app/memory/` so version changes are isolated.
4. Use YAML for agent/task definitions and Pydantic for all structured outputs.
5. Write tests for scope enforcement and the brand checker before wiring the UI.
6. Do not hardcode secrets, scope paths, or model names outside `config.py` and `scopes.py`.
