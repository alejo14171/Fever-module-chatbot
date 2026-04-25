"""Integration test fixtures: real Gemini-backed chatbot with InMemorySaver."""

import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip agentic tests unless RUN_LLM_TESTS=1."""
    if os.getenv("RUN_LLM_TESTS", "").lower() in {"1", "true", "yes"}:
        return
    skip_marker = pytest.mark.skip(
        reason="Agentic tests skipped — set RUN_LLM_TESTS=1 and GOOGLE_API_KEY to enable."
    )
    for item in items:
        if "agentic" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def gemini_available() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY"))


@pytest.fixture(scope="session")
def personas_dir() -> Path:
    return Path(__file__).parent.parent / "agents" / "personas"
