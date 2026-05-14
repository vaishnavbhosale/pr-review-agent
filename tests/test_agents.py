import pytest
from app.agents.reviewer import ReviewerAgent
from app.core.schemas import ReviewResult


@pytest.fixture
def reviewer():
    return ReviewerAgent()


class TestParseJson:
    def test_pure_json(self, reviewer):
        raw = '{"overall_score": 8, "approved": true, "summary": "Good", "comments": []}'
        result = reviewer._parse_json(raw)
        assert result["overall_score"] == 8
        assert result["approved"] is True

    def test_with_json_codeblock(self, reviewer):
        raw = '```json\n{"overall_score": 7, "approved": false, "summary": "Ok", "comments": []}\n```'
        result = reviewer._parse_json(raw)
        assert result["overall_score"] == 7
        assert result["approved"] is False

    def test_with_plain_codeblock(self, reviewer):
        raw = '```\n{"overall_score": 9, "approved": true, "summary": "Great", "comments": []}\n```'
        result = reviewer._parse_json(raw)
        assert result["overall_score"] == 9

    def test_fallback_on_invalid_json(self, reviewer):
        result = reviewer._parse_json("this is not json")
        assert result["overall_score"] == 5
        assert result["approved"] is False
        assert "could not be parsed" in result["summary"]

    def test_empty_string(self, reviewer):
        result = reviewer._parse_json("")
        assert result["overall_score"] == 5

    def test_extra_whitespace(self, reviewer):
        raw = '  \n  {"overall_score": 6, "approved": true, "summary": "Meh", "comments": []}  \n  '
        result = reviewer._parse_json(raw)
        assert result["overall_score"] == 6

    def test_json_only_start_codeblock(self, reviewer):
        raw = '```json\n{"overall_score": 10, "approved": true, "summary": "Perfect", "comments": []}'
        result = reviewer._parse_json(raw)
        assert result["overall_score"] == 10

    def test_codeblock_no_newline(self, reviewer):
        raw = '```{"overall_score": 5, "approved": false, "summary": "Bad", "comments": []}```'
        result = reviewer._parse_json(raw)
        assert result["overall_score"] == 5


class TestBuildResult:
    def test_valid_data(self, reviewer):
        data = {
            "overall_score": 8,
            "approved": True,
            "summary": "Nice PR",
            "comments": [
                {
                    "filename": "app/main.py",
                    "line": 5,
                    "issue": "Bug",
                    "suggestion": "Fix it",
                    "severity": "critical",
                }
            ],
        }
        result = reviewer._build_result(data)
        assert isinstance(result, ReviewResult)
        assert result.overall_score == 8
        assert result.approved is True
        assert len(result.comments) == 1
        assert result.comments[0].filename == "app/main.py"
        assert result.comments[0].severity == "critical"

    def test_missing_comments_defaults_empty(self, reviewer):
        data = {"overall_score": 6, "approved": False, "summary": "Needs work"}
        result = reviewer._build_result(data)
        assert result.overall_score == 6
        assert result.comments == []

    def test_empty_comments(self, reviewer):
        data = {
            "overall_score": 10,
            "approved": True,
            "summary": "Perfect",
            "comments": [],
        }
        result = reviewer._build_result(data)
        assert result.overall_score == 10
        assert len(result.comments) == 0

    def test_missing_key_fallback(self, reviewer):
        data = {}
        result = reviewer._build_result(data)
        assert result.overall_score == 5
        assert result.approved is False
        assert result.comments == []

    def test_wrong_types_fallback(self, reviewer):
        data = {
            "overall_score": "not_an_int",
            "approved": "not_a_bool",
            "summary": 123,
        }
        result = reviewer._build_result(data)
        assert result.overall_score == 5
        assert result.comments == []

    def test_multiple_comments(self, reviewer):
        data = {
            "overall_score": 7,
            "approved": False,
            "summary": "Several issues",
            "comments": [
                {
                    "filename": "a.py",
                    "line": 1,
                    "issue": "Issue 1",
                    "suggestion": "Fix 1",
                    "severity": "critical",
                },
                {
                    "filename": "b.py",
                    "line": 10,
                    "issue": "Issue 2",
                    "suggestion": "Fix 2",
                    "severity": "warning",
                },
                {
                    "filename": "c.py",
                    "line": 20,
                    "issue": "Issue 3",
                    "suggestion": "Fix 3",
                    "severity": "suggestion",
                },
            ],
        }
        result = reviewer._build_result(data)
        assert len(result.comments) == 3
        assert result.comments[0].severity == "critical"
        assert result.comments[1].severity == "warning"
        assert result.comments[2].severity == "suggestion"
