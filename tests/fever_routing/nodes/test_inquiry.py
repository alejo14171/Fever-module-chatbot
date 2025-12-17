from unittest.mock import MagicMock, patch
from fever_routing.nodes.inquiry.node import inquiry_node, get_next_question, check_needs_no_fever_clarification
from langchain_core.messages import HumanMessage, AIMessage
import json

def test_inquiry_node_generates_question():
    # State with minimal info, missing mostly everything
    state = {
        "messages": [HumanMessage(content="Hola")],
        "patient_name": "Juan",
        "questions_asked": "[]",
        "temperature": "desconocido",
        "patient_age_months": "desconocido"
    }
    
    mock_response = MagicMock()
    mock_response.content = "¿Cuál es la edad de Juan?"
    
    with patch("fever_routing.nodes.inquiry.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = inquiry_node(state)
        
        assert len(new_state["messages"]) == 1
        assert new_state["messages"][0].content == "¿Cuál es la edad de Juan?"
        
        # Verify context update
        assert "last_inquiry_question" in new_state
        assert "expected_fields" in new_state
        
        # Verify question tracking
        questions_asked = json.loads(new_state["questions_asked"])
        assert len(questions_asked) > 0

def test_inquiry_node_detects_urgency_priority():
    # Age < 3 months, missing temperature -> Should prioritize temperature
    state = {
        "messages": [HumanMessage(content="Tiene 2 meses")],
        "patient_name": "Juan",
        "patient_age_months": "2", # < 3 months
        "temperature": "desconocido", # Missing
        "questions_asked": "[]"
    }
    
    mock_response = MagicMock()
    mock_response.content = "Pregunta sobre temperatura rectal"
    
    with patch("fever_routing.nodes.inquiry.node.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response
        
        new_state = inquiry_node(state)
        
        expected = json.loads(new_state["expected_fields"])
        # Expecting temperature fields to be required
        assert "temperature" in expected or "has_thermometer" in expected

def test_get_next_question_medical_history_priority():
    state = {"patient_name": "Juan"}
    missing = ["antecedentes", "temperatura", "edad"]
    
    q = get_next_question(state, missing)
    assert q["field"] == "antecedentes"
    assert "condición médica" in q["question"]

def test_get_next_question_temperature_priority():
    state = {"patient_name": "Juan"}
    missing = ["temperatura", "edad"]
    
    q = get_next_question(state, missing)
    assert q["field"] == "temperatura"

def test_get_next_question_symptom_cluster():
    state = {"patient_name": "Juan"}
    missing = ["sintomas_generales", "hidratacion", "alimentacion"]
    
    q = get_next_question(state, missing)
    assert q["field"] == "sintomas_generales"
    assert "jugando" in q["question"] or "decaído" in q["question"]

def test_check_needs_no_fever_clarification():
    # Case: Temp recently asked, < 38, user said "fiebre"
    state = {"temperature": "37.5"}
    messages = [HumanMessage(content="Tiene fiebre")]
    questions_asked = ["temperatura"]
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is True
    assert "NO es fiebre" in result["clarification_text"]

def test_no_fever_clarification_already_given():
    # Case: Already given
    state = {"temperature": "37.5"}
    messages = [
        HumanMessage(content="Tiene fiebre"),
        AIMessage(content="37.5 NO es fiebre")
    ]
    questions_asked = ["temperatura"]
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is False
