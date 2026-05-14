import hmac
import hashlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from app.config import settings
from app.core.orchestrator import run_pipeline
from app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("PR Review Agent starting up...")
    init_db()
    yield
    logger.info("PR Review Agent shutting down...")


app = FastAPI(
    title="PR Review Agent",
    description="Automatically reviews GitHub Pull Requests using AI",
    version="1.0.0",
    lifespan=lifespan
)


def verify_github_signature(payload: bytes, signature: str) -> bool:
    expected_signature = "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


@app.post("/ingest/{repo_owner}/{repo_name}")
async def ingest_repo(repo_owner: str, repo_name: str, background_tasks: BackgroundTasks):
    from app.rag.ingestor import CodebaseIngestor

    full_repo_name = f"{repo_owner}/{repo_name}"
    logger.info(f"[API] Ingestion requested for {full_repo_name}")

    def run_ingestion():
        ingestor = CodebaseIngestor()
        result = ingestor.ingest_repo(full_repo_name)
        logger.info(f"[API] Ingestion complete: {result}")

    background_tasks.add_task(run_ingestion)

    return {
        "status": "ingestion_started",
        "repo": full_repo_name,
        "message": "Codebase is being indexed. Reviews will use RAG context once complete."
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "PR Review Agent",
        "version": "1.0.0"
    }


@app.get("/metrics")
async def get_metrics():
    from app.db.database import SessionLocal
    from app.db.crud import get_evaluation_report, get_stats

    db = SessionLocal()
    try:
        report = get_evaluation_report(db)
        stats = get_stats(db)
        return {
            "system_stats": stats,
            "ai_quality": report
        }
    finally:
        db.close()


@app.post("/webhook/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    payload_bytes = await request.body()
    github_signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_github_signature(payload_bytes, github_signature):
        logger.warning(
            "[Webhook] Rejected request — invalid signature. "
            "Someone may be sending fake webhook requests."
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    event_type = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event_type != "pull_request":
        logger.info(f"[Webhook] Ignoring event type: {event_type}")
        return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}

    action = payload.get("action", "")
    if action not in ("opened", "synchronize"):
        logger.info(f"[Webhook] Ignoring pull_request action: {action}")
        return {"status": "ignored", "reason": f"Action '{action}' not handled"}

    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]

    logger.info(
        f"[Webhook] Received pull_request event — "
        f"Repo: {repo_name} | PR: #{pr_number} | Action: {action}"
    )

    background_tasks.add_task(run_pipeline, repo_name, pr_number)

    logger.info(f"[Webhook] Pipeline queued for PR #{pr_number}")

    return {
        "status": "accepted",
        "message": f"Review queued for PR #{pr_number} in {repo_name}"
    }
