"""
Answer-user-question node.

When the parent asks the bot a direct question ("¿es grave?", "¿qué hago?"),
this node decides between three SAFE responses:

1. If we have the 3 critical fields (age + temp + duration) → tentative
   guidance based on what we know + 1 question to refine.
2. If critical fields are missing → contention + ask for the missing piece.
   Never invent guidance without minimal data (Mount Sinai 2026 finding:
   the #1 failure mode of clinical LLMs is over-confidence with sparse data).
3. If user asks meta/operational stuff ("¿cuánto tiempo más?") and a
   recommendation was already delivered → reference it.

Per the 2026 healthcare-agent guardrail pattern: when in doubt, escalate to
"consultá pediatra/urgencias" rather than fabricate.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from fever_routing.routes.triage.route import (
    assess_urgency,
    detect_red_flags,
    safe_parse_float,
    safe_parse_int,
)
from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()


SYSTEM = """Sos un PEDIATRA colombiano respondiendo una pregunta DIRECTA del padre/madre.

REGLAS DURAS:
- Máximo 3 frases, ≤55 palabras.
- Hablás tuteando, sin emojis, sin "como pediatra…".
- Tu respuesta debe ser HONESTA Y SEGURA — no inventes diagnóstico ni dosis sin datos.
- Si te pasan datos críticos faltantes en el contexto, pedí UNO específico al final ("para responderte bien necesito X").
- Si NO tenés datos suficientes para opinar con seguridad: contené + pedí dato faltante + escalá ("si te urge antes de que pueda orientarte, consultá pediatra/urgencias").
- Si tenés datos suficientes: respuesta tentativa breve + 1 pregunta para refinar.
- Para preguntas tipo "¿es grave?" / "¿qué hago?": no minimices NI alarmes. Da contexto basado en datos reales que tienes.

Devolvé SOLO el mensaje al padre, sin meta-comentarios."""


def _has_critical_data(state: State) -> bool:
    age = safe_parse_int(state.get("patient_age_months", ""), -1)
    temp = safe_parse_float(state.get("temperature", ""), -1.0)
    duration = safe_parse_float(state.get("fever_duration_hours", ""), -1.0)
    return age >= 0 and temp > 0 and duration >= 0


def answer_question_node(state: State):
    new_state: State = {}
    question = state.get("pending_user_question", "") or ""
    if not question:
        # Fallback: use the last user message as the question.
        history = state.get("messages", []) or []
        for msg in reversed(history):
            if msg.__class__.__name__ == "HumanMessage":
                question = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

    has_critical = _has_critical_data(state)
    age = state.get("patient_age_months") or "desconocida"
    temp = state.get("temperature") or "no medida"
    duration = state.get("fever_duration_hours") or "desconocida"
    last_q = state.get("last_inquiry_question", "") or ""
    rec_section = state.get("recommendation_section", "") or ""
    urgency_given = state.get("urgency_recommendation_given", "") or ""

    # If a recommendation/urgency was already given, defer to that context.
    prior_assessment = ""
    if rec_section == "done":
        prior_assessment = state.get("recommendation_section_1", "") or ""

    urgency = assess_urgency(state)
    red_flags = detect_red_flags(state)

    user_prompt = (
        f"PREGUNTA DEL PADRE: \"{question}\"\n\n"
        f"DATOS QUE TENÉS DEL PACIENTE:\n"
        f"  Edad meses: {age}\n"
        f"  Temperatura: {temp}\n"
        f"  Duración fiebre (h): {duration}\n"
        f"  Síntomas generales: {state.get('general_symptoms', '') or '(no recolectado)'}\n"
        f"  Antecedentes: {state.get('medical_history', '') or '(no recolectado)'}\n"
        f"  Red flags detectados: {', '.join(red_flags) if red_flags else 'ninguno'}\n"
        f"  Nivel de urgencia calculado: {urgency['level']}\n\n"
        f"DATOS CRÍTICOS COMPLETOS: {'sí' if has_critical else 'no'}\n"
        f"ÚLTIMA PREGUNTA QUE HABÍAS HECHO: {last_q or '(ninguna)'}\n"
        f"ESTADO RECOMENDACIÓN: {'ya entregada' if rec_section == 'done' else ('urgencia entregada' if urgency_given == 'yes' else 'pendiente')}\n"
        + (f"\nRECOMENDACIÓN PREVIA RESUMEN: {prior_assessment[:300]}\n" if prior_assessment else "")
        + "\nGenerá tu respuesta corta y segura."
    )

    try:
        response = _llm.invoke([("system", SYSTEM), ("user", user_prompt)])
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Answer-question LLM error: {exc}")
        if has_critical:
            text = "Te respondo con lo que sé. Por la edad, temperatura y duración que me diste, te conviene consultar pediatra para evaluar mejor. ¿Hay algún síntoma nuevo que quieras contarme?"
        else:
            text = "Para responderte bien necesito un dato más. Si te urge antes, consulta pediatra. ¿Pudiste medir la temperatura?"

    new_state["messages"] = [AIMessage(content=text.strip())]
    new_state["last_intent"] = ""
    new_state["pending_user_question"] = ""
    new_state["short_acknowledgement"] = ""
    return new_state
