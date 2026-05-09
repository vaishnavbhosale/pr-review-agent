from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    Float,
    ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class PRReview(Base):
    """
    Stores one row for every PR that was reviewed.
    One PRReview has many ReviewComments.
    """

    __tablename__ = "pr_reviews"

    id = Column(Integer, primary_key=True, index=True)
    repo_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String(500), nullable=True)
    author = Column(String(100), nullable=True)
    overall_score = Column(Integer, nullable=True)
    approved = Column(Boolean, nullable=True)
    summary = Column(Text, nullable=True)
    posted_successfully = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    comments = relationship(
        "ReviewComment",
        back_populates="review",
        cascade="all, delete-orphan"
    )

    metrics = relationship(
        "EvaluationMetrics",
        back_populates="review",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<PRReview "
            f"id={self.id} "
            f"repo={self.repo_name} "
            f"pr={self.pr_number} "
            f"score={self.overall_score}>"
        )


class ReviewComment(Base):
    """
    Stores one row for every comment the AI made on a PR.
    Many ReviewComments belong to one PRReview.
    """

    __tablename__ = "review_comments"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(
        Integer,
        ForeignKey("pr_reviews.id"),
        nullable=False
    )
    filename = Column(String(500), nullable=True)
    line = Column(Integer, nullable=True)
    issue = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    severity = Column(String(50), nullable=True)

    # Evaluation fields
    # True  = line exists in the diff, comment is valid
    # False = line does not exist, this is a hallucination
    # None  = not yet evaluated
    is_valid_line = Column(Boolean, nullable=True)

    # True  = developer dismissed this comment (false positive signal)
    # False = developer accepted this comment
    # None  = not yet recorded
    was_dismissed = Column(Boolean, nullable=True)

    review = relationship(
        "PRReview",
        back_populates="comments"
    )

    def __repr__(self):
        return (
            f"<ReviewComment "
            f"id={self.id} "
            f"severity={self.severity} "
            f"valid={self.is_valid_line}>"
        )


class EvaluationMetrics(Base):
    """
    Stores computed evaluation metrics for each PR review.
    One EvaluationMetrics row per PRReview.
    """

    __tablename__ = "evaluation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(
        Integer,
        ForeignKey("pr_reviews.id"),
        nullable=False,
        unique=True
    )

    # Total number of comments the AI made
    total_comments = Column(Integer, default=0)

    # Comments where the line number does not exist in the diff
    hallucinated_comments = Column(Integer, default=0)

    # Hallucination rate as a percentage 0.0 to 100.0
    hallucination_rate = Column(Float, default=0.0)

    # Number of files in the PR that had at least one comment
    files_covered = Column(Integer, default=0)

    # Total files in the PR
    total_files = Column(Integer, default=0)

    # Coverage percentage 0.0 to 100.0
    coverage_rate = Column(Float, default=0.0)

    # Overall quality score for this review 0.0 to 100.0
    # Computed from hallucination rate and coverage
    quality_score = Column(Float, default=0.0)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    review = relationship(
        "PRReview",
        back_populates="metrics"
    )

    def __repr__(self):
        return (
            f"<EvaluationMetrics "
            f"review_id={self.review_id} "
            f"quality={self.quality_score:.1f} "
            f"hallucination={self.hallucination_rate:.1f}%>"
        )