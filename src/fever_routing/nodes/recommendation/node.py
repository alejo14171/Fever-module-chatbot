"""
Recommendation node — single, brief assessment + follow-up Q&A.

Replaces the previous 4-section state machine. The first time we land here we
emit ONE short pediatrician-style message; subsequent turns are short answers
to the parent's follow-up questions, anchored on the prior assessment.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from fever_routing.nodes.inquiry.prompt import get_age_display
from fever_routing.nodes.recommendation.prompt import (
    calculate_acetaminofen_dose,
    calculate_ibuprofen_dose,
    get_fever_duration_display,
    prompt_template,
    safe_display,
)
from fever_routing.routes.triage.route import detect_red_flags
from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_recommendation_model()


def _extract_user_message(history: list) -> str:
    for msg in reversed(history):
        if msg.__class__.__name__ != "HumanMessage":
            continue
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    return item.get("text", "")
            return str(content)
        return str(content)
    return ""


def _build_context(state: State) -> dict:
    patient_name = safe_display(state.get("patient_name", ""), "el niño/a")
    patient_age_months = safe_display(state.get("patient_age_months", ""), "desconocido")
    patient_weight_kg = safe_display(state.get("patient_weight_kg", ""), "desconocido")

    temperature_raw = safe_display(state.get("temperature", ""), "No medida")
    thermometer_location = safe_display(state.get("thermometer_location", ""), "no especificado")
    fever_duration = safe_display(state.get("fever_duration_hours", ""), "desconocida")

    tactile_assess = state.get("tactile_fever_assessment", "")
    if tactile_assess and temperature_raw == "No medida":
        tactile_map = {"febricula": "37.5-38", "fiebre_moderada": "38-39", "fiebre_alta": "39-40"}
        temperature_raw = f"{tactile_map.get(tactile_assess, '38')} (evaluación táctil)"
        thermometer_location = "evaluación táctil"

    medication_given = safe_display(state.get("medication_given", ""), "ninguno")
    home_measures = safe_display(state.get("home_measures_taken", ""), "ninguna reportada")
    antibiotics = safe_display(state.get("recent_antibiotics", ""), "no")

    medication_info = (
        f"medicamentos: {medication_given}; medidas caseras: {home_measures}; antibióticos recientes: {antibiotics}"
    )

    red_flags = detect_red_flags(state)
    red_flag_descriptions = {
        "menor_3m_fiebre_alta": "lactante <3m con fiebre",
        "3_6m_fiebre_muy_alta": "3-6m con fiebre ≥39°C",
        "fiebre_mayor_40": "fiebre ≥40°C",
        "decaimiento_severo": "decaimiento severo",
        "letargo_posible": "posible letargo",
        "dificultad_respiratoria_severa": "dificultad respiratoria severa",
        "alteracion_coloracion_piel": "alteración de coloración",
        "rash_requiere_evaluacion": "rash que requiere evaluación",
        "convulsiones": "convulsiones",
        "rigidez_nuca": "rigidez de nuca",
        "letargo_extremo": "letargo extremo",
        "rash_no_blanqueable": "rash no blanqueable",
        "signos_neurologicos_criticos": "signos neurológicos críticos",
        "inestabilidad_hemodinamica": "inestabilidad hemodinámica",
        "alteracion_estado_mental_severa": "alteración mental severa",
    }
    red_flags_display = ", ".join(red_flag_descriptions.get(f, f) for f in red_flags) if red_flags else ""

    return {
        "patient_name": patient_name,
        "patient_age_months": patient_age_months,
        "patient_weight_kg": patient_weight_kg,
        "age_display": get_age_display(patient_age_months),
        "parent_phone": safe_display(state.get("parent_phone", ""), "no proporcionado"),
        "temperature": temperature_raw,
        "thermometer_location": thermometer_location,
        "fever_duration": fever_duration,
        "fever_duration_display": get_fever_duration_display(fever_duration),
        "has_thermometer": safe_display(state.get("has_thermometer", ""), "desconocido"),
        "can_get_thermometer": safe_display(state.get("can_get_thermometer", ""), "desconocido"),
        "tactile_fever_assessment": tactile_assess or "",
        "medication_info": medication_info,
        "current_medication_info": {
            "taking_medication": medication_given not in {"no", "ninguno", "ninguno reportado", "desconocido"},
            "medication_name": medication_given,
        },
        "acetaminofen_dose": calculate_acetaminofen_dose(patient_weight_kg, patient_age_months),
        "ibuprofen_dose": calculate_ibuprofen_dose(patient_weight_kg, patient_age_months),
        "general_symptoms_display": safe_display(state.get("general_symptoms", ""), "no evaluado"),
        "respiratory_symptoms_display": safe_display(state.get("respiratory_symptoms", ""), "no evaluado"),
        "visual_alarm_signs_display": safe_display(state.get("visual_alarm_signs", ""), "no evaluado"),
        "other_symptoms": safe_display(state.get("other_symptoms", ""), ""),
        "epidemiological_info": safe_display(state.get("epidemiological_context", ""), "no especificado"),
        "vaccination_status": safe_display(state.get("vaccination_status", ""), "desconocido"),
        "medical_history_display": safe_display(state.get("medical_history", ""), "no especificado"),
        "fever_context": state.get("fever_context") or "primary",
        "red_flags": red_flags,
        "red_flags_display": red_flags_display,
    }


def _generate_assessment(state: State) -> str:
    ctx = _build_context(state)
    formatted = prompt_template.format(**ctx)
    try:
        response = _llm.invoke(
            [
                ("system", formatted),
                ("user", "Genera ahora la recomendación corta para el padre."),
            ]
        )
        return response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Recommendation LLM error: {exc}")
        return (
            "No pude generar la recomendación en este momento. "
            "Te sugiero contactar a tu pediatra para una evaluación presencial."
        )


def _answer_followup(state: State, prior_assessment: str, user_message: str) -> str:
    ctx = _build_context(state)
    aceta = ctx["acetaminofen_dose"]
    ibu = ctx["ibuprofen_dose"]
    aceta_line = (
        f"Acetaminofén: {aceta.get('dose_ml_suspension', 'N/A')} ml jarabe 160mg/5ml cada {aceta.get('interval_hours', 6)}h."
        if not aceta.get("error")
        else aceta.get("warning", "")
    )
    ibu_line = (
        f"Ibuprofeno: {ibu.get('dose_ml_suspension', 'N/A')} ml jarabe 100mg/5ml cada {ibu.get('interval_hours', 8)}h."
        if (not ibu.get("error") and not ibu.get("contraindicated"))
        else (ibu.get("warning") or "")
    )

    system = (
        f"Eres un PEDIATRA colombiano respondiendo una pregunta de seguimiento de la mamá/papá de "
        f"{ctx['patient_name']} ({ctx['age_display']}, {ctx['patient_weight_kg']} kg).\n\n"
        f"Recomendación previa que diste:\n{prior_assessment[:600]}\n\n"
        f"Dosis ya calculadas (úsalas si vienen al caso):\n- {aceta_line}\n- {ibu_line}\n\n"
        f"REGLAS: máximo 3 frases, tono cálido y directo, sin disclaimers ni listas. Si la pregunta no "
        f"tiene relación clínica (agradecimiento, despedida), responde cordialmente con 1-2 frases."
    )
    try:
        response = _llm.invoke([("system", system), ("user", user_message)])
        return response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Recommendation followup error: {exc}")
        return "Tengo problemas para responderte ahora mismo. Si la duda es importante, contacta a tu pediatra."


def recommendation_node(state: State):
    new_state: State = {}
    history = state["messages"]
    current_section = state.get("recommendation_section", "0") or "0"

    if current_section in {"0", ""}:
        message = _generate_assessment(state)
        new_state["messages"] = [AIMessage(content=message)]
        new_state["recommendation_section"] = "done"
        new_state["recommendation_section_1"] = message  # for backward-compat with state schema

        # Cleanup inquiry scratchpad once we move past data-gathering.
        new_state["last_inquiry_question"] = ""
        new_state["expected_fields"] = "[]"
        new_state["fallback_values"] = "{}"

        red_flags = detect_red_flags(state)
        if red_flags:
            new_state["red_flags_detected"] = ", ".join(red_flags)
            new_state["risk_category"] = "alto"
            new_state["recommended_action"] = "consult_24h"
        else:
            new_state["risk_category"] = "bajo"
            new_state["recommended_action"] = "home_care"
        return new_state

    user_message = _extract_user_message(history)
    prior = state.get("recommendation_section_1", "") or ""
    answer = _answer_followup(state, prior, user_message)
    new_state["messages"] = [AIMessage(content=answer)]
    new_state["recommendation_section"] = "done"
    return new_state
