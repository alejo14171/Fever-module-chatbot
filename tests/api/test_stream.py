import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from langchain_core.messages import AIMessage

def test_stream_endpoint(client):
    # Mock the agent and its stream method
    mock_agent = MagicMock()
    
    # Mock astream to be an async generator
    async def mock_astream(*args, **kwargs):
        yield AIMessage(content="Hello"), {}
        yield AIMessage(content=" world"), {}
        
    mock_agent.astream = mock_astream
    
    # Patch make_graph to return our mock agent
    with patch("api.main.make_graph", return_value=mock_agent):
        response = client.post(
            "/chat/test_thread/stream",
            json={"message": "Hello"},
            headers={"X-API-Key": "valid_key"}
        )
        
        assert response.status_code == 200
        assert "data: Hello" in response.text
        assert "data:  world" in response.text
