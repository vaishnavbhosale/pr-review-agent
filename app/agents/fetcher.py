import logging
from github import Github, GithubException
from app.config import settings
from app.core.schemas import PRContext, ChangedFile, RepoContext

logger = logging.getLogger(__name__)


class FetcherAgent:

    def __init__(self):
        self.client = Github(settings.GITHUB_TOKEN)

    def run(self, repo_name: str, pr_number: int) -> PRContext:
        logger.info(f"[FetcherAgent] Starting fetch for PR #{pr_number} in {repo_name}")

        try:
            repo = self.client.get_repo(repo_name)
        except GithubException as e:
            logger.error(f"[FetcherAgent] Could not find repo {repo_name}. Error: {e}")
            raise

        try:
            pr = repo.get_pull(pr_number)
        except GithubException as e:
            logger.error(f"[FetcherAgent] Could not find PR #{pr_number}. Error: {e}")
            raise

        # Fetch changed files
        changed_files = []
        for github_file in pr.get_files():
            changed_files.append(ChangedFile(
                filename=github_file.filename,
                status=github_file.status,
                additions=github_file.additions,
                deletions=github_file.deletions,
                patch=github_file.patch if github_file.patch else "",
            ))

        # Fetch repo context
        repo_context = self._fetch_repo_context(repo)

        context = PRContext(
            repo_name=repo_name,
            pr_number=pr_number,
            title=pr.title,
            description=pr.body if pr.body else "No description provided",
            author=pr.user.login,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            files=changed_files,
            repo_context=repo_context,
        )

        logger.info(
            f"[FetcherAgent] Done. "
            f"Files: {len(changed_files)} | "
            f"Repo context fetched: True"
        )

        return context

    def _fetch_repo_context(self, repo) -> RepoContext:
        """
        Fetches contextual information about the repository.
        This gives the AI reviewer knowledge about the codebase
        beyond just the PR diff — what the project does, what
        languages it uses, what the file structure looks like,
        and what kind of PRs this team typically merges.
        """
        logger.info(f"[FetcherAgent] Fetching repo context for {repo.full_name}")

        # 1 — Basic repo info
        description = repo.description or "No description provided"
        primary_language = repo.language or "Unknown"

        # 2 — All languages used in the repo
        try:
            languages_dict = repo.get_languages()
            languages = ", ".join(languages_dict.keys())
        except Exception:
            languages = primary_language

        # 3 — Top level file structure
        try:
            contents = repo.get_contents("")
            file_structure = "\n".join([
                f"{'📁' if c.type == 'dir' else '📄'} {c.name}"
                for c in contents
            ])
        except Exception:
            file_structure = "Could not fetch file structure"

        # 4 — README content (first 1500 chars)
        try:
            readme = repo.get_readme()
            readme_content = readme.decoded_content.decode("utf-8")
            readme_summary = readme_content[:1500]
            if len(readme_content) > 1500:
                readme_summary += "\n... [README truncated]"
        except Exception:
            readme_summary = "No README available"

        # 5 — Recent merged PR titles (last 5)
        try:
            merged_prs = repo.get_pulls(
                state="closed",
                sort="updated",
                direction="desc"
            )
            recent_pr_titles = []
            count = 0
            for merged_pr in merged_prs:
                if merged_pr.merged:
                    recent_pr_titles.append(
                        f"- {merged_pr.title} (by {merged_pr.user.login})"
                    )
                    count += 1
                if count >= 5:
                    break
        except Exception:
            recent_pr_titles = []

        logger.info(
            f"[FetcherAgent] Repo context fetched — "
            f"Language: {primary_language} | "
            f"Recent PRs: {len(recent_pr_titles)}"
        )

        return RepoContext(
            name=repo.full_name,
            description=description,
            primary_language=primary_language,
            languages=languages,
            file_structure=file_structure,
            readme_summary=readme_summary,
            recent_pr_titles=recent_pr_titles,
        )