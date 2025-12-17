import pytest
from unittest.mock import MagicMock, patch
from fever_routing.nodes.urgency_recommendation.node import urgency_recommendation_node
from langchain_core.messages import HumanMessage

def test_urgency_recommendation_node_critical():
    state = {
        "urgency_level": "critical",
        "red_flags_detected": "convulsiones",
        "patient_age_months": "12",
        "temperature": "40",
        "messages": [HumanMessage(content="hola")]
    }
    
    mock_llm_response = MagicMock()
    mock_llm_response.content = "URGENT ADVICE"
    
    with patch("fever_routing.nodes.urgency_recommendation.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_llm_response
        
        result = urgency_recommendation_node(state)
        
        assert "urgency_recommendation_given" in result
        assert result["urgency_recommendation_given"] == "yes"
        assert result["messages"][0].content == "URGENT ADVICE"

def test_urgency_recommendation_node_urgent():
    state = {
        "urgency_level": "urgent",
        "red_flags_detected": "fiebre_muy_alta",
        "patient_age_months": "4",
        "temperature": "39.5",
        "messages": [HumanMessage(content="hola")]
    }
    
    mock_llm_response = MagicMock()
    mock_llm_response.content = "URGENT ADVICE"
    
    with patch("fever_routing.nodes.urgency_recommendation.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_llm_response
        
        result = urgency_recommendation_node(state)
        
        assert "urgency_recommendation_given" in result
        assert result["urgency_recommendation_given"] == "yes"
