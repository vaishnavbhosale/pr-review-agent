import logging
from github import Github, GithubException
from app.config import settings
from app.core.schemas import ReviewResult, PRContext

logger = logging.getLogger(__name__)


class PosterAgent:

    def __init__(self):
        self.client = Github(settings.GITHUB_TOKEN)

    def run(self, context: PRContext, result: ReviewResult, comment_evaluations: list[bool] | None = None) -> bool:
        logger.info(f"[PosterAgent] Posting review for PR #{context.pr_number}")

        valid_count = len(result.comments)
        if comment_evaluations:
            valid_count = sum(1 for v in comment_evaluations if v)
            filtered_count = len(result.comments) - valid_count
            if filtered_count > 0:
                logger.info(f"[PosterAgent] Filtering out {filtered_count} hallucinated comments, keeping {valid_count} valid comments")

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

        summary_body = self._build_summary(context, result, comment_evaluations)
        inline_comments = self._build_inline_comments(result, comment_evaluations)

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

            try:
                pr.create_issue_comment(summary_body)
                logger.info(f"[PosterAgent] Fallback summary posted successfully")
                return True
            except GithubException as e2:
                logger.error(f"[PosterAgent] Fallback also failed: {e2}")
                return False

    def _build_summary(self, context: PRContext, result: ReviewResult, comment_evaluations: list[bool] | None = None) -> str:
        filled = "█" * result.overall_score
        empty = "░" * (10 - result.overall_score)
        score_bar = filled + empty

        if comment_evaluations:
            valid_comments = [
                c for i, c in enumerate(result.comments)
                if i < len(comment_evaluations) and comment_evaluations[i]
            ]
        else:
            valid_comments = list(result.comments)

        critical_count = sum(
            1 for c in valid_comments
            if c.severity == "critical"
        )
        warning_count = sum(
            1 for c in valid_comments
            if c.severity == "warning"
        )
        suggestion_count = sum(
            1 for c in valid_comments
            if c.severity == "suggestion"
        )

        if result.approved:
            status_line = "✅ **APPROVED**"
        else:
            status_line = "❌ **CHANGES REQUESTED**"

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
| **Total** | **{len(valid_comments)}** |

---

### 📁 Files Reviewed

| File | Status | Additions | Deletions |
|------|--------|-----------|-----------|
"""

        for f in context.files:
            body += f"| `{f.filename}` | {f.status} | +{f.additions} | -{f.deletions} |\n"

        if hasattr(context, 'truncated_files') and context.truncated_files:
            body += """
---

### ⚠️ Review Limitation Notice

**The following files were too large and have been partially reviewed:**
"""
            for tf in context.truncated_files:
                pct = round((tf['omitted_lines'] / tf['total_lines']) * 100)
                body += f"- `{tf['filename']}`: Only first {tf['shown_lines']} lines reviewed ({pct}% omitted)\n"

            body += """
*Important: Issues may exist in the un-reviewed portions of these files. Please review manually.*
"""

        body += f"""
---

*🤖 This review was generated automatically by the PR Review Agent*
*Model: Llama 3.3-70b via Groq | Reviewer confidence is not a substitute for human judgment*
"""

        return body

    def _build_inline_comments(self, result: ReviewResult, comment_evaluations: list[bool] | None = None) -> list:
        inline_comments = []

        if comment_evaluations:
            valid_comments = [
                c for i, c in enumerate(result.comments)
                if i < len(comment_evaluations) and comment_evaluations[i]
            ]
        else:
            valid_comments = list(result.comments)

        for comment in valid_comments:
            if comment.severity == "critical":
                severity_label = "🔴 CRITICAL"
            elif comment.severity == "warning":
                severity_label = "🟡 WARNING"
            else:
                severity_label = "🟢 SUGGESTION"

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
