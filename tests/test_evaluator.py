import sys
import os

# Ensure app can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.schemas import PRContext, ChangedFile, ReviewResult, ReviewComment
from app.core.evaluator import EvaluatorAgent

def test_hallucination_detection():
    print("--- Running Hallucination Detection Test ---")
    
    # 1. Mock a PR context with a file that only has 10 lines
    fake_diff = "\n".join([f"+ line {i}" for i in range(1, 11)])
    changed_file = ChangedFile(
        filename="src/auth.py", 
        status="modified", 
        additions=10, deletions=0, patch=fake_diff
    )
    context = PRContext(
        repo_name="test/repo", pr_number=1, title="Test", description="",
        author="test", base_branch="main", head_branch="feat",
        files=[changed_file]
    )

    # 2. Mock an AI review where one comment is valid, and one is a hallucination
    valid_comment = ReviewComment(
        filename="src/auth.py", line=5,  # Valid: line 5 exists
        issue="Minor issue", suggestion="Fix this", severity="suggestion"
    )
    hallucinated_comment = ReviewComment(
        filename="src/auth.py", line=50, # Hallucination: File only has 10 lines!
        issue="Fake issue", suggestion="Fake fix", severity="critical"
    )
    hallucinated_file = ReviewComment(
        filename="src/fake_file.py", line=1, # Hallucination: File doesn't exist!
        issue="Fake", suggestion="Fake", severity="warning"
    )

    result = ReviewResult(
        overall_score=8, approved=True, summary="Test",
        comments=[valid_comment, hallucinated_comment, hallucinated_file]
    )

    # 3. Run the Evaluator
    evaluator = EvaluatorAgent()
    metrics, evaluations = evaluator.run(context, result)

    print(f"\nResults:")
    print(f"Total Comments Evaluated : {metrics['total_comments']}")
    print(f"Hallucinations Caught    : {metrics['hallucinated_comments']}")
    print(f"Hallucination Rate       : {metrics['hallucination_rate']}%")
    print(f"Adjusted Quality Score   : {metrics['quality_score']}/100")
    
    assert metrics['hallucinated_comments'] == 2, "Failed to catch hallucinations!"
    print("\n✅ TEST PASSED: Evaluator successfully caught fake line numbers and fake files.")

if __name__ == "__main__":
    test_hallucination_detection()