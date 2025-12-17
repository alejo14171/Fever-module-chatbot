import pytest
from unittest.mock import MagicMock, patch
from api.feedback import (
    create_feedback_table,
    insert_feedback,
    get_all_feedback,
    get_feedback_stats,
    FeedbackSubmission
)

@pytest.fixture
def mock_conn():
    with patch("api.feedback.get_db_connection") as mock:
        conn = MagicMock()
        mock.return_value = conn
        yield conn

def test_create_feedback_table(mock_conn):
    create_feedback_table()
    mock_conn.cursor.return_value.__enter__.return_value.execute.assert_called()
    mock_conn.commit.assert_called()

def test_insert_feedback(mock_conn):
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchone.return_value = [1]
    
    feedback = FeedbackSubmission(
        firstName="Test",
        lastName="User",
        clarity="Sí",
        helpfulness="Sí",
        medicalGuidance="Sí",
        tone="Sí",
        confusion="No",
        recommendation="Definitivamente sí",
        sessionId="123"
    )
    
    id = insert_feedback(feedback)
    assert id == 1
    mock_conn.commit.assert_called()

def test_get_all_feedback(mock_conn):
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "first_name": "Test", 
            "timestamp": MagicMock(isoformat=lambda: "2023-01-01")
        }
    ]
    
    results = get_all_feedback()
    assert len(results) == 1
    assert results[0]["id"] == 1

def test_get_feedback_stats(mock_conn):
    mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
    # Mocking sequential calls for counts
    # First call: total count
    # Subsequent calls: field counts
    
    # We can use side_effect for fetchone/fetchall
    mock_cursor.fetchone.side_effect = [{'total': 10}]
    mock_cursor.fetchall.side_effect = [
        [{'clarity': 'Sí', 'count': 5}, {'clarity': 'No', 'count': 5}], # clarity
        [{'helpfulness': 'Sí', 'count': 8}], # helpfulness
        [], # medicalGuidance
        [], # tone
        [], # confusion
        []  # recommendation
    ]
    
    stats = get_feedback_stats()
    assert stats["total"] == 10
    # Field names are camelCase in response
    assert stats["clarity"]["Sí"] == 5
    assert stats["helpfulness"]["Sí"] == 8
