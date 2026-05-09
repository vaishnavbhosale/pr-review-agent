import logging
from sqlalchemy.orm import Session
from app.db.models import PRReview, ReviewComment
from app.core.schemas import PRContext, ReviewResult

logger = logging.getLogger(__name__)


def save_review(
    db: Session,
    context: PRContext,
    result: ReviewResult,
    posted: bool
) -> PRReview:
    """
    Saves a completed PR review to the database.

    Creates one PRReview row and one ReviewComment row
    for each comment the AI made.

    Returns the saved PRReview object with its generated ID.
    """

    logger.info(
        f"[DB] Saving review for PR #{context.pr_number} "
        f"in {context.repo_name}"
    )

    try:
        # Create the parent review record
        review = PRReview(
            repo_name=context.repo_name,
            pr_number=context.pr_number,
            pr_title=context.title,
            author=context.author,
            overall_score=result.overall_score,
            approved=result.approved,
            summary=result.summary,
            posted_successfully=posted,
        )

        db.add(review)

        # Flush sends the INSERT to the database but does not
        # commit yet. This gives us the auto-generated review.id
        # which we need for the foreign key in ReviewComment
        db.flush()

        logger.info(f"[DB] PRReview created with ID: {review.id}")

        # Create one comment record for each AI comment
        for c in result.comments:
            comment = ReviewComment(
                review_id=review.id,
                filename=c.filename,
                line=c.line,
                issue=c.issue,
                suggestion=c.suggestion,
                severity=c.severity,
            )
            db.add(comment)

        # Commit saves everything to disk permanently
        db.commit()

        # Refresh loads the final state from the database
        # including server-generated fields like created_at
        db.refresh(review)

        logger.info(
            f"[DB] Saved successfully — "
            f"Review ID: {review.id} | "
            f"Comments saved: {len(result.comments)}"
        )

        return review

    except Exception as e:
        # Roll back everything if anything failed
        # This ensures we never have partial data in the database
        db.rollback()
        logger.error(f"[DB] Failed to save review: {e}")
        raise


def get_review_by_pr(
    db: Session,
    repo_name: str,
    pr_number: int
) -> PRReview:
    """
    Fetches the most recent review for a specific PR.
    Returns None if no review exists for this PR.
    """

    review = db.query(PRReview).filter(
        PRReview.repo_name == repo_name,
        PRReview.pr_number == pr_number
    ).order_by(
        PRReview.created_at.desc()
    ).first()

    if review:
        logger.info(
            f"[DB] Found review for PR #{pr_number} — "
            f"ID: {review.id} | Score: {review.overall_score}"
        )
    else:
        logger.info(f"[DB] No review found for PR #{pr_number}")

    return review


def get_all_reviews(
    db: Session,
    limit: int = 50
) -> list:
    """
    Fetches the most recent reviews across all repositories.
    Limited to 50 by default to avoid loading too much data.
    """

    reviews = db.query(PRReview).order_by(
        PRReview.created_at.desc()
    ).limit(limit).all()

    logger.info(f"[DB] Fetched {len(reviews)} reviews")

    return reviews


def get_stats(db: Session) -> dict:
    """
    Returns summary statistics across all reviews.
    Useful for monitoring and dashboards.
    """

    total = db.query(PRReview).count()

    approved = db.query(PRReview).filter(
        PRReview.approved == True
    ).count()

    rejected = db.query(PRReview).filter(
        PRReview.approved == False
    ).count()

    critical_comments = db.query(ReviewComment).filter(
        ReviewComment.severity == "critical"
    ).count()

    return {
        "total_reviews": total,
        "approved": approved,
        "rejected": rejected,
        "critical_comments_found": critical_comments,
    }