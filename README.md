# AI Visibility Intelligence API

A RESTful Flask API that uses a multi-agent AI pipeline to help businesses understand and improve how they appear in AI-generated answers (ChatGPT, Claude, Perplexity, etc.).

---

## What This Does

You register a business. The system runs 3 AI agents in sequence:

1. **Agent 1 (Discovery)** — Asks Claude to generate 10–20 realistic questions people ask AI assistants in your competitive space
2. **Agent 2 (Scoring)** — For each question, simulates whether your domain would appear in an AI answer, then enriches with real search volume from DataForSEO
3. **Agent 3 (Recommendations)** — For the top queries where you're NOT appearing, generates specific content recommendations

---

## Quick Start (Local)

### Option A — One-command setup script

```bash
git clone <your-repo>
cd ai_visibility_api
bash setup.sh
```

Then open `.env` and fill in your `ANTHROPIC_API_KEY`, then:

```bash
source venv/bin/activate
python run.py
```

### Option B — Manual setup

```bash
# 1. Clone and enter
git clone <your-repo>
cd ai_visibility_api

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Now open .env in any editor and add your ANTHROPIC_API_KEY

# 5. Initialize database
export FLASK_APP=run.py
flask db init
flask db migrate -m "initial schema"
flask db upgrade

# 6. Run the server
python run.py
```

Server runs at `http://localhost:5000`

### Option C — Docker Compose

```bash
# Fill in your API key first
cp .env.example .env
# edit .env → add ANTHROPIC_API_KEY

docker-compose up --build
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ Yes | Your Anthropic API key (get one at console.anthropic.com) |
| `DATABASE_URL` | No | Defaults to `sqlite:///dev.db` |
| `SECRET_KEY` | No | Flask session secret (change in production) |
| `DATAFORSEO_LOGIN` | No | Email for DataForSEO API (free trial available) |
| `DATAFORSEO_PASSWORD` | No | Password for DataForSEO API |
| `FLASK_ENV` | No | `development` or `production` |

> If you don't have DataForSEO credentials, the app still works — it falls back to a smart simulation based on query characteristics.

---

## API Reference

### Register a Business Profile
```
POST /api/v1/profiles
```
```json
{
  "name": "Frase",
  "domain": "frase.io",
  "industry": "SEO Content Tools",
  "description": "AI-powered content briefs and SEO research",
  "competitors": ["surferseo.com", "marketmuse.com", "clearscope.io"]
}
```

### Run the Full Pipeline
```
POST /api/v1/profiles/{profile_uuid}/run
```
This triggers all 3 agents. Takes 15–45 seconds. Rate-limited to 5 runs/hour per IP.

### Get Profile + Stats
```
GET /api/v1/profiles/{profile_uuid}
```

### List Discovered Queries
```
GET /api/v1/profiles/{profile_uuid}/queries
GET /api/v1/profiles/{profile_uuid}/queries?min_score=0.6
GET /api/v1/profiles/{profile_uuid}/queries?status=not_visible
GET /api/v1/profiles/{profile_uuid}/queries?page=1&per_page=10
```

### Get Content Recommendations
```
GET /api/v1/profiles/{profile_uuid}/recommendations
```

### Re-score a Single Query
```
POST /api/v1/queries/{query_uuid}/recheck
```
Useful after you've published new content — re-runs Agent 2 to check if visibility improved.

---

## Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

Tests mock all LLM calls so they run instantly without API keys.

---

## Architecture Decisions

### Why Anthropic Claude (not OpenAI)?

I used Claude claude-opus-4-5 for all three agents because:
- It produces more reliably structured JSON with complex schemas
- The instruction-following on strict output format constraints is strong
- One provider keeps the codebase simpler (no switching logic)

### Agent Separation

Each agent is a class in `app/agents/` with its own system prompt and `run()` method. The orchestrator in `app/services/pipeline.py` calls them in sequence. Agents share no state — they receive everything they need via arguments and return plain dicts.

### Why Classes Over Functions?

Classes let you override `_system_prompt` per agent while sharing the LLM call logic (`_call_llm`) and JSON extraction (`_extract_json`) in the base class. Each agent is independently unit-testable by mocking `_call_llm`.

