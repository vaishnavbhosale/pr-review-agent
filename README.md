Here is the complete final README. Copy everything below this line:

---

```markdown
# PR Review Agent

A production-style multi-agent system that automatically reviews GitHub Pull Requests using AI. 
When a developer opens a PR, the system fetches the diff along with full repository context, 
sends it to Llama 3.3-70b via Groq, evaluates the review quality, and posts structured feedback back to GitHub —
 all without human involvement.

Built with FastAPI, Groq, SQLAlchemy, and PyGithub.

---

## How It Works

```
GitHub PR Opened
        │
        ▼
POST /webhook/github          ← FastAPI verifies HMAC-SHA256 signature
        │                       Returns 202 immediately
        ▼
   Orchestrator                ← Background task, retries on failure
        │
        ├── Stage 1: FetcherAgent
        │         GitHub API → PR metadata + file diffs + repo context → PRContext
        │
        ├── Stage 2: ReviewerAgent
        │         PRContext → Groq (Llama 3.3-70b) → ReviewResult
        │
        ├── Stage 3: EvaluatorAgent
        │         ReviewResult × PRContext → hallucination rate, coverage, quality score
        │
        ├── Stage 4: PosterAgent
        │         ReviewResult → GitHub PR review (inline comments + summary)
        │
        └── Stage 5: Database
                  Save review + evaluation metrics → SQLite / PostgreSQL
```

The developer sees a structured review with an overall score (1–10), inline comments on specific lines, severity classifications (critical / warning / suggestion), and an approve or request-changes verdict.

---

## Features

- **HMAC-SHA256 webhook verification** — rejects fake requests at the door
- **Async pipeline** — returns 202 to GitHub immediately, reviews in background
- **Repo-aware reviews** — fetches README, file structure, languages, and recent merged PRs to give the AI full repository context before reviewing
- **Structured JSON output** — AI response is parsed and validated against Pydantic schemas
- **Evaluation layer** — measures hallucination rate, coverage rate, and quality score on every review
- **Graceful degradation** — if inline comments fail, falls back to posting the summary only
- **Retry logic** — pipeline retries up to 2 times on failure with delay
- **Persistent storage** — every review and its metrics saved to database
- **SQLite → PostgreSQL ready** — change one environment variable

---

## Agent Design

Each agent has one responsibility and no knowledge of the others. They are independently testable and replaceable.

| Agent | Responsibility |
|---|---|
| FetcherAgent | Calls GitHub API, builds PRContext with files, metadata, and full repository context — README, file structure, languages, recent merged PRs |
| ReviewerAgent | Builds prompt with repo context, calls Groq, parses JSON response into ReviewResult |
| EvaluatorAgent | Validates comments against actual diff, computes quality metrics |
| PosterAgent | Formats ReviewResult as Markdown, posts to GitHub PR |

**Design principles:**
- Single responsibility — one agent, one job
- Fail loudly — exceptions are logged and re-raised, never swallowed silently
- Graceful degradation — fallbacks ensure partial success over total failure
- Stateless — agents take input, return output, hold no internal state

---

## Repo-Aware Context

Before reviewing any PR, the FetcherAgent gathers full context about the repository:

- **README** — what the project does and how it is structured
- **File structure** — top level directories and files
- **Languages** — all programming languages used in the codebase
- **Recent merged PRs** — what kind of work this team ships

This context is passed to the ReviewerAgent so the AI understands the codebase before reading the diff. Reviews reference the specific repository, its tech stack, and its patterns — not just the isolated code change.

---

## Evaluation Layer

The EvaluatorAgent automatically measures AI review quality without human involvement.

**Hallucination Rate**
The AI occasionally comments on lines that do not exist in the diff. Every comment's line number is cross-referenced against the actual diff. Comments on non-existent lines are flagged as hallucinations.

```
Hallucination Rate = hallucinated comments / total comments × 100
```

**Coverage Rate**
What percentage of changed files received at least one comment.

```
Coverage Rate = files with comments / total files changed × 100
```

**Quality Score**
A composite score from 0 to 100.

```
Quality Score = 100 − (hallucination rate × 0.5) + (coverage rate × 0.1)
                clamped between 0 and 100
