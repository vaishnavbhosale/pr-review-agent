import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.schemas import (
    PRContext, ChangedFile, ReviewResult, ReviewComment, RepoContext
)
from app.core.prompts import build_user_prompt
from app.config import settings


def test_truncation_tracking():
    print("=" * 60)
    print("TEST: Truncation Tracking in PRContext")
    print("=" * 60)

    large_diff = "\n".join([f"+ line {i}" for i in range(1, 1500)])
    normal_diff = "\n".join([f"+ line {i}" for i in range(1, 100)])

    changed_files = [
        ChangedFile(
            filename="src/large_module.py",
            status="modified",
            additions=1500, deletions=0,
            patch=large_diff
        ),
        ChangedFile(
            filename="src/small_module.py",
            status="added",
            additions=100, deletions=0,
            patch=normal_diff
        ),
    ]

    context = PRContext(
        repo_name="test/repo", pr_number=1,
        title="Test", description="", author="test",
        base_branch="main", head_branch="feat",
        files=changed_files
    )

    print(f"\nBefore prompt building:")
    print(f"  truncated_files = {context.truncated_files}")

    prompt = build_user_prompt(context)

    print(f"\nAfter prompt building:")
    print(f"  truncated_files count = {len(context.truncated_files)}")

    for tf in context.truncated_files:
        print(f"    - {tf['filename']}: {tf['total_lines']} lines total, "
              f"{tf['shown_lines']} shown, {tf['omitted_lines']} omitted")

    assert len(context.truncated_files) == 1, \
        f"Expected 1 truncated file, got {len(context.truncated_files)}"
    
    truncated = context.truncated_files[0]
    assert truncated["filename"] == "src/large_module.py", \
        f"Wrong filename: {truncated['filename']}"
    assert truncated["total_lines"] == 1500, \
        f"Wrong total_lines: {truncated['total_lines']}"
    assert truncated["omitted_lines"] == 1500 - settings.MAX_DIFF_LINES_PER_FILE, \
        f"Wrong omitted_lines: {truncated['omitted_lines']}"

    print("\n" + "=" * 60)
    print("TEST PASSED: Truncation tracking works correctly!")
    print("=" * 60)
    return True


def test_prompt_contains_truncation_notice():
    print("\n" + "=" * 60)
    print("TEST: Prompt Contains Truncation Notice")
    print("=" * 60)

    large_diff = "\n".join([f"+ line {i}" for i in range(1, 1200)])
    
    changed_file = ChangedFile(
        filename="src/very_large.py",
        status="modified",
        additions=1200, deletions=0,
        patch=large_diff
    )

    context = PRContext(
        repo_name="test/repo", pr_number=1,
        title="Test", description="", author="test",
        base_branch="main", head_branch="feat",
        files=[changed_file]
    )

    prompt = build_user_prompt(context)

    expected_notice = f"first {settings.MAX_DIFF_LINES_PER_FILE} lines shown"
    
    if expected_notice in prompt:
        print(f"\n  Prompt contains truncation notice: YES")
        print(f"  Notice includes: 'first {settings.MAX_DIFF_LINES_PER_FILE} lines shown'")
    else:
        print(f"\n  Prompt contains truncation notice: NO")
        print(f"  Looking for: '{expected_notice}'")
        print(f"  Prompt preview (last 500 chars):")
        print(prompt[-500:])
        raise AssertionError("Truncation notice not found in prompt")

    print("\n" + "=" * 60)
    print("TEST PASSED: Prompt contains correct truncation notice!")
    print("=" * 60)
    return True


def test_small_files_not_truncated():
    print("\n" + "=" * 60)
    print("TEST: Small Files Are NOT Truncated")
    print("=" * 60)

    small_diff = "\n".join([f"+ line {i}" for i in range(1, 50)])
    
    changed_file = ChangedFile(
        filename="src/small.py",
        status="modified",
        additions=50, deletions=0,
        patch=small_diff
    )

    context = PRContext(
        repo_name="test/repo", pr_number=1,
        title="Test", description="", author="test",
        base_branch="main", head_branch="feat",
        files=[changed_file]
    )

    prompt = build_user_prompt(context)

    assert len(context.truncated_files) == 0, \
        f"Small file should NOT be truncated, but got: {context.truncated_files}"
    
    assert "truncated" not in prompt.lower() or "lines not shown] ..." not in prompt, \
        "Small file should not have truncation notice in prompt"

    print(f"\n  File lines: 50")
    print(f"  Truncation threshold: {settings.MAX_DIFF_LINES_PER_FILE}")
    print(f"  truncated_files: {context.truncated_files}")
    print(f"  Status: NOT truncated (correct!)")

    print("\n" + "=" * 60)
    print("TEST PASSED: Small files are correctly NOT truncated!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("\n" + "#" * 60)
    print("#  TESTING TRUNCATION HANDLING")
    print("#" * 60)
    
    all_passed = True
    
    try:
        test_truncation_tracking()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        all_passed = False
    
    try:
        test_prompt_contains_truncation_notice()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        all_passed = False
    
    try:
        test_small_files_not_truncated()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        all_passed = False
    
    print("\n" + "#" * 60)
    if all_passed:
        print("#  ALL TESTS PASSED!")
    else:
        print("#  SOME TESTS FAILED")
    print("#" * 60)
