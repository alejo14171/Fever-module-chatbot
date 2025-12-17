from fever_routing.routes.triage.route import detect_red_flags

def test_red_flags_age_lt_3_months():
    state = {
        "patient_age_months": "2",
        "temperature": "38.5",
        "thermometer_location": "rectal"
    }
    flags = detect_red_flags(state)
    assert "menor_3m_fiebre_alta" in flags

def test_red_flags_convulsions():
    state = {
        "general_symptoms": "convulsiones:si"
    }
    flags = detect_red_flags(state)
    assert "convulsiones" in flags

def test_red_flags_respiratory():
    state = {
        "respiratory_symptoms": "dificultad_respirar:severo"
    }
    flags = detect_red_flags(state)
    assert "dificultad_respiratoria_severa" in flags

def test_red_flags_visual():
    state = {
        "visual_alarm_signs": "cianosis:si"
    }
    flags = detect_red_flags(state)
    assert "signos_respiratorios_criticos" in flags # cianosis maps to this

def test_red_flags_multiple():
    state = {
        "patient_age_months": "4",
        "temperature": "40.5",
        "general_symptoms": "decaido:severo"
    }
    flags = detect_red_flags(state)
    assert "fiebre_mayor_40" in flags
    assert "decaimiento_severo" in flags

