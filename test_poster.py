from app.agents.fetcher import FetcherAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.poster import PosterAgent

# Replace with your actual GitHub username
REPO = "vaishnavbhosale/test-pr-review"
PR_NUMBER = 1

print("Step 1 — Fetching PR...")
fetcher = FetcherAgent()
context = fetcher.run(REPO, PR_NUMBER)
print(f"Fetched: {context.title}")
print(f"Files: {len(context.files)}")

print()
print("Step 2 — Reviewing PR...")
reviewer = ReviewerAgent()
result = reviewer.run(context)
print(f"Score: {result.overall_score}/10")
print(f"Approved: {result.approved}")
print(f"Comments: {len(result.comments)}")

print()
print("Step 3 — Posting review to GitHub...")
poster = PosterAgent()
success = poster.run(context, result)

if success:
    print("Review posted successfully!")
    print(f"Go check your PR at: https://github.com/{REPO}/pull/{PR_NUMBER}")
else:
    print("Posting failed. Check the logs above for details.")