import logging
from github import Github, GithubException
from app.config import settings
from app.core.schemas import ReviewResult, PRContext

logger = logging.getLogger(__name__)


class PosterAgent:
    """
    Agent 3 — Poster.

    Takes the ReviewResult from the Reviewer Agent.
    Formats it into professional Markdown.
    Posts it back to the GitHub Pull Request.

    Posts two things:
    1. A PR level summary comment with score and overview table
    2. Inline comments on specific files and lines
    """

    def __init__(self):
        self.client = Github(settings.GITHUB_TOKEN)

    def run(self, context: PRContext, result: ReviewResult) -> bool:
        logger.info(f"[PosterAgent] Posting review for PR #{context.pr_number}")

        try:
            repo = self.client.get_repo(context.repo_name)
            pr = repo.get_pull(context.pr_number)
        except GithubException as e:
            logger.error(f"[PosterAgent] Could not access PR: {e}")
            return False


        try:
            bot_user = self.client.get_user().login
        except GithubException as e:
            logger.warning(f"[PosterAgent] Could not fetch bot username: {e}. Defaulting to COMMENT.")
            bot_user = None

        is_self_pr = bot_user is not None and context.author == bot_user

        if is_self_pr:
            logger.warning(
                f"[PosterAgent] PR author '{context.author}' matches bot user '{bot_user}' "
                f"— switching event to COMMENT to avoid GitHub 422"
            )
            review_event = "COMMENT"
        elif result.approved:
            review_event = "APPROVE"
        else:
            review_event = "REQUEST_CHANGES"

        # Step 1 — Build the main summary comment body
        summary_body = self._build_summary(context, result)

        # Step 2 — Build inline comments list
        inline_comments = self._build_inline_comments(result)

        # Step 3 — Submit everything in one API call
        try:
            pr.create_review(
                body=summary_body,
                event=review_event,
                comments=inline_comments,
            )
            logger.info(
                f"[PosterAgent] Review posted successfully. "
                f"Verdict: {review_event}"
            )
            return True

        except GithubException as e:
            logger.error(f"[PosterAgent] Failed to post full review: {e}")
            logger.info(f"[PosterAgent] Attempting fallback — posting summary only")

            # Fallback — if inline comments fail, post just the summary.
            # This happens when line numbers from the AI do not match
            # the actual diff positions GitHub expects.
            try:
                pr.create_issue_comment(summary_body)
                logger.info(f"[PosterAgent] Fallback summary posted successfully")
                return True
            except GithubException as e2:
                logger.error(f"[PosterAgent] Fallback also failed: {e2}")
                return False

    def _build_summary(self, context: PRContext, result: ReviewResult) -> str:
        """
        Builds the main PR level summary comment in Markdown.
        This is what the developer sees first when the review is posted.
        """

        # Build a visual score bar
        # Example: score 7 → ███████░░░
        filled = "█" * result.overall_score
        empty = "░" * (10 - result.overall_score)
        score_bar = filled + empty

        # Count issues by severity
        critical_count = sum(
            1 for c in result.comments
            if c.severity == "critical"
        )
        warning_count = sum(
            1 for c in result.comments
            if c.severity == "warning"
        )
        suggestion_count = sum(
            1 for c in result.comments
            if c.severity == "suggestion"
        )

        # Decide status emoji
        if result.approved:
            status_line = "✅ **APPROVED**"
        else:
            status_line = "❌ **CHANGES REQUESTED**"

        # Build the markdown body
        body = f"""## 🤖 AI Code Review

{status_line}

**Score:** `{score_bar}` {result.overall_score}/10

---

### 📋 Summary

{result.summary}

---

### 📊 Issues Found

| Severity | Count |
|----------|-------|
| 🔴 Critical | {critical_count} |
| 🟡 Warning | {warning_count} |
| 🟢 Suggestion | {suggestion_count} |
| **Total** | **{len(result.comments)}** |

---

### 📁 Files Reviewed

| File | Status | Additions | Deletions |
|------|--------|-----------|-----------|
"""

        for f in context.files:
            body += f"| `{f.filename}` | {f.status} | +{f.additions} | -{f.deletions} |\n"

        body += f"""
---

*🤖 This review was generated automatically by the PR Review Agent*
*Model: Llama 3.3-70b via Groq | Reviewer confidence is not a substitute for human judgment*
"""

        return body

    def _build_inline_comments(self, result: ReviewResult) -> list:
        """
        Builds the list of inline comments for GitHub's review API.

        Each comment needs:
        - path: the file path
        - position: line number in the diff
        - body: the formatted comment text
        """

        inline_comments = []

        for comment in result.comments:

            # Format the severity with emoji
            if comment.severity == "critical":
                severity_label = "🔴 CRITICAL"
            elif comment.severity == "warning":
                severity_label = "🟡 WARNING"
            else:
                severity_label = "🟢 SUGGESTION"

            # Build the inline comment body in markdown
            comment_body = f"""### {severity_label}

**Issue:** {comment.issue}

**Suggestion:** {comment.suggestion}

---
*Generated by AI Code Review Agent*"""

            inline_comments.append({
                "path": comment.filename,
                "position": comment.line,
                "body": comment_body,
            })

        return inline_comments