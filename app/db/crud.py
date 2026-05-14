import logging
from sqlalchemy.orm import Session
from app.db.models import PRReview, ReviewComment, EvaluationMetrics
from app.core.schemas import PRContext, ReviewResult

logger = logging.getLogger(__name__)


def save_review(
    db: Session,
    context: PRContext,
    result: ReviewResult,
    posted: bool,
    comment_evaluations: list = None
) -> PRReview:

    logger.info(
        f"[DB] Saving review for PR #{context.pr_number} "
        f"in {context.repo_name}"
    )

    try:
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
        db.flush()

        logger.info(f"[DB] PRReview created with ID: {review.id}")

        for i, c in enumerate(result.comments):
            is_valid = None
            if comment_evaluations and i < len(comment_evaluations):
                is_valid = comment_evaluations[i]

            comment = ReviewComment(
                review_id=review.id,
                filename=c.filename,
                line=c.line,
                issue=c.issue,
                suggestion=c.suggestion,
                severity=c.severity,
                is_valid_line=is_valid,
            )
            db.add(comment)

        db.commit()
        db.refresh(review)

        logger.info(
            f"[DB] Saved successfully — "
            f"Review ID: {review.id} | "
            f"Comments: {len(result.comments)}"
        )

        return review

    except Exception as e:
        db.rollback()
        logger.error(f"[DB] Failed to save review: {e}")
        raise


def save_evaluation_metrics(
    db: Session,
    review_id: int,
    metrics: dict
) -> EvaluationMetrics:

    logger.info(f"[DB] Saving evaluation metrics for review {review_id}")

    try:
        eval_metrics = EvaluationMetrics(
            review_id=review_id,
            total_comments=metrics["total_comments"],
            hallucinated_comments=metrics["hallucinated_comments"],
            hallucination_rate=metrics["hallucination_rate"],
            files_covered=metrics["files_covered"],
            total_files=metrics["total_files"],
            coverage_rate=metrics["coverage_rate"],
            quality_score=metrics["quality_score"],
        )

        db.add(eval_metrics)
        db.commit()
        db.refresh(eval_metrics)

        logger.info(
            f"[DB] Metrics saved — "
            f"Quality: {eval_metrics.quality_score} | "
            f"Hallucination rate: {eval_metrics.hallucination_rate}%"
        )

        return eval_metrics

    except Exception as e:
        db.rollback()
        logger.error(f"[DB] Failed to save metrics: {e}")
        raise


def get_review_by_pr(
    db: Session,
    repo_name: str,
    pr_number: int
) -> PRReview:

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

    reviews = db.query(PRReview).order_by(
        PRReview.created_at.desc()
    ).limit(limit).all()

    logger.info(f"[DB] Fetched {len(reviews)} reviews")

    return reviews


def get_stats(db: Session) -> dict:

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

    hallucinated = db.query(ReviewComment).filter(
        ReviewComment.is_valid_line == False
    ).count()

    valid_comments = db.query(ReviewComment).filter(
        ReviewComment.is_valid_line == True
    ).count()

    return {
        "total_reviews": total,
        "approved": approved,
        "rejected": rejected,
        "critical_comments_found": critical_comments,
        "hallucinated_comments": hallucinated,
        "valid_comments": valid_comments,
    }


def get_evaluation_report(db: Session) -> dict:

    all_metrics = db.query(EvaluationMetrics).all()

    if not all_metrics:
        return {
            "message": "No evaluation data yet",
            "total_reviews_evaluated": 0,
        }

    total = len(all_metrics)

    avg_quality = sum(
        m.quality_score for m in all_metrics
    ) / total

    avg_hallucination = sum(
        m.hallucination_rate for m in all_metrics
    ) / total

    avg_coverage = sum(
        m.coverage_rate for m in all_metrics
    ) / total

    total_hallucinations = sum(
        m.hallucinated_comments for m in all_metrics
    )

    total_comments = sum(
        m.total_comments for m in all_metrics
    )

    return {
        "total_reviews_evaluated": total,
        "average_quality_score": round(avg_quality, 2),
        "average_hallucination_rate": round(avg_hallucination, 2),
        "average_coverage_rate": round(avg_coverage, 2),
        "total_comments_made": total_comments,
        "total_hallucinations_detected": total_hallucinations,
    }
