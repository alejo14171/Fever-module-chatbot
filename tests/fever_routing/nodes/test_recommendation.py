from unittest.mock import MagicMock, patch
from fever_routing.nodes.recommendation.node import (
    recommendation_node, 
    parse_recommendation_sections, 
    detect_current_medication
)
from langchain_core.messages import HumanMessage

def test_recommendation_node_generates_initial_sections():
    state = {
        "messages": [HumanMessage(content="Gracias")],
        "recommendation_section": "0",
        "patient_name": "Juan",
        "patient_age_months": "24",
        "patient_weight_kg": "12",
        "temperature": "38.5"
    }
    
    mock_response = MagicMock()
    mock_response.content = "Section 1 text\n##########\nSection 2 text\n%%%%%%%%%%\nSection 3 text"
    
    with patch("fever_routing.nodes.recommendation.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = recommendation_node(state)
        
        assert new_state["recommendation_section"] == "1"
        assert new_state["recommendation_section_1"] == "Section 1 text"
        assert len(new_state["messages"]) == 1

def test_recommendation_node_advances_section():
    state = {
        "messages": [HumanMessage(content="Ok, continúa")],
        "recommendation_section": "1",
        "recommendation_section_1": "S1",
        "recommendation_section_2": "S2",
        "recommendation_section_3": "S3"
    }
    
    mock_response = MagicMock()
    mock_response.content = '{"action": "continue", "response": ""}'
    
    with patch("fever_routing.nodes.recommendation.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = recommendation_node(state)
        assert new_state["recommendation_section"] == "2"

def test_recommendation_node_answers_question():
    state = {
        "messages": [HumanMessage(content="¿Qué dosis?")],
        "recommendation_section": "1",
        "recommendation_section_1": "S1",
        "recommendation_section_2": "S2",
        "recommendation_section_3": "S3"
    }
    
    mock_response = MagicMock()
    mock_response.content = '{"action": "answer_question", "response": "5ml"}'
    
    with patch("fever_routing.nodes.recommendation.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = recommendation_node(state)
        assert len(new_state["messages"]) == 1
        assert "5ml" in new_state["messages"][0].content
        # Section should NOT advance
        # Note: implementation detail, it might return empty dict update for section if it doesn't change?
        # Or it might not return "recommendation_section" key?
        # Looking at code: it doesn't change it.
        assert "recommendation_section" not in new_state

def test_parse_recommendation_sections():
    text = "S1\n##########\nS2\n%%%%%%%%%%\nS3"
    sections = parse_recommendation_sections(text)
    assert sections["section_1"] == "S1"
    assert sections["section_2"] == "S2"
    assert sections["section_3"] == "S3"

def test_detect_current_medication():
    assert detect_current_medication("Paracetamol")["taking_medication"] is True
    assert detect_current_medication("no")["taking_medication"] is False
