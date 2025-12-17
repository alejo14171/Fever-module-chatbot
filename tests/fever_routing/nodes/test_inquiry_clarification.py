import pytest
from unittest.mock import MagicMock, patch
from fever_routing.nodes.inquiry.node import check_needs_no_fever_clarification
from langchain_core.messages import HumanMessage, AIMessage

def test_check_needs_no_fever_clarification_no_temp():
    state = {"temperature": ""}
    messages = []
    questions_asked = []
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is False

def test_check_needs_no_fever_clarification_high_temp():
    state = {"temperature": "39.5"}
    messages = []
    questions_asked = []
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is False

def test_check_needs_no_fever_clarification_temp_not_recent():
    state = {"temperature": "37.5"}
    messages = []
    questions_asked = [] # "temperatura" not in list
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is False

def test_check_needs_no_fever_clarification_fever_not_mentioned():
    state = {"temperature": "37.5"}
    messages = [HumanMessage(content="Hola")] # No "fiebre" keyword
    questions_asked = ["temperatura"]
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is False

def test_check_needs_no_fever_clarification_febricula_category():
    state = {"temperature": "37.8"}
    messages = [HumanMessage(content="Tiene fiebre")]
    questions_asked = ["temperatura"]
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is True
    assert "febrícula" in result["clarification_text"]

def test_check_needs_no_fever_clarification_normal_category():
    state = {"temperature": "36.8"}
    messages = [HumanMessage(content="Tiene fiebre")]
    questions_asked = ["temperatura"]
    
    result = check_needs_no_fever_clarification(state, messages, questions_asked)
    assert result["needs_clarification"] is True
    assert "temperatura normal" in result["clarification_text"]

