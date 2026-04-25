"""HTTP smoke test for the /chat endpoint with InMemorySaver."""

from __future__ import annotations

import os

import pytest


@pytest.mark.agentic
def test_chat_endpoint_smoke():
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")

    os.environ["USE_MEMORY_CHECKPOINTER"] = "1"

    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        thread = "smoke-thread"
        r1 = client.post(
            f"/chat/{thread}",
            json={"message": "doctor mi pelao tiene fiebre"},
            headers={"X-API-Key": "default_api_key_secret_12345"},
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert "response" in body1
        assert body1["response"].strip(), "empty bot response"

        r2 = client.post(
            f"/chat/{thread}",
            json={"message": "tiene 4 años, pesa 16 kilos"},
            headers={"X-API-Key": "default_api_key_secret_12345"},
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["response"].strip()
