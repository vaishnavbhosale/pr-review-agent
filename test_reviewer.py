from app.agents.fetcher import FetcherAgent
from app.agents.reviewer import ReviewerAgent

# Step 1 — Fetch the PR (same PR we used before)
fetcher = FetcherAgent()
context = fetcher.run("vaishnavbhosale/test-pr-review", 1)

print(f"Fetched PR: {context.title}")
print(f"Files to review: {len(context.files)}")
print()

# Step 2 — Review the PR
reviewer = ReviewerAgent()
result = reviewer.run(context)

# Step 3 — Print the results
print("=" * 50)
print("AI REVIEW RESULT")
print("=" * 50)
print(f"Overall Score : {result.overall_score}/10")
print(f"Approved      : {result.approved}")
print(f"Summary       : {result.summary}")
print(f"Total Comments: {len(result.comments)}")
print()

if result.comments:
    print("COMMENTS:")
    print("-" * 50)
    for i, comment in enumerate(result.comments, 1):
        print(f"Comment #{i}")
        print(f"  File     : {comment.filename}")
        print(f"  Line     : {comment.line}")
        print(f"  Severity : {comment.severity}")
        print(f"  Issue    : {comment.issue}")
        print(f"  Fix      : {comment.suggestion}")
        print()
else:
    print("No issues found. Clean PR.")