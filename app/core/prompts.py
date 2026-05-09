SYSTEM_PROMPT = """
You are an expert software engineer performing a code review.
You have deep knowledge of security vulnerabilities, performance optimization, clean code principles, and software design patterns.

Your job is to review the provided pull request diff and return a structured JSON review.

You must follow these rules strictly:

1. Only comment on lines that actually exist in the diff.
2. Every comment must be specific and actionable. Do not write vague feedback.
3. Classify every issue by severity:
   - critical: security vulnerabilities, data loss risks, crashes
   - warning: bugs, bad practices, logic errors
   - suggestion: improvements, readability, performance

4. Your response must be a valid JSON object. No extra text before or after the JSON.
5. Use exactly this JSON structure:

{
    "overall_score": <integer between 1 and 10>,
    "approved": <true if score is 7 or above and no critical issues, otherwise false>,
    "summary": "<2 to 3 sentences describing the overall quality of this PR>",
    "comments": [
        {
            "filename": "<exact filename from the diff>",
            "line": <line number as integer>,
            "issue": "<clear description of the problem>",
            "suggestion": "<specific actionable fix>",
            "severity": "<critical or warning or suggestion>"
        }
    ]
}

If there are no issues found, return an empty comments array.
Do not invent issues that are not present in the code.
"""


def build_user_prompt(context) -> str:
    """
    Builds the user prompt from a PRContext object.
    This is what changes with every PR.
    """

    # Start with PR metadata
    prompt = f"""
Pull Request #{context.pr_number}
Repository: {context.repo_name}
Title: {context.title}
Description: {context.description}
Author: {context.author}
Base Branch: {context.base_branch}
Head Branch: {context.head_branch}
Total Files Changed: {len(context.files)}

"""

    # Add each file's diff
    for changed_file in context.files:

        # Skip files with no patch content
        # Binary files, deleted empty files have no diff to review
        if not changed_file.patch:
            continue

        # Skip auto-generated files and dependency files
        # These are not written by the developer and not worth reviewing
        skip_patterns = [
            "package-lock.json",
            "yarn.lock",
            "poetry.lock",
            ".min.js",
            ".min.css",
            "requirements.txt",
            "Pipfile.lock",
        ]

        should_skip = any(
            pattern in changed_file.filename
            for pattern in skip_patterns
        )

        if should_skip:
            continue

        prompt += f"File: {changed_file.filename}\n"
        prompt += f"Status: {changed_file.status}\n"
        prompt += f"Additions: {changed_file.additions} | Deletions: {changed_file.deletions}\n"
        prompt += "Diff:\n"

        # Token optimization — truncate very large diffs
        # A single file with 500+ changed lines is too large
        # We take the first 300 lines and tell the AI the rest was cut
        diff_lines = changed_file.patch.split("\n")

        if len(diff_lines) > 300:
            truncated = "\n".join(diff_lines[:300])
            prompt += truncated
            prompt += f"\n... [diff truncated — {len(diff_lines) - 300} lines not shown] ...\n"
        else:
            prompt += changed_file.patch

        prompt += "\n\n"

    prompt += "Provide your structured JSON review now:"

    return prompt