```

| Quality Score | Meaning |
|---|---|
| 90 – 100 | Excellent — AI is accurate and thorough |
| 70 – 90 | Good — minor hallucination or coverage gaps |
| 50 – 70 | Fair — prompt tuning recommended |
| Below 50 | Poor — significant hallucination problem |

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.11 | Language |
| FastAPI | Web framework — async, fast, auto-docs |
| Uvicorn | ASGI server |
| Groq API | LLM inference — fastest Llama 3 inference available |
| Llama 3.3-70b | AI model — open weight, reliable structured output |
| PyGithub | GitHub API integration — handles auth, pagination, rate limits |
| SQLAlchemy | ORM — database portability, no raw SQL |
| SQLite | Default database — zero infrastructure, file-based |
| Pydantic | Data validation — validates AI response structure |
| python-dotenv | Config — secure secret management |

---

## Project Structure

```
pr-review-agent/
├── app/
│   ├── main.py                 # FastAPI app, webhook endpoint
│   ├── config.py               # Settings loaded from .env
│   ├── agents/
│   │   ├── fetcher.py          # Agent 1: fetch PR and repo context from GitHub API
│   │   ├── reviewer.py         # Agent 2: review with Groq LLM
│   │   └── poster.py           # Agent 4: post review to GitHub PR
│   ├── core/
│   │   ├── orchestrator.py     # Pipeline controller with retry logic
│   │   ├── evaluator.py        # Agent 3: evaluate review quality
│   │   ├── prompts.py          # System prompt and user prompt builder
│   │   └── schemas.py          # Pydantic models and dataclasses
│   └── db/
│       ├── database.py         # SQLAlchemy engine and session factory
│       ├── models.py           # ORM models — PRReview, ReviewComment, EvaluationMetrics
│       └── crud.py             # Database read/write operations
├── tests/
│   ├── test_webhook.py         # Webhook verification and routing tests
│   └── test_agents.py          # Agent unit tests with mocked APIs
├── run.py                      # Manual pipeline runner — test any PR instantly
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- Groq API key — [console.groq.com](https://console.groq.com)
- GitHub Personal Access Token with `repo` scope
- A GitHub repository with webhook access

### Installation

```bash
# Clone the repository
git clone https://github.com/vaishnavbhosale/pr-review-agent
cd pr-review-agent

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in your API keys in .env
```

### Environment Variables

```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
GROQ_API_KEY=gsk_your_groq_key_here
DATABASE_URL=sqlite:///./reviews.db
LOG_LEVEL=INFO
```

---

## Running the System

### Option 1 — Manual testing

Test the full pipeline on any PR instantly:

```bash
python run.py
```

Update `REPO` and `PR_NUMBER` at the top of `run.py` to target any PR.

### Option 2 — Webhook server (automatic)

```bash
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

Once the server is running, expose it to the internet using ngrok:

```bash
ngrok http 8000
```

---

## Webhook Setup

Go to your GitHub repository → **Settings → Webhooks → Add webhook** and configure:

| Field | Value |
|---|---|
| Payload URL | `https://your-ngrok-url/webhook/github` |
| Content type | `application/json` |
| Secret | Your `GITHUB_WEBHOOK_SECRET` value |
| Events | Pull requests |

Open a PR on the repository — the system reviews it automatically.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Server health check |
| GET | `/metrics` | AI quality metrics across all reviews |
| POST | `/webhook/github` | GitHub webhook receiver |

### Sample `/metrics` Response

```json
{
  "system_stats": {
    "total_reviews": 5,
    "approved": 3,
    "rejected": 2,
    "critical_comments_found": 8,
    "hallucinated_comments": 1,
    "valid_comments": 12
  },
  "ai_quality": {
    "total_reviews_evaluated": 5,
    "average_quality_score": 94.5,
    "average_hallucination_rate": 3.2,
    "average_coverage_rate": 87.0,
    "total_comments_made": 13,
    "total_hallucinations_detected": 1
  }
}
```

---

## Security

- **HMAC-SHA256 verification** — every webhook request is signed by GitHub and verified server-side. Requests with invalid signatures are rejected with 401.
- **Timing-safe comparison** — `hmac.compare_digest()` prevents timing attacks on signature verification.
- **Secret management** — all API keys stored in `.env`, never committed to version control.

---

## Known Limitations and Planned Improvements

**Short term**
- Chunking for large PRs — split diffs by file, review in parallel, aggregate results
- Idempotency guard — skip re-reviewing the same commit SHA if already processed
- Exponential backoff — replace fixed retry delay with increasing delays

**Medium term**
- PostgreSQL — swap `DATABASE_URL` for production-scale deployments
- Celery + Redis — replace `BackgroundTasks` with a proper durable job queue
- Checkpoint-based retries — resume pipeline from last successful stage instead of restarting

**Long term**
- RAG with vector DB — store past reviews as embeddings, surface relevant history to improve future reviews
- Multi-model consensus — run two LLMs independently, merge results to reduce false positives
- Per-author profiles — track developer patterns over time and personalise feedback
- MCP compatibility — wrap agents as MCP tools for use with Claude and other MCP-compatible hosts

---

## Built by

**Vaishnavv 🩵**

Built as a production-style AI engineering project demonstrating multi-agent orchestration, repo-aware LLM integration, structured output parsing, and automated evaluation of AI review quality.


