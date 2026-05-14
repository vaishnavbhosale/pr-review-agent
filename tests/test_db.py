import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db import models  # noqa: ensure models are registered
from app.db.crud import (
    save_review,
    save_evaluation_metrics,
    get_review_by_pr,
    get_stats,
    get_all_reviews,
)
from app.core.schemas import PRContext, ChangedFile, ReviewResult, ReviewComment


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def pr_context():
    return PRContext(
        repo_name="test/repo",
        pr_number=42,
        title="Fix bug",
        description="Fixes the thing",
        author="dev1",
        base_branch="main",
        head_branch="fix-bug",
        files=[
            ChangedFile(
                filename="app/main.py",
                status="modified",
                additions=5,
                deletions=3,
                patch="@@ -1,3 +1,5 @@\n+test",
            )
        ],
    )


@pytest.fixture
def review_result():
    return ReviewResult(
        overall_score=7,
        approved=True,
        summary="Looks good",
        comments=[
            ReviewComment(
                filename="app/main.py",
                line=2,
                issue="Nit",
                suggestion="Fix",
                severity="suggestion",
            ),
        ],
    )


class TestSaveReview:
    def test_saves_review(self, db_session, pr_context, review_result):
        review = save_review(db_session, pr_context, review_result, posted=True)
        assert review.id is not None
        assert review.repo_name == "test/repo"
        assert review.pr_number == 42
        assert review.overall_score == 7
        assert review.approved is True
        assert review.posted_successfully is True

    def test_saves_comments(self, db_session, pr_context, review_result):
        review = save_review(db_session, pr_context, review_result, posted=True)
        assert len(review.comments) == 1
        assert review.comments[0].filename == "app/main.py"

    def test_saves_comment_evaluations(self, db_session, pr_context, review_result):
        review = save_review(
            db_session, pr_context, review_result, posted=True, comment_evaluations=[True]
        )
        assert review.comments[0].is_valid_line is True

    def test_false_comment_evaluation(self, db_session, pr_context, review_result):
        review = save_review(
            db_session, pr_context, review_result, posted=True, comment_evaluations=[False]
        )
        assert review.comments[0].is_valid_line is False

    def test_posted_false(self, db_session, pr_context, review_result):
        review = save_review(db_session, pr_context, review_result, posted=False)
        assert review.posted_successfully is False


class TestGetReviewByPr:
    def test_finds_existing_review(self, db_session, pr_context, review_result):
        save_review(db_session, pr_context, review_result, posted=True)
        found = get_review_by_pr(db_session, "test/repo", 42)
        assert found is not None
        assert found.pr_number == 42
        assert found.pr_title == "Fix bug"

    def test_returns_none_for_missing(self, db_session):
        found = get_review_by_pr(db_session, "test/repo", 999)
        assert found is None

    def test_filters_by_repo_name(self, db_session, pr_context, review_result):
        save_review(db_session, pr_context, review_result, posted=True)
        pr_context2 = PRContext(
            repo_name="different/repo",
            pr_number=42,
            title="Other repo PR",
            description="",
            author="dev1",
            base_branch="main",
            head_branch="fix-bug",
            files=[],
        )
        save_review(db_session, pr_context2, review_result, posted=True)
        found = get_review_by_pr(db_session, "test/repo", 42)
        assert found is not None
        assert found.repo_name == "test/repo"


class TestSaveEvaluationMetrics:
    def test_saves_metrics(self, db_session, pr_context, review_result):
        review = save_review(db_session, pr_context, review_result, posted=True)
        metrics = {
            "total_comments": 1,
            "hallucinated_comments": 0,
            "hallucination_rate": 0.0,
            "files_covered": 1,
            "total_files": 1,
            "coverage_rate": 100.0,
            "quality_score": 95.0,
        }
        saved = save_evaluation_metrics(db_session, review.id, metrics)
        assert saved.review_id == review.id
        assert saved.quality_score == 95.0
        assert saved.total_comments == 1

    def test_low_quality_score(self, db_session, pr_context, review_result):
        review = save_review(db_session, pr_context, review_result, posted=True)
        metrics = {
            "total_comments": 5,
            "hallucinated_comments": 3,
            "hallucination_rate": 60.0,
            "files_covered": 0,
            "total_files": 1,
            "coverage_rate": 0.0,
            "quality_score": 30.0,
        }
        saved = save_evaluation_metrics(db_session, review.id, metrics)
        assert saved.quality_score == 30.0
        assert saved.hallucination_rate == 60.0


class TestStats:
    def test_get_stats(self, db_session, pr_context, review_result):
        save_review(db_session, pr_context, review_result, posted=True)
        stats = get_stats(db_session)
        assert stats["total_reviews"] == 1
        assert stats["approved"] == 1
        assert stats["rejected"] == 0

    def test_get_stats_rejected_review(self, db_session, pr_context):
        rejected_result = ReviewResult(
            overall_score=3,
            approved=False,
            summary="Bad",
            comments=[],
        )
        save_review(db_session, pr_context, rejected_result, posted=True)
        stats = get_stats(db_session)
        assert stats["approved"] == 0
        assert stats["rejected"] == 1

    def test_get_all_reviews(self, db_session, pr_context, review_result):
        save_review(db_session, pr_context, review_result, posted=True)
        reviews = get_all_reviews(db_session)
        assert len(reviews) == 1

    def test_get_all_reviews_orders_by_date(self, db_session, pr_context, review_result):
        save_review(db_session, pr_context, review_result, posted=True)
        pr_context2 = PRContext(
            repo_name="test/repo2",
            pr_number=100,
            title="Later",
            description="",
            author="dev1",
            base_branch="main",
            head_branch="feat",
            files=[],
        )
        save_review(db_session, pr_context2, review_result, posted=True)
        reviews = get_all_reviews(db_session)
        assert len(reviews) == 2
