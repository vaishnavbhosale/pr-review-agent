import asyncio
import logging
from app.agents.fetcher import FetcherAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.poster import PosterAgent
from app.core.evaluator import EvaluatorAgent
from app.db.database import SessionLocal
from app.db.crud import save_review, save_evaluation_metrics

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY = 5


async def run_pipeline(repo_name: str, pr_number: int):
    """
    The main pipeline. Runs all agents in sequence.

    Fetcher → Reviewer → Evaluator → Poster → Database

    Evaluator runs before Poster so we have quality metrics
    before deciding how to present the review.

    Retries up to MAX_RETRIES times on failure.
    """

    logger.info(
        f"[Orchestrator] Pipeline started — "
        f"Repo: {repo_name} | PR: #{pr_number}"
    )

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            logger.info(
                f"[Orchestrator] Attempt {attempt} "
                f"of {MAX_RETRIES + 1}"
            )

            # ── Stage 1: Fetch ──────────────────────────────
            logger.info("[Orchestrator] Stage 1 — Fetching PR data")

            fetcher = FetcherAgent()
            context = await asyncio.to_thread(
                fetcher.run, repo_name, pr_number
            )

            logger.info(
                f"[Orchestrator] Stage 1 complete — "
                f"Fetched {len(context.files)} files"
            )

            # ── Stage 2: Review ─────────────────────────────
            logger.info("[Orchestrator] Stage 2 — Reviewing code with AI")

            reviewer = ReviewerAgent()
            result = await asyncio.to_thread(
                reviewer.run, context
            )

            logger.info(
                f"[Orchestrator] Stage 2 complete — "
                f"Score: {result.overall_score}/10 | "
                f"Comments: {len(result.comments)}"
            )

            # ── Stage 3: Evaluate ───────────────────────────
            logger.info("[Orchestrator] Stage 3 — Evaluating review quality")

            evaluator = EvaluatorAgent()
            metrics, comment_evaluations = await asyncio.to_thread(
                evaluator.run, context, result
            )

            logger.info(
                f"[Orchestrator] Stage 3 complete — "
                f"Quality score: {metrics['quality_score']} | "
                f"Hallucination rate: {metrics['hallucination_rate']}% | "
                f"Coverage: {metrics['coverage_rate']}%"
            )

            # ── Stage 4: Post ───────────────────────────────
            logger.info("[Orchestrator] Stage 4 — Posting review to GitHub")

            poster = PosterAgent()
            success = await asyncio.to_thread(
                poster.run, context, result
            )

            logger.info(
                f"[Orchestrator] Stage 4 complete — "
                f"Posted: {success}"
            )

            # ── Stage 5: Save to database ───────────────────
            logger.info("[Orchestrator] Stage 5 — Saving to database")

            db = SessionLocal()
            try:
                # Save review with comment evaluations
                saved = await asyncio.to_thread(
                    save_review,
                    db,
                    context,
                    result,
                    success,
                    comment_evaluations
                )

                # Save evaluation metrics separately
                await asyncio.to_thread(
                    save_evaluation_metrics,
                    db,
                    saved.id,
                    metrics
                )

                logger.info(
                    f"[Orchestrator] Stage 5 complete — "
                    f"Saved review ID: {saved.id}"
                )
            finally:
                db.close()

            # ── Pipeline complete ───────────────────────────
            logger.info(
                f"[Orchestrator] Pipeline finished successfully — "
                f"PR #{pr_number} | "
                f"Score: {result.overall_score}/10 | "
                f"Approved: {result.approved} | "
                f"Quality: {metrics['quality_score']} | "
                f"Posted: {success}"
            )

            return

        except Exception as e:
            logger.error(
                f"[Orchestrator] Attempt {attempt} failed — "
                f"{type(e).__name__}: {e}"
            )

            if attempt <= MAX_RETRIES:
                logger.info(
                    f"[Orchestrator] Waiting {RETRY_DELAY}s "
                    f"before retry..."
                )
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(
                    f"[Orchestrator] All attempts failed — "
                    f"PR #{pr_number} will not be reviewed"
                )