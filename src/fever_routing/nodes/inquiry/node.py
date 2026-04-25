"""
Inquiry node — chooses the next question deterministically (Python) and asks
the LLM only to reformulate it warmly and briefly.

Python decides WHAT to ask. The LLM only reshapes the phrasing.
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage

from fever_routing.nodes.inquiry.adaptive import pick_next_question_adaptive
from fever_routing.nodes.inquiry.prompt import (
    format_missing_items,
    get_age_display,
    prompt_template,
)
from fever_routing.routes.triage.route import (
    calculate_checklist_completion,
    detect_red_flags,
)
from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()


# Map checklist field names → state field names. Used to sync `questions_asked`
# with the current State so that we never re-ask something we already have.
CHECKLIST_TO_STATE = {
    "edad": "patient_age_months",
    "peso": "patient_weight_kg",
    "temperatura": "temperature",
    "duracion_fiebre": "fever_duration_hours",
    "lugar_termometro": "thermometer_location",
    "medicacion_previa": "medication_given",
    "sintomas_generales": "general_symptoms",
    "sintomas_respiratorios": "respiratory_symptoms",
    "hidratacion": "hydration_status",
    "alimentacion": "feeding_status",
    "signos_alarma_visual": "visual_alarm_signs",
    "estado_vacunal": "vaccination_status",
    "antecedentes": "medical_history",
}


def _sync_questions_asked(state: State, questions_asked: list[str]) -> list[str]:
    """Mark as 'asked' anything that already has a real value in State."""
    seen = set(questions_asked)
    for checklist_field, state_field in CHECKLIST_TO_STATE.items():
        value = state.get(state_field, "")
        if value and value not in {"desconocido", "0"}:
            seen.add(checklist_field)
    return sorted(seen)


def get_next_question(state: State, missing: list[str]) -> dict:
    """Pick the next clinical question. Returns dict with question + metadata."""
    patient_name = state.get("patient_name") or "su hijo/a"
    if patient_name == "desconocido":
        patient_name = "su hijo/a"

    fever_context = state.get("fever_context", "") or ""

    age_str = state.get("patient_age_months") or ""
    temp_str = state.get("temperature") or ""
    try:
        age_val = int(age_str) if age_str and age_str != "desconocido" else -1
    except (ValueError, TypeError):
        age_val = -1
    try:
        temp_val = float(temp_str) if temp_str and temp_str != "desconocido" else -1.0
    except (ValueError, TypeError):
        temp_val = -1.0

    # Context-specific questions ONLY trigger once fever is confirmed (temp > 0
    # or tactile assessment present). Otherwise we don't make assumptions about
    # the cause yet.
    fever_confirmed = (
        temp_val > 0
        or bool(state.get("tactile_fever_assessment"))
    )

    questions_asked_now = []
    try:
        questions_asked_now = json.loads(state.get("questions_asked", "[]") or "[]")
    except json.JSONDecodeError:
        questions_asked_now = []

    if (
        fever_context == "trauma"
        and fever_confirmed
        and "trauma_neuro" not in questions_asked_now
    ):
        return {
            "question": (
                f"Como hubo un golpe antes de la fiebre, dime: "
                f"¿{patient_name} estuvo somnoliento, vomitó, perdió la consciencia o se le ven las pupilas raras?"
            ),
            "priority": "🔴 TRAUMA",
            "field": "trauma_neuro",
            "required_fields": ["other_symptoms"],
            "fallback_value": {},
            "extraction_hint": "Buscar signos neurológicos post-trauma en other_symptoms.",
        }

    if fever_context == "base_disease" and "antecedentes" in missing:
        return {
            "question": (
                f"Cuéntame qué condición de base tiene {patient_name} y si está en algún tratamiento activo."
            ),
            "priority": "🔴 ENFERMEDAD BASE",
            "field": "antecedentes",
            "required_fields": ["medical_history"],
            "fallback_value": {},
            "extraction_hint": "Extraer la condición de base y tratamiento en medical_history.",
        }

    # Sub-3-month infants with missing temperature: prioritize temp.
    if 0 <= age_val < 3 and "temperatura" in missing:
        return {
            "question": (
                f"Como {patient_name} es menor de 3 meses, necesito saber la temperatura exacta. "
                f"¿La pudiste medir? Si sí, ¿cuánto y dónde?"
            ),
            "priority": "🚨 URGENTE - Temperatura (lactante <3m)",
            "field": "temperatura",
            "required_fields": ["has_thermometer", "temperature", "thermometer_location"],
            "fallback_value": {
                "has_thermometer": "no",
                "temperature": "desconocido",
                "thermometer_location": "desconocido",
            },
            "extraction_hint": "has_thermometer si/no; temperature en °C; location axilar/rectal/oral/frontal/oido.",
        }

    if temp_val > 38.0 and "edad" in missing:
        return {
            "question": (
                f"Con esa fiebre necesito la edad exacta para orientarte bien. "
                f"¿Cuántos meses tiene {patient_name} o cuándo nació?"
            ),
            "priority": "🚨 URGENTE - Edad (fiebre >38°C)",
            "field": "edad",
            "required_fields": ["patient_birthdate", "patient_age_months"],
            "fallback_value": {},
            "extraction_hint": "Extraer patient_birthdate o patient_age_months.",
        }

    # No-thermometer flow: tactile assessment.
    if (
        "temperatura" in missing
        and state.get("has_thermometer") == "no"
        and state.get("tactile_assessment_given") != "si"
    ):
        return {
            "question": (
                f"Sin termómetro podemos evaluar al tacto: pon el dorso de tu mano en la frente y pecho de "
                f"{patient_name}. ¿Lo sientes tibio, muy caliente o ardiendo?"
            ),
            "priority": "🟡 EVAL TÁCTIL",
            "field": "tactile_assessment_given",
            "required_fields": ["tactile_assessment_given", "tactile_fever_assessment"],
            "fallback_value": {
                "tactile_assessment_given": "si",
                "tactile_fever_assessment": "fiebre_moderada",
            },
            "extraction_hint": "tactile_fever_assessment: febricula/fiebre_moderada/fiebre_alta",
        }

    # Standard ordered checklist.
    # Reordered (Apr 2026): temperatura primero — un chatbot de fiebre necesita
    # confirmar la fiebre antes de cualquier otra cosa. Si no hay fiebre, el
    # caso no es nuestro y el bot puede orientar/derivar.
    if "temperatura" in missing:
        if 0 < age_val < 3:
            return {
                "question": (
                    f"Para bebés menores de 3 meses la temperatura rectal es la más confiable. "
                    f"¿Pudiste medírsela?"
                ),
                "priority": "🔴 Temperatura RECTAL <3m",
                "field": "temperatura",
                "required_fields": ["has_thermometer", "temperature", "thermometer_location"],
                "fallback_value": {
                    "has_thermometer": "no",
                    "temperature": "desconocido",
                    "thermometer_location": "desconocido",
                },
                "extraction_hint": "Extraer has_thermometer, temperature, thermometer_location.",
            }
        return {
            "question": f"¿Pudiste medir la temperatura? Si sí, ¿cuánto y dónde la mediste (axila, frente, oído)?",
            "priority": "🔴 Temperatura",
            "field": "temperatura",
            "required_fields": ["has_thermometer", "temperature", "thermometer_location"],
            "fallback_value": {
                "has_thermometer": "no",
                "temperature": "desconocido",
                "thermometer_location": "desconocido",
            },
            "extraction_hint": "Extraer has_thermometer, temperature, thermometer_location.",
        }

    if "edad" in missing:
        return {
            "question": f"¿Cuántos meses tiene {patient_name} o cuándo nació?",
            "priority": "🔴 Edad",
            "field": "edad",
            "required_fields": ["patient_birthdate", "patient_age_months"],
            "fallback_value": {},
            "extraction_hint": "Extraer patient_birthdate o patient_age_months.",
        }

    if "antecedentes" in missing:
        return {
            "question": f"¿{patient_name} tiene alguna condición de base, alergia o enfermedad importante?",
            "priority": "🔴 Antecedentes",
            "field": "antecedentes",
            "required_fields": ["medical_history"],
            "fallback_value": {"medical_history": "no"},
            "extraction_hint": "Si dice 'no'/'ninguno'/'sano' → medical_history: no.",
        }

    if "peso" in missing:
        return {
            "question": "¿Cuánto pesa más o menos? Si no sabes exacto, dime el peso del último control.",
            "priority": "🔴 Peso",
            "field": "peso",
            "required_fields": ["patient_weight_kg"],
            "fallback_value": {},
            "extraction_hint": "patient_weight_kg numérico (ej '12', '15.5').",
        }

    if "duracion_fiebre" in missing:
        return {
            "question": "¿Hace cuánto le empezó la fiebre? Puedes decirme un día y hora aproximada.",
            "priority": "🔴 Duración",
            "field": "duracion_fiebre",
            "required_fields": ["fever_duration_hours"],
            "fallback_value": {},
            "extraction_hint": "fever_start_datetime si dan fecha/hora; o fever_duration_hours si dan duración directa.",
        }

    if "lugar_termometro" in missing and state.get("temperature") not in {"desconocido", "", None}:
        return {
            "question": "¿Dónde le mediste la temperatura: axila, frente, oído o rectal?",
            "priority": "🟡 Lugar termómetro",
            "field": "lugar_termometro",
            "required_fields": ["thermometer_location"],
            "fallback_value": {"thermometer_location": "axilar"},
            "extraction_hint": "thermometer_location: axilar/rectal/oral/frontal/oido.",
        }

    if "sintomas_generales" in missing:
        return {
            "question": f"¿Cómo lo/la ves: jugando como siempre o más decaído/a? ¿Está comiendo y tomando líquidos normal?",
            "priority": "🟡 Estado general + hidratación",
            "field": "sintomas_generales",
            "required_fields": ["general_symptoms", "hydration_status", "feeding_status"],
            "fallback_value": {
                "general_symptoms": "juega:si, decaido:no",
                "hydration_status": "bebe_normal:si, orina_normal:si",
                "feeding_status": "come_normal:si, rechaza_alimento:no, vomita:no",
            },
            "extraction_hint": "Extraer general_symptoms, hydration_status, feeding_status.",
        }

    if "sintomas_respiratorios" in missing:
        return {
            "question": "¿Tiene tos, mocos o se le dificulta respirar? ¿Algún cambio de color en la piel?",
            "priority": "🟡 Respiratorio + visual",
            "field": "sintomas_respiratorios",
            "required_fields": ["respiratory_symptoms", "visual_alarm_signs"],
            "fallback_value": {
                "respiratory_symptoms": "dificultad_respirar:no, tos:no",
                "visual_alarm_signs": "palido:no, cianosis:no, rash:no",
            },
            "extraction_hint": "Extraer respiratory_symptoms y visual_alarm_signs.",
        }

    if "hidratacion" in missing:
        return {
            "question": f"¿{patient_name} está tomando líquidos y orinando como siempre?",
            "priority": "🟡 Hidratación",
            "field": "hidratacion",
            "required_fields": ["hydration_status"],
            "fallback_value": {"hydration_status": "bebe_normal:si, orina_normal:si"},
            "extraction_hint": "Extraer hydration_status.",
        }

    if "alimentacion" in missing:
        return {
            "question": f"¿{patient_name} está comiendo o ha vomitado?",
            "priority": "🟡 Alimentación",
            "field": "alimentacion",
            "required_fields": ["feeding_status"],
            "fallback_value": {"feeding_status": "come_normal:si, vomita:no"},
            "extraction_hint": "Extraer feeding_status.",
        }

    if "signos_alarma_visual" in missing:
        return {
            "question": f"¿Le has notado la piel pálida, azulada, manchas o brote nuevo?",
            "priority": "🟡 Signos visuales",
            "field": "signos_alarma_visual",
            "required_fields": ["visual_alarm_signs"],
            "fallback_value": {"visual_alarm_signs": "palido:no, cianosis:no, rash:no"},
            "extraction_hint": "Extraer visual_alarm_signs.",
        }

    if "medicacion_previa" in missing:
        return {
            "question": "¿Le has dado algún medicamento para la fiebre? ¿Cuál y hace cuánto?",
            "priority": "🟢 Medicación",
            "field": "medicacion_previa",
            "required_fields": ["medication_given"],
            "fallback_value": {"medication_given": "no"},
            "extraction_hint": "medication_given (con dosis y tiempo) o 'no'.",
        }

    if "estado_vacunal" in missing:
        return {
            "question": "¿Tiene las vacunas al día?",
            "priority": "🟢 Vacunación",
            "field": "estado_vacunal",
            "required_fields": ["vaccination_status"],
            "fallback_value": {"vaccination_status": "desconocido"},
            "extraction_hint": "vaccination_status: completo/incompleto/desconocido.",
        }

    return {
        "question": "¿Hay algún otro síntoma o detalle que quieras contarme?",
        "priority": "ℹ️ Adicional",
        "field": "other",
        "required_fields": ["other_symptoms"],
        "fallback_value": {},
        "extraction_hint": "Extraer cualquier información adicional.",
    }


def inquiry_node(state: State):
    """Pick next question, ask LLM to phrase it briefly, return updated state."""
    new_state: State = {}
    history = state["messages"]
    last_message = history[-1] if history else None

    checklist_status = calculate_checklist_completion(state)
    red_flags = detect_red_flags(state)

    try:
        questions_asked = json.loads(state.get("questions_asked", "[]") or "[]")
    except json.JSONDecodeError:
        questions_asked = []

    questions_asked = _sync_questions_asked(state, questions_asked)

    remaining_missing = [
        field for field in checklist_status["missing"] if field not in questions_asked
    ]

    # If we already asked everything but the parent didn't fill some fields,
    # don't loop — flag for recommendation with partial data and emit a
    # transitional message inviting them to share anything else.
    if not remaining_missing and checklist_status["missing"]:
        debug_print("⚠️ inquiry: all checklist items already asked but data still thin → partial-data path")
        new_state["recommendation_with_partial_data"] = "yes"
        new_state["last_inquiry_question"] = ""
        new_state["expected_fields"] = "[]"
        new_state["fallback_values"] = "{}"
        new_state["messages"] = [
            AIMessage(
                content=(
                    "Listo, con la información que me has dado puedo orientarte. "
                    "¿Hay algún síntoma o detalle que no te haya preguntado y quieras contarme antes de mi recomendación?"
                )
            )
        ]
        new_state["completeness_score"] = f"{checklist_status['score']:.2f}"
        new_state["missing_items"] = ", ".join(checklist_status["missing"])
        return new_state

    # Adaptive picker on EVERY turn: real consultations are dynamic, the parent
    # may bring up new info / emotion / event at any point. The LLM picks the
    # most natural next question anchored on what the parent just said. Python
    # remains the safety floor (red flags, urgency, dosing).
    last_user_msg = (last_message.content if last_message else "")
    if isinstance(last_user_msg, list):
        last_user_msg = " ".join(
            item.get("text", "") if isinstance(item, dict) else str(item) for item in last_user_msg
        )

    next_q = None
    candidate_missing = remaining_missing or checklist_status["missing"]
    if last_user_msg and candidate_missing:
        adaptive = pick_next_question_adaptive(
            state=state,
            last_user_message=last_user_msg,
            missing_fields=candidate_missing,
            questions_already_asked=questions_asked,
            history_len=len(history),
        )
        if adaptive is not None:
            next_q = adaptive

    if next_q is None:
        next_q = get_next_question(state, candidate_missing)

    # Out-of-scope graceful exit: parent's case isn't fever — derive politely
    # and end the clinical pipeline. We send the LLM-crafted message and mark
    # the conversation as done so subsequent turns just close.
    if next_q.get("field") == "out_of_scope_exit":
        from langchain_core.messages import AIMessage as _AIMessage
        debug_print("🚪 inquiry: out_of_scope exit chosen by adaptive picker")
        new_state["messages"] = [_AIMessage(content=next_q["question"])]
        new_state["recommendation_section"] = "done"
        new_state["recommended_action"] = "off_scope"
        new_state["last_inquiry_question"] = ""
        new_state["expected_fields"] = "[]"
        new_state["fallback_values"] = "{}"
        return new_state

    # No-fever clarification: prepend short note when user said "fever" but temp <38.
    temp_str = state.get("temperature", "") or ""
    no_fever_clarif_given = state.get("no_fever_clarification_given", "")
    try:
        temp_value = float(temp_str) if temp_str and temp_str != "desconocido" else -1.0
    except (ValueError, TypeError):
        temp_value = -1.0
    if (
        "temperatura" in questions_asked
        and 0 < temp_value < 38.0
        and no_fever_clarif_given != "yes"
    ):
        clarif = (
            f"Tranquilo/a, {temp_value}°C todavía no es fiebre (la fiebre es ≥38°C). "
        )
        next_q["question"] = clarif + next_q["question"]
        new_state["no_fever_clarification_given"] = "yes"

    appreciation = ""
    new_count = len([q for q in questions_asked if q != next_q["field"]]) + 1
    if new_count > 0 and new_count % 4 == 0:
        appreciation = "Gracias por tu paciencia con tantas preguntas, ya casi terminamos."

    patient_name = state.get("patient_name") or "su hijo/a"
    if patient_name == "desconocido":
        patient_name = "su hijo/a"
    age_display = get_age_display(state.get("patient_age_months", ""))

    formatted_prompt = prompt_template.format(
        patient_name=patient_name,
        patient_age_months=state.get("patient_age_months") or "desconocido",
        age_display=age_display,
        temperature=state.get("temperature") or "desconocido",
        temp_location=state.get("thermometer_location") or "desconocido",
        fever_duration=state.get("fever_duration_hours") or "desconocido",
        fever_context=state.get("fever_context") or "",
        next_question=next_q["question"],
        priority_level=next_q["priority"],
        next_field=next_q["field"],
        appreciation_message=appreciation,
        questions_count=new_count,
        last_message=(last_message.content if last_message else ""),
        history_length=len(history),
        missing_items_text=format_missing_items(checklist_status["missing"]),
        checklist_score=int(checklist_status["score"] * 100),
        completed=checklist_status["completed"],
        total=checklist_status["total"],
    )

    try:
        ai_message = _llm.invoke(
            [
                ("system", formatted_prompt),
                (
                    "user",
                    last_message.content if last_message else "(primer turno)",
                ),
            ]
        )
        ai_content = (
            ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        )
    except Exception as exc:
        debug_print(f"❌ Inquiry LLM error: {exc}")
        ai_content = next_q["question"]

    new_state["messages"] = [AIMessage(content=ai_content)]
    new_state["last_inquiry_question"] = next_q["question"]
    new_state["expected_fields"] = json.dumps(next_q["required_fields"])
    new_state["fallback_values"] = json.dumps(next_q["fallback_value"])

    if next_q["field"] not in questions_asked:
        questions_asked.append(next_q["field"])
    new_state["questions_asked"] = json.dumps(questions_asked)

    if red_flags:
        new_state["red_flags_detected"] = ", ".join(red_flags)
    new_state["completeness_score"] = f"{checklist_status['score']:.2f}"
    new_state["missing_items"] = ", ".join(checklist_status["missing"])

    return new_state
