import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.core.schemas import PRContext, ChangedFile, ReviewResult, ReviewComment, RepoContext


@pytest.fixture
def sample_pr_context():
    return PRContext(
        repo_name="test/repo",
        pr_number=1,
        title="Test PR",
        description="Test description",
        author="testuser",
        base_branch="main",
        head_branch="feature",
        files=[
            ChangedFile(
                filename="src/auth.py",
                status="modified",
                additions=10,
                deletions=2,
                patch="@@ -1,5 +1,10 @@\n+new line 1\n+new line 2\n+new line 3",
            ),
            ChangedFile(
                filename="src/utils.py",
                status="added",
                additions=20,
                deletions=0,
                patch="@@ -0,0 +1,20 @@\n+line 1\n+line 2",
            ),
        ],
        repo_context=RepoContext(
            name="test/repo",
            description="A test repo",
            primary_language="Python",
            languages="Python, JavaScript",
            file_structure="src/\ntests/",
            readme_summary="Test repo summary",
        ),
    )


@pytest.fixture
def sample_review_result():
    return ReviewResult(
        overall_score=8,
        approved=True,
        summary="Good PR with minor issues.",
        comments=[
            ReviewComment(
                filename="src/auth.py",
                line=3,
                issue="Missing error handling",
                suggestion="Add try-except block",
                severity="warning",
            ),
            ReviewComment(
                filename="src/utils.py",
                line=5,
                issue="Unclear variable name",
                suggestion="Rename to something more descriptive",
                severity="suggestion",
            ),
        ],
    )
