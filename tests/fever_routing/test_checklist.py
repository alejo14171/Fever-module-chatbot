from fever_routing.routes.triage.route import calculate_checklist_completion

def test_checklist_completion_empty():
    state = {}
    result = calculate_checklist_completion(state)
    assert result["score"] == 0.0
    assert result["ready_for_recommendation"] is False

def test_checklist_completion_critical_only():
    state = {
        "patient_birthdate": "01/01/2023",
        "temperature": "38.5",
        "fever_duration_hours": "24"
    }
    result = calculate_checklist_completion(state)
    # Critical weight 50%
    assert result["score"] == 0.5
    assert result["ready_for_recommendation"] is False

def test_checklist_completion_full():
    state = {
        # Critical
        "patient_birthdate": "01/01/2023",
        "temperature": "38.5",
        "fever_duration_hours": "24",
        # Important
        "patient_weight_kg": "10",
        "medical_history": "no",
        "general_symptoms": "ok",
        "respiratory_symptoms": "no",
        "hydration_status": "ok",
        "visual_alarm_signs": "no",
        # Optional
        "thermometer_location": "axilar",
        "medication_given": "no",
        "feeding_status": "ok",
        "vaccination_status": "ok"
    }
    result = calculate_checklist_completion(state)
    assert result["score"] == 1.0
    assert result["ready_for_recommendation"] is True

def test_checklist_completion_no_values():
    # "no" is valid
    state = {
        "medication_given": "no",
        "recent_antibiotics": "no",
        "home_measures_taken": "no"
    }
    result = calculate_checklist_completion(state)
    # Optional fields covered?
    # medication_given is optional.
    # Should contribute slightly to score.
    assert result["score"] > 0

def test_checklist_tactile_temperature():
    state = {
        "tactile_fever_assessment": "febricula",
        "temperature": "no_medida" # or empty
    }
    # Should count as temperature data
    # We need to spy on internal helper logic? No, just check result.
    # Critical fields: edad, temperatura, duracion.
    # If we only have temp (tactile), score should reflect 1/3 of critical (approx 16%)
    result = calculate_checklist_completion(state)
    # 1 critical field (temp) out of 3 = 33% of critical weight (50%) = 16.5%
    assert result["score"] > 0.15

