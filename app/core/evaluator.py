import logging
from app.core.schemas import PRContext, ReviewResult

logger = logging.getLogger(__name__)


class EvaluatorAgent:

    def run(
        self,
        context: PRContext,
        result: ReviewResult
    ) -> dict:
        logger.info(
            f"[EvaluatorAgent] Evaluating review for "
            f"PR #{context.pr_number}"
        )

        file_line_counts = self._build_file_line_counts(context)
        comment_evaluations = self._evaluate_comments(
            result, file_line_counts
        )
        metrics = self._compute_metrics(
            context, result, comment_evaluations
        )

        logger.info(
            f"[EvaluatorAgent] Evaluation complete — "
            f"Quality: {metrics['quality_score']:.1f} | "
            f"Hallucination rate: {metrics['hallucination_rate']:.1f}% | "
            f"Coverage: {metrics['coverage_rate']:.1f}%"
        )

        return metrics, comment_evaluations

    def _build_file_line_counts(self, context: PRContext) -> dict:
        file_line_counts = {}

        for changed_file in context.files:
            if changed_file.patch:
                line_count = len(changed_file.patch.split("\n"))
                file_line_counts[changed_file.filename] = line_count
            else:
                file_line_counts[changed_file.filename] = 0

        logger.info(
            f"[EvaluatorAgent] Built line counts for "
            f"{len(file_line_counts)} files"
        )

        return file_line_counts

    def _evaluate_comments(
        self,
        result: ReviewResult,
        file_line_counts: dict
    ) -> list:
        evaluations = []

        for comment in result.comments:
            filename = comment.filename
            line = comment.line

            if filename not in file_line_counts:
                logger.warning(
                    f"[EvaluatorAgent] HALLUCINATION — "
                    f"File '{filename}' does not exist in this PR"
                )
                evaluations.append(False)
                continue

            actual_line_count = file_line_counts[filename]

            if line < 1 or line > actual_line_count:
                logger.warning(
                    f"[EvaluatorAgent] HALLUCINATION — "
                    f"Line {line} does not exist in '{filename}' "
                    f"(diff has {actual_line_count} lines)"
                )
                evaluations.append(False)
                continue

            logger.info(
                f"[EvaluatorAgent] VALID — "
                f"'{filename}' line {line} exists in diff"
            )
            evaluations.append(True)

        return evaluations

    def _compute_metrics(
        self,
        context: PRContext,
        result: ReviewResult,
        comment_evaluations: list
    ) -> dict:

        total_comments = len(result.comments)

        if total_comments > 0:
            hallucinated = comment_evaluations.count(False)
            hallucination_rate = (hallucinated / total_comments) * 100
        else:
            hallucinated = 0
            hallucination_rate = 0.0

        commented_files = set(
            c.filename for c in result.comments
        )
        total_files = len(context.files)
        files_covered = len(
            commented_files & set(
                f.filename for f in context.files
            )
        )

        if total_files > 0:
            coverage_rate = (files_covered / total_files) * 100
        else:
            coverage_rate = 0.0

        quality_score = 100.0
        quality_score -= hallucination_rate * 0.5
        quality_score += coverage_rate * 0.1
        quality_score = max(0.0, min(100.0, quality_score))

        metrics = {
            "total_comments": total_comments,
            "hallucinated_comments": hallucinated,
            "hallucination_rate": round(hallucination_rate, 2),
            "files_covered": files_covered,
            "total_files": total_files,
            "coverage_rate": round(coverage_rate, 2),
            "quality_score": round(quality_score, 2),
        }

        return metrics
