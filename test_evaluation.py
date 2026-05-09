from app.db.database import init_db, SessionLocal
from app.db.crud import (
    save_review,
    save_evaluation_metrics,
    get_evaluation_report,
    get_stats
)
from app.agents.fetcher import FetcherAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.poster import PosterAgent
from app.core.evaluator import EvaluatorAgent

# Step 1 — Initialize database
print("Initializing database...")
init_db()
print("Database ready.")
print()

# Step 2 — Run full pipeline
REPO = "vaishnavbhosale/test-pr-review"
PR_NUMBER = 2

print("Step 1 — Fetching PR...")
fetcher = FetcherAgent()
context = fetcher.run(REPO, PR_NUMBER)
print(f"Fetched: {context.title}")
print(f"Files: {len(context.files)}")
print()

print("Step 2 — Reviewing PR...")
reviewer = ReviewerAgent()
result = reviewer.run(context)
print(f"Score    : {result.overall_score}/10")
print(f"Approved : {result.approved}")
print(f"Comments : {len(result.comments)}")
print()

print("Step 3 — Evaluating review quality...")
evaluator = EvaluatorAgent()
metrics, comment_evaluations = evaluator.run(context, result)

print(f"Quality score      : {metrics['quality_score']}")
print(f"Hallucination rate : {metrics['hallucination_rate']}%")
print(f"Coverage rate      : {metrics['coverage_rate']}%")
print(f"Total comments     : {metrics['total_comments']}")
print(f"Hallucinated       : {metrics['hallucinated_comments']}")
print(f"Files covered      : {metrics['files_covered']}/{metrics['total_files']}")
print()

if result.comments:
    print("Comment evaluations:")
    for i, comment in enumerate(result.comments):
        valid = comment_evaluations[i]
        status = "VALID" if valid else "HALLUCINATION"
        print(
            f"  [{status}] "
            f"{comment.filename} line {comment.line} "
            f"— {comment.severity}"
        )
    print()

print("Step 4 — Posting review...")
poster = PosterAgent()
success = poster.run(context, result)
print(f"Posted: {success}")
print()

print("Step 5 — Saving to database...")
db = SessionLocal()
try:
    saved = save_review(
        db, context, result, success, comment_evaluations
    )
    print(f"Review saved with ID: {saved.id}")

    eval_saved = save_evaluation_metrics(db, saved.id, metrics)
    print(f"Metrics saved — Quality: {eval_saved.quality_score}")
finally:
    db.close()
print()

print("Step 6 — Fetching evaluation report...")
db = SessionLocal()
try:
    report = get_evaluation_report(db)
    stats = get_stats(db)

    print("=" * 50)
    print("SYSTEM STATS")
    print("=" * 50)
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print()
    print("=" * 50)
    print("AI QUALITY REPORT")
    print("=" * 50)
    for key, value in report.items():
        print(f"  {key}: {value}")
finally:
    db.close()