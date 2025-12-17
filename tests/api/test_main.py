import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy as possible"

def test_admin_login_success(client):
    # Patch authenticate_admin to return True
    with patch("api.main.authenticate_admin", return_value=True):
        response = client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "correct_password"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

def test_admin_login_failure(client):
    with patch("api.main.authenticate_admin", return_value=False):
        response = client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "wrong_password"}
        )
        assert response.status_code == 401

def test_chat_endpoint(client):
    # Mock the agent
    mock_agent = MagicMock()
    # Mock ainvoke to be async
    mock_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Bot response")]})
    
    with patch("api.main.make_graph", return_value=mock_agent):
        response = client.post(
            "/chat/test_thread",
            json={"message": "Hello"},
            headers={"X-API-Key": "valid_key"}
        )
        assert response.status_code == 200
        assert response.json()["response"] == "Bot response"
