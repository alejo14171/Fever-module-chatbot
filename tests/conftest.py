import os
# Set env var before importing app
os.environ["DB_URI"] = "postgresql://mock:mock@localhost:5432/mock"

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from api.main import app
from api.db import get_checkpointer
from api.auth import verify_api_key

@pytest.fixture
def mock_checkpointer():
    mock = MagicMock()
    
    # Async methods must return awaitables
    async def async_get_tuple(*args, **kwargs):
        return None # No state found
        
    async def async_put(*args, **kwargs):
        return {"configurable": {"thread_id": "mock"}}
        
    async def async_setup(*args, **kwargs):
        return None

    mock.aget_tuple = MagicMock(side_effect=async_get_tuple)
    mock.aput = MagicMock(side_effect=async_put)
    mock.asetup = MagicMock(side_effect=async_setup)
    
    # Sync methods (if used)
    mock.get_tuple = MagicMock(return_value=None)
    mock.put = MagicMock(return_value={"configurable": {"thread_id": "mock"}})
    
    # Fix for test_main.py failing on await _checkpointer.setup()
    # Ensure setup is awaitable if the code awaits it
    mock.setup = AsyncMock() 
    
    return mock

@pytest.fixture
def client(mock_checkpointer):
    # Override dependencies
    app.dependency_overrides[get_checkpointer] = lambda: mock_checkpointer
    app.dependency_overrides[verify_api_key] = lambda: "valid_key"
    
    # Patch PostgresSaver in api.db
    with patch("api.db.PostgresSaver") as mock_pg_class:
        # Mock the context manager
        mock_pg_class.from_conn_string.return_value.__aenter__.return_value = mock_checkpointer
        
        with TestClient(app) as c:
            yield c
    
    # Clean up overrides
    app.dependency_overrides.clear()
