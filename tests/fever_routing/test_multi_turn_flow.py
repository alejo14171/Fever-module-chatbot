"""
Deterministic multi-turn flow tests.

These do NOT call any LLM. They verify pure-Python orchestration:
- questions_asked syncs from State
- receptor only sees recent messages
- inquiry/recommendation cleanup state
- triage routing follows the documented decision tree
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from fever_routing.nodes.inquiry.node import _sync_questions_asked, get_next_question
from fever_routing.routes.triage.route import (
    assess_urgency,
    calculate_checklist_completion,
    detect_red_flags,
    triage_route,
)


def _state(**overrides):
    base = {
        "messages": [],
        "patient_name": "",
        "patient_birthdate": "",
        "patient_age_months": "",
        "patient_weight_kg": "",
        "temperature": "",
        "thermometer_location": "",
        "has_thermometer": "",
        "fever_duration_hours": "",
        "general_symptoms": "",
        "respiratory_symptoms": "",
        "visual_alarm_signs": "",
        "hydration_status": "",
        "feeding_status": "",
        "other_symptoms": "",
        "medication_given": "",
        "medical_history": "",
        "vaccination_status": "",
        "questions_asked": "[]",
        "expected_fields": "[]",
        "fallback_values": "{}",
        "last_inquiry_question": "",
        "fever_context": "",
        "urgency_recommendation_given": "",
        "recommendation_section": "0",
    }
    base.update(overrides)
    return base


def test_sync_questions_asked_marks_filled_fields():
    state = _state(
        patient_age_months="48",
        temperature="38.5",
        medical_history="no",
    )
    asked = _sync_questions_asked(state, [])
    assert "edad" in asked
    assert "temperatura" in asked
    assert "antecedentes" in asked


def test_sync_questions_asked_ignores_unknown_values():
    state = _state(
        patient_age_months="desconocido",
        temperature="0",
        medical_history="",
    )
    asked = _sync_questions_asked(state, [])
    assert asked == []


def test_get_next_question_prioritizes_temperature_for_neonate():
    state = _state(patient_age_months="2")
    question = get_next_question(state, ["temperatura", "edad", "duracion_fiebre"])
    assert "temperatura" in question["field"] or "Temperatura" in question["question"]


def test_get_next_question_handles_trauma_context():
    state = _state(
        patient_age_months="14",
        temperature="38.3",
        fever_duration_hours="1",
        fever_context="trauma",
    )
    question = get_next_question(state, ["antecedentes", "sintomas_generales"])
    assert "TRAUMA" in question["priority"] or "golpe" in question["question"].lower()


def test_assess_urgency_critical_for_seizure():
    state = _state(
        patient_age_months="24",
        temperature="39.0",
        other_symptoms="convulsiones:si",
    )
    urgency = assess_urgency(state)
    assert urgency["level"] == "critical"


def test_assess_urgency_critical_for_petechiae():
    state = _state(
        patient_age_months="36",
        temperature="39.5",
        visual_alarm_signs="rash_no_blanqueable:si",
    )
    urgency = assess_urgency(state)
    assert urgency["level"] == "critical"


def test_assess_urgency_urgent_for_neonate_fever():
    state = _state(
        patient_age_months="2",
        temperature="38.5",
        thermometer_location="axilar",
    )
    urgency = assess_urgency(state)
    assert urgency["level"] == "urgent"


def test_assess_urgency_standard_for_typical_case():
    state = _state(
        patient_age_months="60",
        temperature="38.5",
        thermometer_location="axilar",
    )
    urgency = assess_urgency(state)
    assert urgency["level"] == "standard"


def test_triage_routes_to_urgency_for_critical():
    state = _state(
        patient_age_months="24",
        temperature="39.0",
        other_symptoms="convulsiones:si",
        messages=[HumanMessage(content="convulsionó")],
    )
    assert triage_route(state) == "urgency_recommendation"


def test_triage_routes_to_urgency_for_neonate_fever():
    state = _state(
        patient_age_months="2",
        temperature="38.5",
        thermometer_location="axilar",
        messages=[HumanMessage(content="38.5")],
    )
    assert triage_route(state) == "urgency_recommendation"


def test_triage_returns_to_urgency_when_already_given():
    state = _state(
        patient_age_months="2",
        temperature="38.5",
        thermometer_location="axilar",
        urgency_recommendation_given="yes",
        messages=[HumanMessage(content="ok pero qué llevamos")],
    )
    assert triage_route(state) == "urgency_recommendation"


def test_triage_routes_to_inquiry_when_data_missing():
    state = _state(messages=[HumanMessage(content="hola, mi pelado tiene fiebre")])
    assert triage_route(state) == "inquiry"


def test_extraction_schema_serializes_only_provided_fields():
    from fever_routing.utils.extraction_schema import ExtractionResult

    result = ExtractionResult(
        update=True,
        patient_age_months="48",
        temperature="38.5",
        general_symptoms="juega:si",
    )
    updates = result.to_state_updates()
    assert updates == {
        "patient_age_months": "48",
        "temperature": "38.5",
        "general_symptoms": "juega:si",
    }
    assert "patient_name" not in updates
    assert "update" not in updates


def test_extraction_schema_preserves_no_values():
    from fever_routing.utils.extraction_schema import ExtractionResult

    result = ExtractionResult(update=True, medication_given="no", medical_history="no")
    updates = result.to_state_updates()
    assert updates["medication_given"] == "no"
    assert updates["medical_history"] == "no"


def test_extraction_schema_no_update_returns_empty():
    from fever_routing.utils.extraction_schema import ExtractionResult

    result = ExtractionResult(update=False)
    updates = result.to_state_updates()
    assert updates == {}


def test_detect_red_flags_finds_convulsiones_in_other_symptoms():
    state = _state(
        patient_age_months="36",
        temperature="38.8",
        other_symptoms="convulsion:si",
    )
    flags = detect_red_flags(state)
    assert "convulsiones" in flags


def test_checklist_completion_counts_no_as_complete():
    state = _state(
        patient_age_months="48",
        patient_birthdate="15/01/2021",
        patient_weight_kg="16",
        temperature="38.5",
        fever_duration_hours="20",
        thermometer_location="axilar",
        general_symptoms="juega:si",
        respiratory_symptoms="tos:no",
        hydration_status="bebe_normal:si",
        feeding_status="come_normal:si",
        visual_alarm_signs="palido:no",
        medication_given="no",
        recent_antibiotics="no",
        medical_history="no",
        vaccination_status="completo",
    )
    status = calculate_checklist_completion(state)
    assert status["critical_complete"]
    assert status["important_complete_pct"] >= 0.99
