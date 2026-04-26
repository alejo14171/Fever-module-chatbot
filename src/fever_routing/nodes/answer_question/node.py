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

ORDEN DEL MENSAJE:
1. RESPONDÉ primero la pregunta del padre con lo que sabés. NO empieces con "Para responderte necesito X" — eso evade.
2. Si la pregunta requiere un dato faltante para una respuesta completa, dale primero un esbozo honesto ("Lo que sé hasta ahora es X") y al final pedí ese dato.
3. Para "¿es grave?" / "¿qué hago?": no minimices NI alarmes. Anclá la respuesta en datos reales que ya tenés.

REGLA DE SAFETY CRÍTICA (sobre minimización):
- **NUNCA digas "no es grave por sí sola", "no necesariamente es grave", "es común"** sobre una fiebre
  cuando NO sabés la edad confirmada del paciente. Si el padre usa "bebé", "recién nacido",
  "mi'jo chiquito", "Valentina/Mateo/etc" (nombres) sin edad explícita, asumí que PUEDE ser <3 meses
  (criterio crítico de urgencia). En ese caso, NO minimices — decile claramente:
  "No puedo decirte si es grave hasta saber su edad. Si es bebé pequeño (menos de 3 meses) con esa
  fiebre, sería urgencia. Decime cuántos meses tiene."
- Si hay temperatura ≥38°C pero NO edad → priorizá pedir edad ANTES de cualquier juicio sobre gravedad.

PALABRAS PROHIBIDAS:
- "llamar / llamame / llámenme / llamen / llama una ambulancia" — esto es chat de TEXTO. Para futuras dudas decí "escribime". Si la pregunta lo amerita, decí "pedir/marcar al 123" para ambulancia.
- "Entiendo tu preocupación" como muletilla genérica — usá las palabras del padre.
- "si te urge antes…", "antes de que pueda orientarte", "consulta con tu pediatra o urgencias" como cierre genérico. Sólo escalá si hay red flag real.

Variá las muletillas turno a turno. NO repitas frase exacta del turno anterior.

Devolvé SOLO el mensaje al padre, sin meta-comentarios."""


def _has_critical_data(state: State) -> bool:
    age = safe_parse_int(state.get("patient_age_months", ""), -1)
    temp = safe_parse_float(state.get("temperature", ""), -1.0)
    duration = safe_parse_float(state.get("fever_duration_hours", ""), -1.0)
    tactile = state.get("tactile_fever_assessment") or ""
    has_temp_signal = temp > 0 or bool(tactile)
    return age >= 0 and has_temp_signal and duration >= 0


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

    has_thermometer = state.get("has_thermometer") or "desconocido"
    tactile = state.get("tactile_fever_assessment") or "(no evaluado)"
    weight = state.get("patient_weight_kg") or "desconocido"
    other_sym = state.get("other_symptoms") or "(ninguno)"

    user_prompt = (
        f"PREGUNTA DEL PADRE: \"{question}\"\n\n"
        f"DATOS QUE TENÉS DEL PACIENTE:\n"
        f"  Edad meses: {age}\n"
        f"  Peso kg: {weight}\n"
        f"  Temperatura medida: {temp}\n"
        f"  Termómetro: {has_thermometer}\n"
        f"  Evaluación táctil de fiebre: {tactile}\n"
        f"  Duración fiebre (h): {duration}\n"
        f"  Síntomas generales: {state.get('general_symptoms', '') or '(no recolectado)'}\n"
        f"  Otros síntomas (dolor, etc): {other_sym}\n"
        f"  Antecedentes: {state.get('medical_history', '') or '(no recolectado)'}\n"
        f"  Red flags detectados: {', '.join(red_flags) if red_flags else 'ninguno'}\n"
        f"  Nivel de urgencia calculado: {urgency['level']}\n\n"
        f"DATOS CRÍTICOS COMPLETOS: {'sí' if has_critical else 'no'}\n"
        f"ÚLTIMA PREGUNTA QUE HABÍAS HECHO: {last_q or '(ninguna)'}\n"
        f"ESTADO RECOMENDACIÓN: {'ya entregada' if rec_section == 'done' else ('urgencia entregada' if urgency_given == 'yes' else 'pendiente')}\n"
        + (f"\nRECOMENDACIÓN PREVIA RESUMEN: {prior_assessment[:300]}\n" if prior_assessment else "")
        + "\nGenerá tu respuesta corta y segura. Si tienes evaluación táctil, ÚSALA — no pidas otra vez la temperatura. Si tienes 'caliente' táctil + edad ≥6m + sin red flags, podés sugerir dosis de paracetamol calculada por peso."
    )

    try:
        response = _llm.invoke([("system", SYSTEM), ("user", user_prompt)])
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Answer-question LLM error: {exc}")
        if has_critical:
            text = "Te respondo con lo que sé. Por la edad, temperatura y duración que me diste, te conviene consultar pediatra para evaluar mejor. ¿Hay algún síntoma nuevo que quieras contarme?"
        else:
            text = "Para responderte bien necesito un dato más. ¿Pudiste medir la temperatura?"

    # SAFETY GUARD (post-process): never let the bot minimize a fever in a child
    # whose age is unknown — it could be <3 months (critical).
    age_known = age != "desconocido" and age != "" and age != "0"
    try:
        temp_val = float(temp) if temp not in ("desconocido", "no_medida", "", "0") else 0.0
    except (ValueError, TypeError):
        temp_val = 0.0
    if not age_known and temp_val >= 38.0:
        minimization_phrases = [
            "no es grave por sí",
            "no es grave por si",
            "no es grave por sí sola",
            "no necesariamente es grave",
            "es común",
            "no parece grave",
            "no suele ser grave",
            "no debes preocuparte",
            "no te preocupes",
        ]
        lower = text.lower()
        if any(p in lower for p in minimization_phrases):
            debug_print("🛡 SAFETY: replacing minimizing answer (age unknown + temp≥38)")
            text = (
                "No puedo decirte si es grave hasta saber su edad. Si es bebé pequeño "
                "(menos de 3 meses), una fiebre así sería urgencia. ¿Cuántos meses tiene?"
            )

    new_state["messages"] = [AIMessage(content=text.strip())]
    new_state["last_intent"] = ""
    new_state["pending_user_question"] = ""
    new_state["short_acknowledgement"] = ""
    return new_state
