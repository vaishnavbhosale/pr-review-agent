# PR Review Agent — Multi-Agent AI Code Review System

An automated Pull Request review system that uses multiple AI agents 
to fetch, review, evaluate, and post code reviews on GitHub PRs. 
Built with FastAPI, Groq (Llama 3.3-70b), and SQLAlchemy.

---

## What it does

When a developer opens a Pull Request on GitHub, this system automatically:

1. Fetches the PR diff and changed files from GitHub API
2. Sends the code changes to Llama 3.3-70b via Groq for review
3. Evaluates the AI review for hallucinations and coverage
4. Posts a structured, professional review back to the GitHub PR
5. Saves all results and metrics to a database for analytics

The developer receives a review with an overall score, specific 
inline comments on problematic lines, and severity classifications 
— without any human reviewer involvement.

---

## System Architecture
GitHub PR Opened
│
▼
POST /webhook/github  ←── FastAPI server
│
│  Verify HMAC-SHA256 signature
│  Return 202 immediately
│
▼
Orchestrator  ←── Background task
│
├── Stage 1: FetcherAgent
│     └── GitHub API → PRContext
│
├── Stage 2: ReviewerAgent
│     └── Groq API (Llama 3) → ReviewResult
│
├── Stage 3: EvaluatorAgent
│     └── PRContext + ReviewResult → Metrics
│
├── Stage 4: PosterAgent
│     └── ReviewResult → GitHub PR Comment
│
└── Stage 5: Database
└── Save review + metrics → SQLite

---

## Why this architecture

**Multi-agent design** — Each agent has one responsibility.
If the GitHub API changes, only the FetcherAgent needs updating.
If we switch from Groq to OpenAI, only the ReviewerAgent changes.
Agents are independently testable and replaceable.

**Async pipeline** — FastAPI responds to GitHub in milliseconds.
The review runs in the background. GitHub never times out.
Multiple PRs can be reviewed concurrently.

**Evaluation layer** — We do not blindly trust the AI.
Every comment is checked against the actual diff.
We track hallucination rate, coverage, and quality score over time.

**SQLite first, PostgreSQL ready** — Zero infrastructure to start.
Change one environment variable to switch to PostgreSQL.
All queries use SQLAlchemy ORM — no raw SQL, no migration needed.

---

## Tech Stack

| Technology | Purpose | Why |
|---|---|---|
| Python 3.11 | Language | Standard for AI/ML work |
| FastAPI | Web framework | Async, fast, auto-docs |
| Uvicorn | ASGI server | Runs FastAPI in production |
| Groq API | LLM inference | Fastest Llama 3 inference |
| Llama 3.3-70b | AI model | Open weight, structured output |
| PyGithub | GitHub integration | Handles auth, pagination, rate limits |
| SQLAlchemy | ORM | Database portability |
| SQLite | Database | Zero infrastructure, file based |
| Pydantic | Data validation | Validates AI response structure |
| python-dotenv | Config | Secure secret management |

---

## Folder Structure
pr-review-agent/
├── app/
│   ├── main.py                 # FastAPI server, webhook receiver
│   ├── config.py               # Settings from .env file
│   ├── agents/
│   │   ├── fetcher.py          # Agent 1: fetch PR from GitHub
│   │   ├── reviewer.py         # Agent 2: review with Groq LLM
│   │   ├── poster.py           # Agent 3: post review to GitHub
│   ├── core/
│   │   ├── orchestrator.py     # Pipeline controller
│   │   ├── evaluator.py        # Agent 4: evaluate review quality
│   │   ├── prompts.py          # All LLM prompt templates
│   │   └── schemas.py          # Pydantic models and dataclasses
│   └── db/
│       ├── database.py         # SQLAlchemy engine and session
│       ├── models.py           # ORM models
│       └── crud.py             # Database read/write functions
├── tests/
│   ├── test_webhook.py
│   └── test_agents.py
├── requirements.txt
├── .env.example
└── README.md

