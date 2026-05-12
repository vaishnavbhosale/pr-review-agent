import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s"
)
from app.agents.fetcher import FetcherAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.poster import PosterAgent
from app.core.evaluator import EvaluatorAgent
from app.db.database import init_db, SessionLocal
from app.db.crud import save_review, save_evaluation_metrics

# ──────────────────────────────
REPO      = "vaishnavbhosale/test-pr-review"
PR_NUMBER = 5
# ──────────────────────────────

def main():
    print(f"\nPR Review Agent")
    print(f"Repo      : {REPO}")
    print(f"PR Number : #{PR_NUMBER}")
    print("-" * 40)

    init_db()

    print("\n[1/4] Fetching PR from GitHub...")
    context = FetcherAgent().run(REPO, PR_NUMBER)
    print(f"      Title  : {context.title}")
    print(f"      Author : {context.author}")
    print(f"      Files  : {len(context.files)}")

    print("\n[2/4] Reviewing code with Llama 3.3...")
    result = ReviewerAgent().run(context)
    print(f"      Score    : {result.overall_score}/10")
    print(f"      Approved : {result.approved}")
    print(f"      Comments : {len(result.comments)}")

    print("\n[3/4] Evaluating review quality...")
    metrics, evaluations = EvaluatorAgent().run(context, result)
    print(f"      Quality score      : {metrics['quality_score']}")
    print(f"      Hallucination rate : {metrics['hallucination_rate']}%")
    print(f"      Coverage rate      : {metrics['coverage_rate']}%")

    print("\n[4/4] Posting review to GitHub...")
    success = PosterAgent().run(context, result)
    print(f"      Posted : {success}")

    print("\nSaving to database...")
    db = SessionLocal()
    try:
        saved = save_review(db, context, result, success, evaluations)
        save_evaluation_metrics(db, saved.id, metrics)
        print(f"Saved with ID: {saved.id}")
    finally:
        db.close()

    print("\n" + "=" * 40)
    print("DONE")
    print(f"Check your PR at:")
    print(f"https://github.com/{REPO}/pull/{PR_NUMBER}")
    print("=" * 40)

if __name__ == "__main__":
    main()