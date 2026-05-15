import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.schemas import (
    PRContext, ChangedFile, ReviewResult, ReviewComment, RepoContext
)


def test_poster_inline_comment_filtering():
    print("=" * 60)
    print("TEST: PosterAgent Inline Comment Filtering")
    print("=" * 60)

    from app.agents.poster import PosterAgent

    poster = PosterAgent()

    diff = "\n".join([f"+ line {i}" for i in range(1, 100)])
    changed_file = ChangedFile(
        filename="src/auth.py",
        status="modified",
        additions=100, deletions=0,
        patch=diff
    )

    context = PRContext(
        repo_name="test/repo", pr_number=1,
        title="Test", description="", author="test",
        base_branch="main", head_branch="feat",
        files=[changed_file]
    )

    valid_comment_1 = ReviewComment(
        filename="src/auth.py", line=10,
        issue="Issue 1", suggestion="Fix 1", severity="critical"
    )
    valid_comment_2 = ReviewComment(
        filename="src/auth.py", line=50,
        issue="Issue 2", suggestion="Fix 2", severity="warning"
    )
    valid_comment_3 = ReviewComment(
        filename="src/auth.py", line=90,
        issue="Issue 3", suggestion="Fix 3", severity="suggestion"
    )

    result = ReviewResult(
        overall_score=8, approved=True, summary="Good",
        comments=[valid_comment_1, valid_comment_2, valid_comment_3]
    )

    print("\n--- Scenario 1: No evaluations provided (backward compatibility) ---")
    inline_comments = poster._build_inline_comments(result, comment_evaluations=None)
    print(f"  Input comments: 3")
    print(f"  Output inline comments: {len(inline_comments)}")
    assert len(inline_comments) == 3, "Without evaluations, all comments should be kept"
    print("  PASSED: All 3 comments kept (backward compatibility)")

    print("\n--- Scenario 2: All comments valid ---")
    all_valid = [True, True, True]
    inline_comments = poster._build_inline_comments(result, all_valid)
    print(f"  Input comments: 3")
    print(f"  Evaluations: {all_valid}")
    print(f"  Output inline comments: {len(inline_comments)}")
    assert len(inline_comments) == 3, "All valid comments should be kept"
    print("  PASSED: All 3 valid comments kept")

    print("\n--- Scenario 3: Some comments invalid (hallucinations) ---")
    some_invalid = [True, False, True]
    inline_comments = poster._build_inline_comments(result, some_invalid)
    print(f"  Input comments: 3")
    print(f"  Evaluations: {some_invalid}")
    print(f"  Output inline comments: {len(inline_comments)}")
    assert len(inline_comments) == 2, "Only 2 valid comments should be kept"
    
    paths = [c["path"] for c in inline_comments]
    print(f"  Kept comments: {paths}")
    print("  PASSED: 2 valid comments kept, 1 hallucination filtered")

    print("\n--- Scenario 4: All comments invalid ---")
    all_invalid = [False, False, False]
    inline_comments = poster._build_inline_comments(result, all_invalid)
    print(f"  Input comments: 3")
    print(f"  Evaluations: {all_invalid}")
    print(f"  Output inline comments: {len(inline_comments)}")
    assert len(inline_comments) == 0, "No valid comments should be kept"
    print("  PASSED: 0 comments kept (all hallucinations)")

    print("\n" + "=" * 60)
    print("TEST PASSED: Inline comment filtering works correctly!")
    print("=" * 60)
    return True


