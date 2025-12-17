import pytest
from fever_routing.routes.triage.route import detect_red_flags

def test_red_flags_age_3_6_months_high_fever():
    state = {
        "patient_age_months": "4",
        "temperature": "39.5"
    }
    flags = detect_red_flags(state)
    assert "3_6m_fiebre_muy_alta" in flags

def test_red_flags_general_state():
    state = {
        "general_symptoms": "decaido:si"
    }
    flags = detect_red_flags(state)
    assert "decaimiento_severo" in flags

    state = {
        "general_symptoms": "juega:no, decaido:si"
    }
    flags = detect_red_flags(state)
    assert "letargo_posible" in flags

def test_red_flags_mental_status():
    state = {
        "general_symptoms": "confuso:si"
    }
    flags = detect_red_flags(state)
    assert "alteracion_estado_mental_severa" in flags

def test_red_flags_respiratory_critical():
    state = {
        "respiratory_symptoms": "quejido:si"
    }
    flags = detect_red_flags(state)
    assert "signos_respiratorios_criticos" in flags

def test_red_flags_skin():
    state = {
        "visual_alarm_signs": "mal_color:si"
    }
    flags = detect_red_flags(state)
    assert "alteracion_coloracion_piel" in flags
    
    state = {
        "visual_alarm_signs": "erupciones:si"
    }
    flags = detect_red_flags(state)
    assert "rash_requiere_evaluacion" in flags

    state = {
        "visual_alarm_signs": "petequias:si"
    }
    flags = detect_red_flags(state)
    assert "rash_no_blanqueable" in flags

def test_red_flags_hemodynamic():
    state = {
        "visual_alarm_signs": "piel_moteada:si"
    }
    flags = detect_red_flags(state)
    assert "inestabilidad_hemodinamica" in flags

def test_red_flags_neurological():
    state = {
        "other_symptoms": "rigidez_nuca:si"
    }
    flags = detect_red_flags(state)
    assert "signos_neurologicos_criticos" in flags

def test_red_flags_organ_dysfunction():
    state = {
        "other_symptoms": "no_orina:si"
    }
    flags = detect_red_flags(state)
    assert "disfuncion_organica" in flags

