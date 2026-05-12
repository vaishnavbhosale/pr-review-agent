import sys
import os

# Ensure app can be imported from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import httpx
import hmac
import hashlib
import json
from app.config import settings

WEBHOOK_URL = "http://127.0.0.1:8000/webhook/github"


def generate_signature(payload_bytes: bytes) -> str:
    """Generate the fake GitHub HMAC signature"""
    return "sha256=" + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

async def fire_webhook(pr_number: int, client: httpx.AsyncClient):
    """Simulate a GitHub webhook payload for a PR"""
    payload = {
        "action": "opened",
        "pull_request": {"number": pr_number},
        "repository": {"full_name": "vaishnavbhosale/test-pr-review"}
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = generate_signature(payload_bytes)

    headers = {
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": signature,
        "Content-Type": "application/json"
    }

    print(f"[Request] Firing webhook for PR #{pr_number}...")
    response = await client.post(WEBHOOK_URL, content=payload_bytes, headers=headers)
    print(f"[Response] PR #{pr_number} -> {response.status_code} {response.json()}")

async def main():
    print("--- Running Concurrency & Webhook Test ---")
    # Simulate 3 webhooks hitting your server at the exact same second
    async with httpx.AsyncClient() as client:
        tasks = [fire_webhook(i, client) for i in range(10, 13)]
        await asyncio.gather(*tasks)
    
    print("\n✅ TEST PASSED: Webhooks fired. Check your FastAPI logs to watch the orchestrator queue them up safely!")

if __name__ == "__main__":
    asyncio.run(main())