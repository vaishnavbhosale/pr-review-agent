import hmac
import hashlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from app.config import settings
from app.core.orchestrator import run_pipeline
from app.db.database import init_db

# Configure logging for the entire application
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
    """
    Verifies that the webhook request actually came from GitHub.

    GitHub signs every webhook payload with your secret using HMAC-SHA256.
    We compute the expected signature and compare it to what GitHub sent.
    If they match, the request is genuine. If not, we reject it.

    This prevents anyone on the internet from triggering reviews
    by sending fake webhook requests to our server.
    """

    expected_signature = "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Used by Docker and load balancers to verify the server is running.
    """
    return {
        "status": "healthy",
        "service": "PR Review Agent",
        "version": "1.0.0"
    }


@app.post("/webhook/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Receives GitHub webhook events.

    GitHub sends a POST request here whenever something happens
    in a repository that has this webhook configured.

    We only care about pull_request events with action
    'opened' or 'synchronize'. We ignore everything else.

    We respond with 202 Accepted immediately, then process
    the review in the background so GitHub does not time out.
    """

    # Step 1 — Read the raw request body
    payload_bytes = await request.body()

    # Step 2 — Get the signature GitHub sent in the header
    github_signature = request.headers.get("X-Hub-Signature-256", "")

    # Step 3 — Verify the signature
    if not verify_github_signature(payload_bytes, github_signature):
        logger.warning(
            "[Webhook] Rejected request — invalid signature. "
            "Someone may be sending fake webhook requests."
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    # Step 4 — Get the event type from the header
    event_type = request.headers.get("X-GitHub-Event", "")

    # Step 5 — Parse the JSON payload
    payload = await request.json()

    # Step 6 — Only process pull request events
    if event_type != "pull_request":
        logger.info(f"[Webhook] Ignoring event type: {event_type}")
        return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}

    # Step 7 — Only process opened or updated PRs
    action = payload.get("action", "")

    if action not in ("opened", "synchronize"):
        logger.info(f"[Webhook] Ignoring pull_request action: {action}")
        return {"status": "ignored", "reason": f"Action '{action}' not handled"}

    # Step 8 — Extract PR details
    pr_number = payload["pull_request"]["number"]
    repo_name = payload["repository"]["full_name"]

    logger.info(
        f"[Webhook] Received pull_request event — "
        f"Repo: {repo_name} | PR: #{pr_number} | Action: {action}"
    )

    # Step 9 — Queue the pipeline as a background task
    # We return 202 immediately so GitHub does not time out
    # The actual review happens asynchronously after this response
    background_tasks.add_task(run_pipeline, repo_name, pr_number)

    logger.info(f"[Webhook] Pipeline queued for PR #{pr_number}")

    return {
        "status": "accepted",
        "message": f"Review queued for PR #{pr_number} in {repo_name}"
    }