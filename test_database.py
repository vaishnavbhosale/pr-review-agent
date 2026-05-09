from app.db.database import init_db, SessionLocal
from app.db.crud import save_review, get_review_by_pr, get_all_reviews, get_stats
from app.agents.fetcher import FetcherAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.poster import PosterAgent

# Step 1 — Initialize database
print("Initializing database...")
init_db()
print("Database ready.")
print()

# Step 2 — Run the full pipeline
REPO = "vaishnavbhosale/test-pr-review"
PR_NUMBER = 1

print("Running full pipeline...")
fetcher = FetcherAgent()
context = fetcher.run(REPO, PR_NUMBER)
print(f"Fetched: {context.title}")

reviewer = ReviewerAgent()
result = reviewer.run(context)
print(f"Score: {result.overall_score}/10")

poster = PosterAgent()
success = poster.run(context, result)
print(f"Posted: {success}")
print()

# Step 3 — Save to database
print("Saving to database...")
db = SessionLocal()
try:
    saved = save_review(db, context, result, success)
    print(f"Saved with ID: {saved.id}")
    print(f"Created at: {saved.created_at}")
finally:
    db.close()
print()

# Step 4 — Read it back
print("Reading from database...")
db = SessionLocal()
try:
    review = get_review_by_pr(db, REPO, PR_NUMBER)
    print(f"Found review ID: {review.id}")
    print(f"Repo: {review.repo_name}")
    print(f"PR Number: {review.pr_number}")
    print(f"Score: {review.overall_score}/10")
    print(f"Approved: {review.approved}")
    print(f"Comments in DB: {len(review.comments)}")
finally:
    db.close()
print()

# Step 5 — Get stats
print("Database stats:")
db = SessionLocal()
try:
    stats = get_stats(db)
    for key, value in stats.items():
        print(f"  {key}: {value}")
finally:
    db.close()