def test_poster_summary_count_filtering():
    print("\n" + "=" * 60)
    print("TEST: PosterAgent Summary Count Filtering")
    print("=" * 60)

    from app.agents.poster import PosterAgent

    poster = PosterAgent()

    diff = "\n".join([f"+ line {i}" for i in range(1, 100)])
    changed_file = ChangedFile(
        filename="src/auth.py",
        status="modified",
        additions=100, deletions=0,
        patch=diff
    )

    context = PRContext(
        repo_name="test/repo", pr_number=1,
        title="Test", description="", author="test",
        base_branch="main", head_branch="feat",
        files=[changed_file]
    )

    critical = ReviewComment(
        filename="src/auth.py", line=10,
        issue="Critical issue", suggestion="Fix", severity="critical"
    )
    warning = ReviewComment(
        filename="src/auth.py", line=20,
        issue="Warning issue", suggestion="Fix", severity="warning"
    )
    suggestion = ReviewComment(
        filename="src/auth.py", line=30,
        issue="Suggestion", suggestion="Improve", severity="suggestion"
    )

    result = ReviewResult(
        overall_score=8, approved=True, summary="Good",
        comments=[critical, warning, suggestion]
    )

    print("\n--- Scenario: Filtering summary counts by severity ---")
    print(f"  Input: 1 critical, 1 warning, 1 suggestion (3 total)")
    
    comment_evaluations = [True, False, True]
    print(f"  Evaluations: {comment_evaluations} (warning is hallucination)")

    summary = poster._build_summary(context, result, comment_evaluations)

    has_critical = "🔴 Critical | 1" in summary or "Critical | 1 |" in summary
    has_warning = "🟡 Warning | 1" in summary or "Warning | 1 |" in summary
    has_suggestion = "🟢 Suggestion | 1" in summary or "Suggestion | 1 |" in summary
    has_total_2 = "Total | 2" in summary or "Total | **2**" in summary

    print(f"\n  Summary contains:")
    print(f"    Critical count = 1: {has_critical}")
    print(f"    Warning count = 1: {has_warning} (should be FALSE - it was filtered)")
    print(f"    Suggestion count = 1: {has_suggestion}")
    print(f"    Total = 2: {has_total_2}")

    print("\n  Summary preview (Issues Found section):")
    if "###" in summary:
        sections = summary.split("###")
        for section in sections:
            if "Issues Found" in section or "Issues" in section:
                lines = section.strip().split("\n")[:15]
                for line in lines:
                    print(f"    {line}")
                break

    assert has_critical, "Critical count should be 1"
    assert not has_warning, "Warning count should be 0 (filtered out)"
    assert has_suggestion, "Suggestion count should be 1"

    print("\n" + "=" * 60)
    print("TEST PASSED: Summary counts are correctly filtered!")
    print("=" * 60)
    return True


def test_poster_truncation_warning_in_summary():
    print("\n" + "=" * 60)
    print("TEST: PosterAgent Truncation Warning in Summary")
    print("=" * 60)

    from app.agents.poster import PosterAgent

    poster = PosterAgent()

    diff = "\n".join([f"+ line {i}" for i in range(1, 100)])
    changed_file = ChangedFile(
        filename="src/auth.py",
        status="modified",
        additions=100, deletions=0,
        patch=diff
    )

    context = PRContext(
        repo_name="test/repo", pr_number=1,
        title="Test", description="", author="test",
        base_branch="main", head_branch="feat",
        files=[changed_file],
        truncated_files=[{
            "filename": "src/large_module.py",
            "total_lines": 2000,
            "shown_lines": 1000,
            "omitted_lines": 1000
        }]
    )

    result = ReviewResult(
        overall_score=8, approved=True, summary="Good",
        comments=[]
    )

    print("\n--- Scenario: Context has truncated_files ---")
    print(f"  truncated_files: {context.truncated_files}")

    summary = poster._build_summary(context, result, None)

    has_warning_title = "Review Limitation" in summary or "limitation" in summary.lower()
    has_filename = "src/large_module.py" in summary
    has_omitted_info = "omitted" in summary.lower()

    print(f"\n  Summary contains:")
    print(f"    'Review Limitation' warning: {has_warning_title}")
    print(f"    Truncated filename: {has_filename}")
    print(f"    Omitted information: {has_omitted_info}")

    if has_warning_title:
        print("\n  Truncation warning section found in summary:")
        if "limitation" in summary.lower():
            idx = summary.lower().find("limitation")
            section = summary[max(0, idx-50):min(len(summary), idx+500)]
            lines = section.strip().split("\n")[:10]
            for line in lines:
                print(f"    {line}")

    assert has_warning_title, "Summary should contain truncation warning"
    assert has_filename, "Summary should mention the truncated file"

    print("\n" + "=" * 60)
    print("TEST PASSED: Truncation warning appears in GitHub summary!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("\n" + "#" * 60)
    print("#  TESTING POSTERAGENT FILTERING")
    print("#  (Hallucination filtering before posting to GitHub)")
    print("#" * 60)
    
    all_passed = True
    
    try:
        test_poster_inline_comment_filtering()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        all_passed = False
    
    try:
        test_poster_summary_count_filtering()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        all_passed = False
    
    try:
        test_poster_truncation_warning_in_summary()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        all_passed = False
    
    print("\n" + "#" * 60)
    if all_passed:
        print("#  ALL TESTS PASSED!")
    else:
        print("#  SOME TESTS FAILED")
    print("#" * 60)
