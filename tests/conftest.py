import os

# Set env vars before importing the app — keep tests isolated from real DB.
os.environ.setdefault("DB_URI", "memory://")
os.environ.setdefault("USE_MEMORY_CHECKPOINTER", "1")
os.environ.setdefault("API_KEY", "default_api_key_secret_12345")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import verify_api_key
from api.db import get_checkpointer
from api.main import app


@pytest.fixture
def mock_checkpointer():
    mock = MagicMock()

    async def async_get_tuple(*args, **kwargs):
        return None

    async def async_put(*args, **kwargs):
        return {"configurable": {"thread_id": "mock"}}

    async def async_setup(*args, **kwargs):
        return None

    mock.aget_tuple = MagicMock(side_effect=async_get_tuple)
    mock.aput = MagicMock(side_effect=async_put)
    mock.asetup = MagicMock(side_effect=async_setup)
    mock.get_tuple = MagicMock(return_value=None)
    mock.put = MagicMock(return_value={"configurable": {"thread_id": "mock"}})
    mock.setup = AsyncMock()
    return mock


@pytest.fixture
def client(mock_checkpointer):
    app.dependency_overrides[get_checkpointer] = lambda: mock_checkpointer
    app.dependency_overrides[verify_api_key] = lambda: "valid_key"

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
