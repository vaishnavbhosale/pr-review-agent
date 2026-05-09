from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
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

    # One PRReview has many ReviewComments
    comments = relationship(
        "ReviewComment",
        back_populates="review",
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

    # Many ReviewComments belong to one PRReview
    review = relationship(
        "PRReview",
        back_populates="comments"
    )

    def __repr__(self):
        return (
            f"<ReviewComment "
            f"id={self.id} "
            f"review_id={self.review_id} "
            f"severity={self.severity} "
            f"file={self.filename}>"
        )