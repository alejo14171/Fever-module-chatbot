import pytest
from fever_routing.nodes.urgency_recommendation.prompt import (
    get_age_display,
    get_fever_duration_display,
    safe_display
)

def test_get_age_display():
    assert get_age_display("6") == "6 meses"
    assert get_age_display("12") == "1 año"
    assert get_age_display("18") == "1 años 6 meses"
    assert get_age_display("24") == "2 años"
    assert get_age_display("desconocido") == "desconocido"
    assert get_age_display("") == "desconocido"

def test_get_fever_duration_display():
    assert get_fever_duration_display("0.5") == "menos de 1 hora"
    assert get_fever_duration_display("12") == "12 horas"
    assert get_fever_duration_display("24") == "24 horas (1 día)" # < 48 is 1 day? Logic says <48 is 1 day but 24 is 1 day.
    assert get_fever_duration_display("36") == "36 horas (1 día)"
    assert get_fever_duration_display("48") == "48 horas (2 días)" # < 72 is 2 days. 48 is not < 48.
    assert get_fever_duration_display("72") == "72 horas (3 días)"
    assert get_fever_duration_display("invalid") == "desconocida"

def test_safe_display():
    assert safe_display("valor") == "valor"
    assert safe_display("") == "No especificado"
    assert safe_display("  ") == "No especificado"
    assert safe_display(None) == "No especificado"
    assert safe_display("", "Default") == "Default"

