import json
import logging
from groq import Groq
from app.config import settings
from app.core.schemas import PRContext, ReviewResult, ReviewComment
from app.core.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class ReviewerAgent:

    MODEL = "llama-3.3-70b-versatile"
    MAX_TOKENS = 4096
    TEMPERATURE = 0.1

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def run(self, context: PRContext) -> ReviewResult:
        logger.info(f"[ReviewerAgent] Starting review for PR #{context.pr_number}")

        user_prompt = build_user_prompt(context)

        prompt_length = len(user_prompt)
        logger.info(f"[ReviewerAgent] Prompt size: {prompt_length} characters")

        if prompt_length > 100000:
            logger.warning(f"[ReviewerAgent] Prompt is very large. Consider chunking this PR.")

        logger.info(f"[ReviewerAgent] Sending prompt to {self.MODEL}")

        try:
            response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system",
                     "content": SYSTEM_PROMPT
                     },
                    {"role": "user",
                     "content": user_prompt
                     }
                ],
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
            )
        except Exception as e:
            logger.error(f"[ReviewerAgent] Groq API call failed: {e}")
            raise

        raw_response = response.choices[0].message.content
        logger.info(f"[ReviewerAgent] Received response from Groq")

        review_data = self._parse_json(raw_response)
        result = self._build_result(review_data)

        logger.info(
            f"[ReviewerAgent] Review complete. "
            f"Score: {result.overall_score}/10 | "
            f"Approved: {result.approved} | "
            f"Comments: {len(result.comments)}"
        )

        return result

    def _parse_json(self, raw_response: str) -> dict:
        cleaned = raw_response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]

        if cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"[ReviewerAgent] Failed to parse JSON: {e}")
            logger.error(f"[ReviewerAgent] Raw response was: {raw_response[:500]}")

            return {
                "overall_score": 5,
                "approved": False,
                "summary": "Review could not be parsed. Please review manually.",
                "comments": []
            }

    def _build_result(self, data: dict) -> ReviewResult:
        try:
            comments = [
                ReviewComment(
                    filename=c["filename"],
                    line=c["line"],
                    issue=c["issue"],
                    suggestion=c["suggestion"],
                    severity=c["severity"]
                )
                for c in data.get("comments", [])
            ]

            result = ReviewResult(
                overall_score=data["overall_score"],
                approved=data["approved"],
                summary=data["summary"],
                comments=comments
            )

            return result

        except (KeyError, ValueError) as e:
            logger.error(f"[ReviewerAgent] Failed to build ReviewResult: {e}")
            logger.error(f"[ReviewerAgent] Data received: {data}")

            return ReviewResult(
                overall_score=5,
                approved=False,
                summary="Review structure was invalid. Please review manually.",
                comments=[]
            )
