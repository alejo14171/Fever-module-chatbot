from unittest.mock import MagicMock, patch
from fever_routing.nodes.receptor.node import receptor_node, calculate_age_in_months, calculate_duration_from_datetime
from langchain_core.messages import HumanMessage
import datetime

def test_receptor_node_extracts_data():
    state = {
        "messages": [HumanMessage(content="Mi hijo Juan de 2 años tiene 38.5 de fiebre")],
        "expected_fields": "[]",
        "fallback_values": "{}"
    }
    
    mock_response = MagicMock()
    mock_response.content = "patient_name: Juan\npatient_age_months: 24\ntemperature: 38.5"
    
    with patch("fever_routing.nodes.receptor.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = receptor_node(state)
        
        assert new_state["patient_name"] == "Juan"
        assert new_state["patient_age_months"] == "24" 
        assert new_state["temperature"] == "38.5"

def test_receptor_node_calculates_age_from_birthdate():
    state = {
        "messages": [HumanMessage(content="Nació el 01/01/2023")],
    }
    
    mock_response = MagicMock()
    mock_response.content = "patient_birthdate: 01/01/2023"
    
    with patch("fever_routing.nodes.receptor.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = receptor_node(state)
        
        assert "patient_birthdate" in new_state
        assert "patient_age_months" in new_state

def test_receptor_node_validates_expected_fields():
    state = {
        "messages": [HumanMessage(content="No sé")],
        "expected_fields": '["temperature"]',
        "fallback_values": '{"temperature": "desconocido"}'
    }
    
    mock_response = MagicMock()
    mock_response.content = "" # Nothing extracted
    
    with patch("fever_routing.nodes.receptor.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = receptor_node(state)
        
        assert new_state["temperature"] == "desconocido"

def test_calculate_age_in_months():
    # Assuming current date is somewhat recent, or we mock datetime
    # But let's test invalid formats
    assert calculate_age_in_months("invalid") == ""
    assert calculate_age_in_months("unknown") == ""

def test_calculate_duration_from_datetime():
    # We need to mock datetime.now() ideally
    # But checking invalid inputs
    assert calculate_duration_from_datetime("invalid") == ""
