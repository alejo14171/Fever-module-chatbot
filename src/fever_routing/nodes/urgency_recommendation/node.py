"""
Urgency recommendation node — short urgent message, then short follow-up answers.
"""

from __future__ import annotations

from datetime import date

from langchain_core.messages import AIMessage

from fever_routing.nodes.urgency_recommendation.prompt import (
    get_age_display,
    get_fever_duration_display,
    prompt_template,
    safe_display,
)
from fever_routing.routes.triage.route import detect_red_flags
from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_urgency_recommendation_model()


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


def urgency_recommendation_node(state: State):
    new_state: State = {}
    history = state["messages"]
    urgency_given = state.get("urgency_recommendation_given", "") or ""

    patient_name = safe_display(state.get("patient_name", ""), "el bebé")
    patient_age_months = safe_display(state.get("patient_age_months", ""), "desconocido")
    patient_weight_kg = safe_display(state.get("patient_weight_kg", ""), "desconocido")
    temperature = safe_display(state.get("temperature", ""), "no medida")
    fever_duration = safe_display(state.get("fever_duration_hours", ""), "desconocida")

    general_symptoms = safe_display(state.get("general_symptoms", ""), "no evaluado")
    respiratory_symptoms = safe_display(state.get("respiratory_symptoms", ""), "no evaluado")
    other_symptoms = safe_display(state.get("other_symptoms", ""), "ninguno")

    age_display = get_age_display(patient_age_months)
    fever_duration_display = get_fever_duration_display(fever_duration)

    if urgency_given != "yes":
        formatted = prompt_template.format(
            today=date.today().strftime("%Y-%m-%d"),
            patient_name=patient_name,
            patient_age_months=patient_age_months,
            age_display=age_display,
            patient_weight_kg=patient_weight_kg,
            temperature=temperature,
            fever_duration_display=fever_duration_display,
            general_symptoms_display=general_symptoms,
            respiratory_symptoms_display=respiratory_symptoms,
            other_symptoms=other_symptoms,
        )
        try:
            response = _llm.invoke(
                [("system", formatted), ("user", "Genera el mensaje urgente ahora.")]
            )
            urgent_message = response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            debug_print(f"❌ Urgency LLM error: {exc}")
            urgent_message = (
                f"Tienen que llevar a {patient_name} ya mismo a urgencias pediátricas "
                f"por la fiebre y los síntomas que mencionas. Pueden ir en carro si están tranquilos. "
                f"Lleven carnet de vacunas y la hora en que empezó la fiebre. ¿Tienes alguna duda antes de salir?"
            )

        new_state["messages"] = [AIMessage(content=urgent_message)]
        new_state["urgency_recommendation_given"] = "yes"
        new_state["urgency_criteria_met"] = "yes"
        new_state["risk_category"] = "critico"
        new_state["recommended_action"] = "urgent_ed"
        live_red_flags = detect_red_flags(state)
        if live_red_flags:
            new_state["red_flags_detected"] = ", ".join(live_red_flags)
        elif state.get("red_flags_detected"):
            new_state["red_flags_detected"] = state["red_flags_detected"]
        new_state["last_inquiry_question"] = ""
        new_state["expected_fields"] = "[]"
        new_state["fallback_values"] = "{}"
        return new_state

    user_message = _extract_user_message(history)
    system = (
        f"Eres un PEDIATRA colombiano. Ya le dijiste a la mamá/papá de {patient_name} "
        f"({age_display}) que vayan AHORA a urgencias pediátricas. "
        f"Responde su pregunta o comentario en MÁXIMO 2 frases, tono firme y calmado. "
        f"No dejes lugar a dudas sobre la necesidad de ir. No recetes medicamentos. "
        f"No uses listas ni disclaimers."
    )
    try:
        response = _llm.invoke([("system", system), ("user", user_message)])
        followup = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Urgency followup error: {exc}")
        followup = "Estás haciendo lo correcto. Vayan ya a urgencias y allá los acompañarán."

    new_state["messages"] = [AIMessage(content=followup)]
    return new_state
