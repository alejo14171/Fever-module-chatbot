from fever_routing.routes.triage.route import triage_route
from fever_routing.state import State

def test_triage_urgency_given():
    state = {"urgency_recommendation_given": "yes"}
    assert triage_route(state) == "urgency_recommendation"

def test_triage_recommendation_in_progress():
    state = {"recommendation_section": "1"}
    assert triage_route(state) == "recommendation"

def test_triage_critical_urgency():
    # Age < 3mo + fever > 38
    state = {
        "patient_age_months": "2",
        "temperature": "38.5",
        "urgency_recommendation_given": ""
    }
    assert triage_route(state) == "urgency_recommendation"

def test_triage_checklist_incomplete_missing_critical():
    # Missing temperature
    state = {
        "patient_age_months": "12",
        "urgency_recommendation_given": "",
        "temperature": ""
    }
    assert triage_route(state) == "inquiry"

def test_triage_checklist_complete_enough():
    # All critical fields + some important ones
    state = {
        "patient_age_months": "12",
        "patient_birthdate": "01/01/2023",
        "temperature": "38.5",
        "fever_duration_hours": "24",
        "patient_weight_kg": "10",
        "medical_history": "no",
        "general_symptoms": "vomitos:no",
        "respiratory_symptoms": "tos:no",
        "hydration_status": "bien",
        "visual_alarm_signs": "no",
        "urgency_recommendation_given": "",
        "recommendation_section": "0"
    }
    # This might depend on exact scoring logic, checking logic.
    # The logic requires "important_complete_pct >= 0.99" which is very strict.
    # Let's ensure ALL important fields are set.
    state["hydration_status"] = "normal"
    state["visual_alarm_signs"] = "none"
    state["medical_history"] = "none"
    state["general_symptoms"] = "none"
    state["respiratory_symptoms"] = "none"
    state["thermometer_location"] = "axilar" # nice to have
    
    # We need to make sure calculate_checklist_completion returns ready.
    # The function checks:
    # critical_complete (age, temp, duration)
    # important_complete_pct >= 0.99 (weight, history, gen_symp, resp_symp, hydration, visual)
    
    # Let's verify we have all of them
    assert triage_route(state) == "recommendation"

def test_triage_checklist_incomplete_important():
    # Critical ok, but important missing
    state = {
        "patient_age_months": "12",
        "patient_birthdate": "01/01/2023",
        "temperature": "38.5",
        "fever_duration_hours": "24",
        # Missing weight, etc.
    }
    assert triage_route(state) == "inquiry"

