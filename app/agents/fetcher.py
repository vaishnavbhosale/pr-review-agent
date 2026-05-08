import logging
from github import Github, GithubException
from app.config import settings
from app.core.schemas import PRContext, ChangedFile

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

        changed_files = []

        for github_file in pr.get_files():
            changed_file = ChangedFile(
                filename=github_file.filename,
                status=github_file.status,
                additions=github_file.additions,
                deletions=github_file.deletions,
                patch=github_file.patch if github_file.patch else "",
            )
            changed_files.append(changed_file)

        context = PRContext(
            repo_name=repo_name,
            pr_number=pr_number,
            title=pr.title,
            description=pr.body if pr.body else "No description provided",
            author=pr.user.login,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            files=changed_files,
        )

        logger.info(f"[FetcherAgent] Done. Fetched {len(changed_files)} files.")
        logger.info(f"[FetcherAgent] Total additions: {sum(f.additions for f in changed_files)}")
        logger.info(f"[FetcherAgent] Total deletions: {sum(f.deletions for f in changed_files)}")

        return context