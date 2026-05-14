SYSTEM_PROMPT = """
You are an expert software engineer performing a code review.
You have deep knowledge of security vulnerabilities, performance
optimization, clean code principles, and software design patterns.

You will be given:
1. Context about the repository — what it does, its tech stack,
   file structure, and recent merged PRs
2. The pull request diff — what changed in this PR

Use the repository context to give REPO-AWARE feedback.
This means:
- Understand the project's purpose before reviewing
- Consider the tech stack when flagging issues
- Follow patterns consistent with this codebase
- Reference the existing structure when suggesting improvements

Your response must be a valid JSON object. No extra text before
or after the JSON. Use exactly this structure:

{
    "overall_score": <integer between 1 and 10>,
    "approved": <true if score >= 7 and no critical issues>,
    "summary": "<2-3 sentences about the PR in context of this repo>",
    "comments": [
        {
            "filename": "<exact filename from the diff>",
            "line": <line number as integer>,
            "issue": "<specific issue referencing repo context where relevant>",
            "suggestion": "<actionable fix consistent with this codebase>",
            "severity": "<critical|warning|suggestion>"
        }
    ]
}

Rules:
- Only comment on lines that exist in the diff
- critical = security risks, data loss, crashes
- warning = bugs, bad patterns, logic errors
- suggestion = improvements, readability, performance
- Reference the repo context in your summary
- If the code follows existing repo patterns, acknowledge it
- Return ONLY the JSON. No markdown, no explanation.
"""


def build_user_prompt(context) -> str:
    prompt = ""

    if context.repo_context:
        rc = context.repo_context
        prompt += "=" * 60 + "\n"
        prompt += "REPOSITORY CONTEXT\n"
        prompt += "=" * 60 + "\n"
        prompt += f"Repository     : {rc.name}\n"
        prompt += f"Description    : {rc.description}\n"
        prompt += f"Primary Lang   : {rc.primary_language}\n"
        prompt += f"All Languages  : {rc.languages}\n"
        prompt += "\n"

        prompt += "File Structure:\n"
        prompt += rc.file_structure + "\n\n"

        if rc.recent_pr_titles:
            prompt += "Recent Merged PRs (what this team ships):\n"
            for title in rc.recent_pr_titles:
                prompt += title + "\n"
            prompt += "\n"

        prompt += "README Summary:\n"
        prompt += rc.readme_summary + "\n\n"

    prompt += "=" * 60 + "\n"
    prompt += "PULL REQUEST\n"
    prompt += "=" * 60 + "\n"
    prompt += f"PR Number  : #{context.pr_number}\n"
    prompt += f"Title      : {context.title}\n"
    prompt += f"Author     : {context.author}\n"
    prompt += f"Description: {context.description}\n"
    prompt += f"Base Branch: {context.base_branch}\n"
    prompt += f"Head Branch: {context.head_branch}\n"
    prompt += f"Files Changed: {len(context.files)}\n\n"

    prompt += "=" * 60 + "\n"
    prompt += "CODE CHANGES\n"
    prompt += "=" * 60 + "\n"

    skip_patterns = [
        "package-lock.json",
        "yarn.lock",
        "poetry.lock",
        ".min.js",
        ".min.css",
        "requirements.txt",
        "Pipfile.lock",
    ]

    for changed_file in context.files:

        if not changed_file.patch:
            continue

        should_skip = any(
            pattern in changed_file.filename
            for pattern in skip_patterns
        )

        if should_skip:
            continue

        prompt += f"\nFile   : {changed_file.filename}\n"
        prompt += f"Status : {changed_file.status}\n"
        prompt += f"Changes: +{changed_file.additions} additions, "
        prompt += f"-{changed_file.deletions} deletions\n"
        prompt += "Diff:\n"

        diff_lines = changed_file.patch.split("\n")

        if len(diff_lines) > 300:
            truncated = "\n".join(diff_lines[:300])
            prompt += truncated
            prompt += (
                f"\n... [diff truncated — "
                f"{len(diff_lines) - 300} lines not shown] ...\n"
            )
        else:
            prompt += changed_file.patch

        prompt += "\n"

    if hasattr(context, 'rag_context') and context.rag_context:
        prompt += "=" * 60 + "\n"
        prompt += "SEMANTICALLY RELATED CODE FROM THE CODEBASE\n"
        prompt += "(Retrieved based on similarity to this PR's changes)\n"
        prompt += "=" * 60 + "\n"
        prompt += context.rag_context + "\n\n"

    prompt += "\n" + "=" * 60 + "\n"
    prompt += "Provide your repo-aware structured JSON review now:\n"

    return prompt