---

## How to Run

### Prerequisites

- Python 3.11+
- Groq API key — https://console.groq.com
- GitHub Personal Access Token with `repo` scope

### Setup

```bash
# Clone the repository
git clone https://github.com/vaishnavbhosale/pr-review-agent
cd pr-review-agent

# Create virtual environment
python -m venv venv

# Activate — Mac/Linux
source venv/bin/activate

# Activate — Windows
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Fill in your real API keys in .env
```

### Configure .env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
GROQ_API_KEY=gsk_your_groq_key_here
DATABASE_URL=sqlite:///./reviews.db
LOG_LEVEL=INFO

### Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

Server starts at `http://localhost:8000`

Interactive API docs at `http://localhost:8000/docs`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Server health check |
| GET | /metrics | AI quality metrics dashboard |
| POST | /webhook/github | GitHub webhook receiver |

### Sample /metrics response

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

## Evaluation Layer

The evaluation layer automatically measures AI review quality
without human involvement.

### What we measure

**Hallucination Rate**
The AI sometimes comments on lines that do not exist in the diff.
We detect this by checking every comment's line number against
the actual diff length.
Hallucination rate = hallucinated comments / total comments × 100

**Coverage Rate**
What percentage of changed files received at least one comment.
Coverage rate = files with comments / total files changed × 100

**Quality Score**
A composite score from 0 to 100.
Quality = 100
- (hallucination rate × 0.5)
+ (coverage rate × 0.1)
clamped between 0 and 100

### How to interpret the metrics

| Quality Score | Meaning |
|---|---|
| 90 to 100 | Excellent — AI is accurate and thorough |
| 70 to 90 | Good — minor hallucination or coverage gaps |
| 50 to 70 | Fair — prompt tuning recommended |
| Below 50 | Poor — significant hallucination problem |

---

## Webhook Setup

To connect GitHub to your server:

1. Expose your local server using ngrok:
```bash
ngrok http 8000
```

2. Go to your GitHub repo → Settings → Webhooks → Add webhook

3. Configure:
   - Payload URL: `https://your-ngrok-url/webhook/github`
   - Content type: `application/json`
   - Secret: your `GITHUB_WEBHOOK_SECRET` value
   - Events: Pull requests

4. Open a PR on that repo — the system reviews it automatically

---

## Security

- **HMAC-SHA256 verification** — every webhook request is verified
  using a shared secret. Fake requests are rejected with 401.
- **Timing-safe comparison** — `hmac.compare_digest()` prevents
  timing attacks on signature verification.
- **Secret management** — all API keys in `.env`, never committed.
- **Non-root execution** — Docker container runs as limited user.

---

## Future Improvements

**Short term**
- Chunking for large PRs — split diffs into chunks, review in parallel
- Idempotency check — skip re-reviewing same commit SHA twice
- Exponential backoff — smarter retry with increasing delays

**Medium term**
- PostgreSQL — swap DATABASE_URL for production scale
- Celery + Redis — replace BackgroundTasks with proper job queue
- Per-file review — review each file independently for better quality

**Long term**
- RAG with vector DB — store past reviews as embeddings,
  surface relevant history to improve future reviews
- Per-author profiles — track developer patterns over time
- Multi-model review — run two LLMs, merge results, reduce false positives
- MCP compatibility — wrap agents as MCP tools for Claude integration

---

## Agent Design Principles

Each agent follows these rules:

1. **Single responsibility** — one agent, one job
2. **Independent** — agents do not know about each other
3. **Fail loudly** — exceptions are logged and re-raised, never swallowed
4. **Graceful degradation** — fallbacks ensure partial success over total failure
5. **Stateless** — agents take input, return output, hold no state

---

## Built by

Vaishnav Bhosale

Built as a production-style AI engineering project demonstrating
multi-agent orchestration, LLM integration, structured output parsing,
and automated evaluation of AI quality.
