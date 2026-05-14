import json
import hmac
import hashlib
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app, verify_github_signature
from app.config import settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_secret(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "test_secret")


def _sign(payload: bytes, secret: str = "test_secret") -> str:
    return "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()


class TestVerifySignature:
    def test_valid_signature(self):
        payload = b'{"test": "data"}'
        sig = _sign(payload)
        assert verify_github_signature(payload, sig) is True

    def test_invalid_signature(self):
        assert verify_github_signature(b'{"test": "data"}', "sha256=invalid") is False

    def test_empty_signature(self):
        payload = b'{"test": "data"}'
        assert verify_github_signature(payload, "") is False

    def test_tampered_payload(self):
        payload = b'{"test": "data"}'
        sig = _sign(payload)
        assert verify_github_signature(b'{"test": "tampered"}', sig) is False


class TestWebhookEndpoint:
    @patch("app.main.run_pipeline")
    def test_valid_pr_opened(self, mock_pipeline, client):
        payload = {
            "action": "opened",
            "pull_request": {"number": 1},
            "repository": {"full_name": "test/repo"},
        }
        body = json.dumps(payload).encode()
        response = client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"
        mock_pipeline.assert_called_once_with("test/repo", 1)

    @patch("app.main.run_pipeline")
    def test_valid_pr_synchronize(self, mock_pipeline, client):
        payload = {
            "action": "synchronize",
            "pull_request": {"number": 2},
            "repository": {"full_name": "test/repo"},
        }
        body = json.dumps(payload).encode()
        response = client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert response.status_code == 202
        mock_pipeline.assert_called_once_with("test/repo", 2)

    def test_invalid_signature_rejected(self, client):
        payload = {
            "action": "opened",
            "pull_request": {"number": 1},
            "repository": {"full_name": "test/repo"},
        }
        body = json.dumps(payload).encode()
        response = client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=bad",
            },
        )
        assert response.status_code == 401

    def test_wrong_event_type_ignored(self, client):
        payload = {
            "action": "opened",
            "pull_request": {"number": 1},
            "repository": {"full_name": "test/repo"},
        }
        body = json.dumps(payload).encode()
        response = client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"

    def test_wrong_action_ignored(self, client):
        payload = {
            "action": "closed",
            "pull_request": {"number": 1},
            "repository": {"full_name": "test/repo"},
        }
        body = json.dumps(payload).encode()
        response = client.post(
            "/webhook/github",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(body),
            },
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
