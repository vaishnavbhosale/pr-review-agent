from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class PRReview(Base):
    __tablename__ = "pr_reviews"

    # Uncomment to enforce one review per PR.
    # __table_args__ = (
    #     UniqueConstraint("repo_name", "pr_number", name="uq_repo_pr"),
    # )

    id = Column(Integer, primary_key=True, index=True)
    repo_name = Column(String(255), nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String(500), nullable=False)
    author = Column(String(100), nullable=False)
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
    is_valid_line = Column(Boolean, nullable=True)
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
    __tablename__ = "evaluation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(
        Integer,
        ForeignKey("pr_reviews.id"),
        nullable=False,
        unique=True
    )
    total_comments = Column(Integer, default=0)
    hallucinated_comments = Column(Integer, default=0)
    hallucination_rate = Column(Float, default=0.0)
    files_covered = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    coverage_rate = Column(Float, default=0.0)
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