### Prompt Engineering Strategy

Every agent prompt has:
1. A clear persona ("You are an AI visibility analyst...")
2. Explicit output schema defined in the prompt itself
3. The instruction "Return ONLY valid JSON" in bold
4. Fallback handling in Python if the model ignores this

This pattern consistently produces parseable output across different phrasings of the same question.

### Opportunity Score Formula

```
score = 0.30 × volume_norm
      + 0.35 × gap_signal
      + 0.20 × ease_signal
      + 0.15 × intent_signal
```

**Volume** (30%) — log-scaled and capped at 50k/month. Log scale because the jump from 100→1000 searches matters as much as 10k→100k for niche B2B.

**Gap** (35%, heaviest) — 1.0 if not appearing, 0.3 if unknown, 0.0 if visible. The gap IS the opportunity, so this gets the most weight.

**Ease** (20%) — `1 - difficulty/100`. Lower competition = easier to capture = higher score.

**Intent** (15%) — high-intent queries (comparisons, "best X") get 1.0, medium 0.6, low 0.2. A comparison query at rank 0 is worth more than an informational one.

### DataForSEO Integration

Real search volume data comes from DataForSEO's Google Ads Search Volume endpoint. If credentials are missing, `app/utils/dataforseo.py` runs a deterministic simulation using log-scaled heuristics based on query length and commercial-signal keywords. The simulation produces reasonable ordering (comparison queries > informational) so the opportunity scores stay meaningful even without the API.

### Why SQLite by Default?

SQLite requires zero setup and works fine for an assessment. The `DATABASE_URL` env var switches to PostgreSQL for production with no code changes (SQLAlchemy handles the difference).

### Failure Isolation

Agent 2 runs inside a try/except per query. If it crashes on one query (network error, malformed LLM output), that query is marked `unknown` and the pipeline continues. A full pipeline failure (Agent 1 produces zero queries) marks the run `failed` in the database and returns a clear error response.

---

## Project Structure

```
ai_visibility_api/
├── app/
│   ├── __init__.py          # create_app() factory, extension init
│   ├── agents/
│   │   ├── base.py          # shared LLM client + JSON extraction
│   │   ├── discovery.py     # Agent 1: generates queries
│   │   ├── scoring.py       # Agent 2: visibility + opportunity score
│   │   └── recommendation.py# Agent 3: content gap recommendations
│   ├── api/
│   │   ├── profiles.py      # POST/GET profile + pipeline + queries endpoints
│   │   ├── queries.py       # POST recheck endpoint
│   │   └── errors.py        # global 400/404/500 handlers
│   ├── models/
│   │   ├── profile.py       # BusinessProfile
│   │   ├── pipeline_run.py  # PipelineRun
│   │   ├── query.py         # DiscoveredQuery
│   │   └── recommendation.py# ContentRecommendation
│   ├── services/
│   │   └── pipeline.py      # orchestrates all 3 agents
│   └── utils/
│       ├── scoring.py       # opportunity score formula
│       └── dataforseo.py    # real search volume API + fallback
├── tests/
│   ├── conftest.py          # pytest fixtures (in-memory DB)
│   └── test_agents.py       # unit tests for all agents + score formula
├── migrations/              # Flask-Migrate auto-generated
├── run.py                   # development entry point
├── setup.sh                 # one-command setup
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Tradeoffs

| Decision | Why | What I'd do differently at scale |
|---|---|---|
| Synchronous pipeline | Simpler, meets spec | Celery + Redis for background jobs |
| SQLite default | Zero config | PostgreSQL in production |
| One LLM per pipeline run | Simpler code | Cache Agent 1 results, only re-run Agent 2 on recheck |
| Simulated visibility check | Real scraping is fragile | Actually query live AI APIs via their search products |
| Claude for all 3 agents | One API key, simpler | GPT-4o-mini for Agent 2 (cheaper, lower creativity needed) |

---

## AI Tools Used

Claude (claude.ai) was used to help plan the architecture and draft initial code. All prompts, schema decisions, opportunity score formula design, and agent separation strategy were my own. The code was reviewed, understood, and refined before submission.
