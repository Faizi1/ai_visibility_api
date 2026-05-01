# AI Visibility Intelligence API
## Complete Project Documentation
### What I Built · How It Works · How to Test It

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [What I Implemented](#2-what-i-implemented)
3. [How to Run the Project](#3-how-to-run-the-project)
4. [How to Test with Postman](#4-how-to-test-with-postman)
5. [How to Run Unit Tests](#5-how-to-run-unit-tests)
6. [API Endpoints Reference](#6-api-endpoints-reference)
7. [How the 3-Agent Pipeline Works](#7-how-the-3-agent-pipeline-works)
8. [Opportunity Score Formula](#8-opportunity-score-formula)
9. [Database Schema](#9-database-schema)
10. [Project Folder Structure](#10-project-folder-structure)
11. [Architecture Decisions](#11-architecture-decisions)

---

## 1. Project Overview

This is a **RESTful Flask API** that helps businesses understand how they appear in AI-generated answers (like ChatGPT, Claude, Perplexity).

**The problem it solves:** When someone asks ChatGPT "What is the best SEO tool?", which businesses get mentioned? This API figures that out, scores the opportunity, and tells the business what content to create to start appearing.

**Real-world use case:** A company like Frase.io wants to know — for the 20 most common questions people ask AI about SEO tools, does Frase appear in the answers? If not, what should they write/publish to fix that?

---

## 2. What I Implemented

### Core Features

| Feature | Status | Details |
|---|---|---|
| Flask App Factory pattern | ✅ Done | `create_app()` in `app/__init__.py` |
| SQLAlchemy database models | ✅ Done | 4 models with relationships |
| Flask-Migrate migrations | ✅ Done | Full migration history |
| 3 distinct AI agents | ✅ Done | Each in its own class/file |
| Structured JSON prompts | ✅ Done | Schema defined in every system prompt |
| Malformed LLM fallback | ✅ Done | Every agent has fallback logic |
| All 6 API endpoints | ✅ Done | With proper HTTP codes |
| Opportunity score formula | ✅ Done | 4-factor weighted formula |
| Real search volume data | ✅ Done | DataForSEO + smart simulation fallback |
| Rate limiting | ✅ Done | 5 pipeline runs/hour per IP |
| Unit tests (13 tests) | ✅ Done | All agents + score formula tested |
| Environment variable management | ✅ Done | `.env` + `python-dotenv` |
| Docker Compose | ✅ Done | One command deployment |
| Setup script | ✅ Done | `bash setup.sh` |
| Structured logging | ✅ Done | `structlog` with context binding |

### What Each Part Does

**Agents (the AI brain):**
- `app/agents/discovery.py` — Asks Claude to generate 10-20 realistic questions people ask AI about your business space
- `app/agents/scoring.py` — Asks Claude to simulate whether your domain would appear in an AI answer, then gets real search volumes
- `app/agents/recommendation.py` — Asks Claude to generate specific content recommendations for queries where you're invisible

**Pipeline (the conductor):**
- `app/services/pipeline.py` — Runs Agent 1 → Agent 2 → Agent 3 in sequence, saves everything to the database, handles partial failures

**API (the interface):**
- `app/api/profiles.py` — Create profiles, trigger pipeline, list queries, list recommendations
- `app/api/queries.py` — Re-score individual queries after publishing content

---

## 3. How to Run the Project

### Prerequisites
- Python 3.10 or higher
- An Anthropic API key (get one free at https://console.anthropic.com)

### Step-by-Step Setup

**Step 1 — Get the code**
```bash
git clone <your-repo-url>
cd ai_visibility_api
```

**Step 2 — Create a virtual environment**
```bash
python3 -m venv venv

# On Mac/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

You should see `(venv)` appear at the start of your terminal line.

**Step 3 — Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 4 — Add your API key**
```bash
cp .env.example .env
```

Now open `.env` in any text editor (Notepad, VS Code, etc.) and change:
```
ANTHROPIC_API_KEY=sk-ant-...
```
to your real Anthropic API key. Save the file.

**Step 5 — Set up the database**
```bash
export FLASK_APP=run.py          # Mac/Linux
# OR on Windows:
set FLASK_APP=run.py

flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

You should see a `dev.db` file appear in the project folder.

**Step 6 — Start the server**
```bash
python run.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

The API is now live at `http://localhost:5000`.

### Running with Docker (Alternative)

If you have Docker installed:
```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

docker-compose up --build
```

That's it — Docker handles everything else.

---

## 4. How to Test with Postman

### Import the Collection

1. Open Postman
2. Click **Import** (top left button)
3. Select the file: `AI_Visibility_API.postman_collection.json`
4. Click **Import**

You will see a collection called **"AI Visibility Intelligence API"** appear in your sidebar.

### Set the Base URL Variable

1. Click on the collection name in the sidebar
2. Click the **Variables** tab
3. Make sure `base_url` is set to `http://localhost:5000`
4. Click **Save**

### Run Requests in This Exact Order

The collection has automatic scripts that save UUIDs between requests, so you must run them in order:

---

#### STEP 1 — Create a Profile
**Open:** `1. Profiles` → `1.1 Create Profile (Frase)`

Click **Send**.

Expected response (201 Created):
```json
{
  "profile_uuid": "abc-123-def-456",
  "name": "Frase",
  "domain": "frase.io",
  "status": "created",
  "created_at": "2025-01-15T10:00:00Z"
}
```

The `profile_uuid` is **automatically saved** to the collection variables. All future requests use it automatically.

---

#### STEP 2 — Run the Pipeline
**Open:** `2. Pipeline` → `2.1 Run Pipeline ⚡`

Click **Send**.

> ⚠️ **This takes 15–45 seconds.** Do not cancel. The AI agents are running.

Expected response (200 OK):
```json
{
  "run_uuid": "xyz-789",
  "status": "completed",
  "queries_discovered": 15,
  "queries_scored": 15,
  "top_opportunity_queries": [
    {
      "query_text": "What is the best AI tool for writing SEO content briefs?",
      "opportunity_score": 0.8562,
      "visibility_status": "not_visible",
      "estimated_search_volume": 3200
    }
  ],
  "content_recommendations": [
    {
      "content_type": "comparison_page",
      "title": "Frase vs Surfer SEO: Which Tool Wins for Content Teams?",
      "priority": "high",
      "target_keywords": ["frase vs surfer seo", "ai content brief tool"]
    }
  ],
  "tokens_used": 4823
}
```

The `query_uuid` from the top query is also **automatically saved**.

---

#### STEP 3 — View All Queries
**Open:** `3. Queries` → `3.1 List All Queries`

Click **Send**.

See all discovered queries sorted by opportunity score (best opportunities first).

---

#### STEP 4 — Filter Queries
Try these filter requests:

- `3.2 Filter — High Opportunity` → only queries with score ≥ 0.6
- `3.3 Filter — Not Visible Queries` → only queries where you don't appear
- `3.5 Filter — Combined` → not visible AND high opportunity (most actionable!)

---

#### STEP 5 — View Recommendations
**Open:** `4. Recommendations` → `4.1 List All Recommendations`

Click **Send**.

See Agent 3's specific content recommendations with titles, rationale, and target keywords.

---

#### STEP 6 — Recheck a Query
**Open:** `3. Queries` → `3.7 Recheck Single Query`

Click **Send**.

This re-runs Agent 2 on one query. Useful after you've published content — check if the AI now mentions your domain.

---

### Testing Error Cases

Also test these to verify error handling works:

| Request | Expected |
|---|---|
| `1.3 Create Profile — Validation Error` | 400 with missing_fields |
| `1.4 Create Profile — Duplicate Domain` | 409 conflict |
| `1.6 Get Profile — Not Found` | 404 |
| `2.2 Run Pipeline — Profile Not Found` | 404 |
| `3.8 Recheck — Invalid UUID` | 404 |
| `4.2 Recommendations — Profile Not Found` | 404 |

---

## 5. How to Run Unit Tests

```bash
# Make sure virtual environment is active
source venv/bin/activate

# Run all tests
pytest tests/ -v
```

Expected output:
```
tests/test_agents.py::TestQueryDiscoveryAgent::test_returns_queries_on_valid_response PASSED
tests/test_agents.py::TestQueryDiscoveryAgent::test_falls_back_when_llm_returns_garbage PASSED
tests/test_agents.py::TestQueryDiscoveryAgent::test_falls_back_when_queries_key_missing PASSED
tests/test_agents.py::TestVisibilityScoringAgent::test_scores_not_visible_query_high PASSED
tests/test_agents.py::TestVisibilityScoringAgent::test_scores_visible_query_lower PASSED
tests/test_agents.py::TestVisibilityScoringAgent::test_handles_malformed_llm_output PASSED
tests/test_agents.py::TestContentRecommendationAgent::test_returns_recommendations_on_valid_response PASSED
tests/test_agents.py::TestContentRecommendationAgent::test_returns_empty_when_no_queries PASSED
tests/test_agents.py::TestContentRecommendationAgent::test_fallback_when_llm_crashes PASSED
tests/test_agents.py::TestOpportunityScore::test_not_visible_high_volume_scores_high PASSED
tests/test_agents.py::TestOpportunityScore::test_visible_low_volume_scores_low PASSED
tests/test_agents.py::TestOpportunityScore::test_score_always_between_0_and_1 PASSED
tests/test_agents.py::TestOpportunityScore::test_not_visible_always_beats_visible_same_conditions PASSED

13 passed in 1.23s
```

**Important:** Tests use mocked LLM calls — no real API key needed, runs in ~1 second.

---

## 6. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/profiles` | Register a new business |
| GET | `/api/v1/profiles/{uuid}` | Get profile + stats |
| POST | `/api/v1/profiles/{uuid}/run` | Trigger 3-agent pipeline |
| GET | `/api/v1/profiles/{uuid}/queries` | List queries (filterable) |
| GET | `/api/v1/profiles/{uuid}/recommendations` | List content recommendations |
| POST | `/api/v1/queries/{uuid}/recheck` | Re-score a single query |

### Query Filter Parameters

```
GET /api/v1/profiles/{uuid}/queries?min_score=0.5
GET /api/v1/profiles/{uuid}/queries?status=not_visible
GET /api/v1/profiles/{uuid}/queries?status=visible
GET /api/v1/profiles/{uuid}/queries?page=1&per_page=10
GET /api/v1/profiles/{uuid}/queries?status=not_visible&min_score=0.6
```

### Error Response Format (consistent across all endpoints)

```json
{
  "error": "not_found",
  "message": "Profile not found"
}
```

HTTP codes used: `200`, `201`, `400`, `404`, `409`, `429`, `500`

---

## 7. How the 3-Agent Pipeline Works

```
POST /api/v1/profiles/{uuid}/run
         │
         ▼
┌─────────────────────────────┐
│  Pipeline Orchestrator       │
│  (app/services/pipeline.py) │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  AGENT 1 — Query Discovery  │
│  app/agents/discovery.py    │
│                             │
│  Input:  business profile   │
│  Action: asks Claude to     │
│          generate 10-20     │
│          realistic queries  │
│  Output: list of questions  │
└─────────────────────────────┘
         │
         ▼ (for each query, isolated — 1 failure won't stop the rest)
┌─────────────────────────────┐
│  AGENT 2 — Visibility Score │
│  app/agents/scoring.py      │
│                             │
│  Input:  one query + domain │
│  Action: asks Claude        │
│          "would this domain │
│          appear in an AI    │
│          answer for this    │
│          query?"            │
│          + fetches real     │
│          search volume      │
│          from DataForSEO    │
│  Output: score 0.0–1.0      │
└─────────────────────────────┘
         │
         ▼ (only passes queries where domain is NOT visible)
┌─────────────────────────────┐
│  AGENT 3 — Recommendations  │
│  app/agents/recommendation  │
│                             │
│  Input:  top 5 gap queries  │
│  Action: asks Claude to     │
│          generate specific  │
│          content pieces     │
│  Output: recommendations    │
│          with titles,       │
│          keywords, priority │
└─────────────────────────────┘
         │
         ▼
   Save to database
   Return full result
```

### Failure Isolation

- If **Agent 1** fails → entire pipeline fails (no queries = nothing to do)
- If **Agent 2** fails for **one query** → that query is marked `unknown`, pipeline continues with other queries
- If **Agent 3** fails → queries are still saved and returned, just no recommendations
- If **LLM returns bad JSON** → fallback logic runs, pipeline never crashes

---

## 8. Opportunity Score Formula

Each query gets a score from 0.0 to 1.0. Higher = bigger opportunity.

```
score = (0.30 × volume_score)
      + (0.35 × gap_score)
      + (0.20 × ease_score)
      + (0.15 × intent_score)
```

| Factor | Weight | How It's Calculated |
|---|---|---|
| **Volume** | 30% | Log-scale of monthly searches, capped at 50k. Log scale because 100→1000 matters as much as 10k→100k |
| **Gap** | 35% | 1.0 = not appearing, 0.3 = unknown, 0.0 = already visible. Gap is the heaviest factor because it IS the opportunity |
| **Ease** | 20% | `1 - (competitive_difficulty / 100)`. Difficulty 30 = ease 0.70 |
| **Intent** | 15% | high intent = 1.0, medium = 0.6, low = 0.2. Comparison queries worth more |

**Example:**
```
Query: "Frase vs Surfer SEO — which is better?"
Volume: 3,200/month  → volume_score = 0.72
Visibility: not_visible → gap_score = 1.0
Difficulty: 45/100   → ease_score = 0.55
Intent: high         → intent_score = 1.0

score = (0.30 × 0.72) + (0.35 × 1.0) + (0.20 × 0.55) + (0.15 × 1.0)
      = 0.216 + 0.35 + 0.11 + 0.15
      = 0.826
```

---

## 9. Database Schema

Four tables, all using UUID primary keys:

```
business_profiles
├── uuid (PK)
├── name
├── domain (unique)
├── industry
├── description
├── competitors (JSON array)
├── status (created/running/completed/failed)
├── created_at
└── updated_at

pipeline_runs
├── uuid (PK)
├── profile_uuid (FK → business_profiles)
├── status (running/completed/failed)
├── queries_discovered
├── queries_scored
├── tokens_used
├── error_message
├── started_at
└── completed_at

discovered_queries
├── uuid (PK)
├── profile_uuid (FK → business_profiles)
├── run_uuid (FK → pipeline_runs)
├── query_text
├── estimated_search_volume
├── competitive_difficulty (0-100)
├── opportunity_score (0.0-1.0)
├── domain_visible (boolean)
├── visibility_status (visible/not_visible/unknown)
├── visibility_position (1, 2, 3... or null)
├── commercial_intent (high/medium/low)
└── discovered_at

content_recommendations
├── uuid (PK)
├── profile_uuid (FK → business_profiles)
├── query_uuid (FK → discovered_queries)
├── content_type (blog_post/landing_page/faq/comparison_page/guide)
├── title
├── rationale
├── target_keywords (JSON array)
├── priority (high/medium/low)
└── created_at
```

---

## 10. Project Folder Structure

```
ai_visibility_api/
│
├── run.py                          ← Start the server (python run.py)
├── setup.sh                        ← One-command setup script
├── requirements.txt                ← All Python dependencies
├── .env.example                    ← Template for environment variables
├── Dockerfile                      ← Docker container config
├── docker-compose.yml              ← Docker Compose setup
├── AI_Visibility_API.postman_collection.json  ← Postman tests
│
├── app/                            ← Main application package
│   ├── __init__.py                 ← create_app() factory
│   │
│   ├── agents/                     ← The 3 AI agents
│   │   ├── base.py                 ← Shared LLM client + JSON extraction
│   │   ├── discovery.py            ← Agent 1: generates queries
│   │   ├── scoring.py              ← Agent 2: scores visibility
│   │   └── recommendation.py       ← Agent 3: content recommendations
│   │
│   ├── api/                        ← HTTP endpoints (Flask Blueprints)
│   │   ├── profiles.py             ← Profile + pipeline + query routes
│   │   ├── queries.py              ← Recheck route
│   │   └── errors.py              ← 400/404/500 error handlers
│   │
│   ├── models/                     ← Database models (SQLAlchemy)
│   │   ├── profile.py              ← BusinessProfile table
│   │   ├── pipeline_run.py         ← PipelineRun table
│   │   ├── query.py                ← DiscoveredQuery table
│   │   └── recommendation.py       ← ContentRecommendation table
│   │
│   ├── services/
│   │   └── pipeline.py             ← Orchestrates all 3 agents
│   │
│   └── utils/
│       ├── scoring.py              ← Opportunity score formula
│       └── dataforseo.py           ← Real search volume API + fallback
│
├── tests/
│   ├── conftest.py                 ← Test fixtures (in-memory DB)
│   └── test_agents.py              ← 13 unit tests
│
└── migrations/                     ← Auto-generated by Flask-Migrate
```

---

## 11. Architecture Decisions

### Why Flask (not Django)?
Flask's minimal structure fits this project perfectly. We need a lightweight API, not a full web framework with admin panels and auth. Flask blueprints give us clean route organization without overhead.

### Why Anthropic Claude?
Claude claude-opus-4-5 produces reliably structured JSON even with strict output schemas. One API key, one provider, simpler code. All 3 agents use the same model for consistency.

### Why Separate Agent Classes?
Each agent has one job. The base class handles all LLM wiring. If you want to swap Claude for GPT-4o in one agent, you change 3 lines. If you want to test Agent 3 in isolation, you mock `_call_llm` and test just the prompt logic.

### Why SQLite by Default?
Zero setup. Works out of the box. Change `DATABASE_URL` in `.env` to switch to PostgreSQL — SQLAlchemy handles the difference with no code changes.

### Why Simulate Visibility (not scrape AI)?
Scraping live AI chatbots is fragile, rate-limited, and against most ToS. Claude simulating its own behavior is surprisingly accurate and stable. This is how most real AI visibility tools work today.

### Why DataForSEO with Fallback?
Real data is always better. But the fallback simulation uses deterministic heuristics (query length, commercial keyword signals) so the pipeline works and scores are still meaningful even without credentials. The simulation clearly logs that it's simulating.
