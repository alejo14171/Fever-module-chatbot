"""
Adaptive question picker — runs on EVERY inquiry turn, not just the first.

The conversation surface (what to ask, how to phrase it, when to acknowledge
something the parent just said) is genuinely dynamic. Python keeps the safety
floor (red flags, urgency, dosing) and the canonical checklist of missing
fields. This module asks the LLM, given the missing-fields list and the
parent's most recent message, which one to pursue NOW and how to phrase it.

If the LLM fails or returns nonsense, the caller falls back to the Python
deterministic `get_next_question`.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()


# Whitelist of fields the adaptive picker may target. Mapped to the same
# `field` keys the Python checklist uses.
TargetField = Literal[
    "antecedentes",
    "temperatura",
    "edad",
    "peso",
    "duracion_fiebre",
    "lugar_termometro",
    "sintomas_generales",
    "sintomas_respiratorios",
    "hidratacion",
    "alimentacion",
    "signos_alarma_visual",
    "medicacion_previa",
    "estado_vacunal",
    "fever_check",         # confirm whether there's actually a fever
    "event_followup",      # anchor on the event the parent just mentioned
    "general_open",        # open invitation when message is too vague
    "out_of_scope_exit",   # parent's case is NOT fever — derive politely
]


class AdaptiveQuestion(BaseModel):
    target_field: TargetField = Field(
        ...,
        description=(
            "Which field/question to pursue NOW. Choose one from the missing list "
            "given to you, OR fever_check / event_followup / general_open if those "
            "fit better given what the parent just said."
        ),
    )
    question_text: str = Field(
        ...,
        description=(
            "Exact phrasing of your message to the parent. ≤2 sentences (≤30 words). "
            "Tutea, español colombiano, sin emojis, sin disclaimers, sin 'como pediatra…'. "
            "ANCLA en lo que el padre acaba de decir: si mencionó algo nuevo (síntoma, "
            "evento, emoción), reconócelo brevemente ANTES de preguntar."
        ),
    )
    reasoning: str = Field(default="", description="One sentence explaining the choice.")


SYSTEM = """Sos un PEDIATRA colombiano por WhatsApp ESPECIALISTA EN FIEBRE PEDIÁTRICA. Cada turno tenés que decidir qué hacer a continuación.

Tenés:
1. Lista de campos clínicos que faltan (Python te la da, son las "casillas" que llenan el checklist).
2. El último mensaje del padre.
3. Datos ya conocidos del paciente.
4. Lo que ya preguntaste.

Tu trabajo: elegir LA respuesta más natural para una consulta REAL — no un script.

REGLAS DE COMPORTAMIENTO (críticas):

**RESPETO AL PADRE — NO INSISTIR:**
- Si el padre dijo claramente "no tiene fiebre" / "no creo que tenga fiebre" / "no es por fiebre"
  → NO insistas en pedirle temperatura. Aceptá su lectura y cambiá el rumbo.
- Si el padre dijo "no tengo termómetro" → NO insistas que mida. Pasá a evaluación táctil
  o a otra pregunta útil.
- Si el padre evita una pregunta dos veces seguidas → cambiá de tema, no machaques.

**SCOPE AWARENESS — Sos chatbot de FIEBRE:**
- Si el padre habla de un evento que NO es fiebre (golpe sin fiebre, vómito aislado, dolor sin fiebre),
  preguntá UNA SOLA VEZ "¿también tiene fiebre o sólo está por [el evento]?".
- Si después de esa pregunta el padre confirma que NO hay fiebre → elegí target='out_of_scope_exit'.
- NUNCA finjas ser pediatra general — sos especialista en fiebre.
- NUNCA uses 'out_of_scope_exit' SI ya tenemos los datos críticos extraídos (edad + temperatura + duración).
  Si el padre se frustra y dice "mejor llevo al pediatra", elegí target='general_open' o el siguiente missing
  para que el sistema entregue la recomendación con los datos parciales que tenemos.

**ANCLA Y ACKNOWLEDGE:**
- Si el padre acaba de mencionar EVENTO/SÍNTOMA NUEVO, reconocelo brevemente ANTES de tu pregunta.
- Las muletillas de transición DEBEN VARIAR turno a turno. Nunca uses la misma palabra inicial dos
  turnos seguidos. Alterná: "Listo.", "Vale.", "Entiendo.", "Ay.", "Te entiendo.", "Bueno.", "Perfecto.",
  "Claro.", o sin muletilla.
- NO uses la misma frase de empatía dos veces ("Entiendo, eso preocupa" → buscá otras formas).
- Si el padre expresó UNA EMOCIÓN específica ("estoy temblando", "qué susto", "estoy desespera/o"),
  usá esas palabras en tu acknowledgement — es lo que da empatía situada.

**PALABRAS PROHIBIDAS:**
- "llamar / llámame / llamenme / llamen / llama" — esto es chat de TEXTO. Si querés invitar a continuar, usá "escribime".
- "Entiendo tu preocupación" como muletilla genérica — usá las palabras del padre.

**SEGURIDAD CLÍNICA:**
- Si el padre menciona red flag (convulsión, no responde, manchitas que no blanquean, cianosis,
  rigidez de nuca, vómito repetido tras golpe), priorizá ESO sobre todo lo demás.
- target_field: UNO de los disponibles, o 'fever_check' / 'event_followup' / 'general_open' / 'out_of_scope_exit'.

**ANTI-REDUNDANCIA (importante):**
- Si el estado ya tiene un valor para un campo (edad, peso, temperatura, duración, etc.), NUNCA
  vuelvas a pedir ese campo. Mira el bloque "Estado conocido del paciente" en el contexto.
- Si todos los missing_fields ya están en el bloque conocido O ya preguntaste, elegí 'out_of_scope_exit'
  o 'general_open' — el sistema decidirá si pasar a recomendación.

EJEMPLOS DE DECISIÓN (estudialos):

Caso A — padre habla de golpe sin fiebre confirmada:
  Padre: "mi hijo se cayó del columpio"
  → target='fever_check', question="Ay, ¿cómo está después de la caída? ¿También tiene fiebre o solo te preocupa el golpe?"

Caso B — padre confirma no hay fiebre, sólo otro síntoma:
  Padre (turno previo: ¿también tiene fiebre?): "no, no creo que tenga fiebre, está un poco decaído"
  → target='out_of_scope_exit', question="Entiendo, no parece ser fiebre. Mi orientación es para fiebre; por el decaimiento + golpe te conviene consulta presencial pronto. Si después le aparece fiebre, escribime de nuevo."

Caso C — padre dice no tiene termómetro pero confirma fiebre:
  Padre: "no tengo termómetro pero está hirviendo"
  → target='temperatura' con fallback táctil, question="Listo, sin termómetro pasamos a evaluación táctil. Pon el dorso de tu mano en la frente y pecho: ¿lo sientes tibio, muy caliente o ardiendo?"

Caso D — padre da temperatura clara:
  Padre: "39 grados en la axila"
  → target='edad' o 'duracion_fiebre' (siguiente missing field), question="Listo, 39°C en axila. ¿Cuántos meses tiene o cuándo nació?"

Caso E — padre menciona red flag mid-flow:
  Padre: "ah por cierto, ayer tembló"
  → target='signos_alarma_visual' o atención inmediata, question="Eso es importante. Cuéntame, ¿la convulsión duró cuánto y cómo está ahora?"

Devolvé SOLO el schema."""


def pick_next_question_adaptive(
    state: dict,
    last_user_message: str,
    missing_fields: list[str],
    questions_already_asked: list[str],
    history_len: int,
) -> Optional[dict]:
    """Return a dict with the same shape as get_next_question() output, or None."""

    if not last_user_message or not last_user_message.strip():
        return None

    keep = [
        "patient_name", "patient_age_months", "temperature", "thermometer_location",
        "fever_duration_hours", "general_symptoms", "respiratory_symptoms",
        "visual_alarm_signs", "medical_history", "fever_context",
    ]
    state_summary_lines = [
        f"  {k}: {state.get(k, '') or '(vacío)'}" for k in keep
    ]
    state_summary = "\n".join(state_summary_lines)

    user_prompt = (
        f"Mensaje más reciente del padre: \"{last_user_message}\"\n\n"
        f"Estado conocido del paciente:\n{state_summary}\n\n"
        f"Campos clínicos que faltan (elegí UNO de aquí o usá fever_check/event_followup/general_open): "
        f"{', '.join(missing_fields) if missing_fields else '(ninguno — checklist completo)'}\n"
        f"Preguntas que YA hiciste (no repitas): {', '.join(questions_already_asked) or '(ninguna)'}\n"
        f"Turnos previos: {history_len}\n\n"
        f"Elegí target_field y redactá la pregunta natural."
    )

    try:
        structured = _llm.with_structured_output(AdaptiveQuestion)
        result: AdaptiveQuestion = structured.invoke(
            [("system", SYSTEM), ("user", user_prompt)]
        )
    except Exception as exc:
        debug_print(f"❌ adaptive picker error: {exc}")
        return None

    debug_print(
        f"🎯 adaptive: target={result.target_field} → '{result.question_text[:80]}'"
    )

    field_meta = {
        "antecedentes": {
            "field": "antecedentes",
            "required_fields": ["medical_history"],
            "fallback_value": {"medical_history": "no"},
            "extraction_hint": "Si dice 'no'/'ninguno'/'sano' → medical_history: no.",
        },
        "temperatura": {
            "field": "temperatura",
            "required_fields": ["temperature", "thermometer_location", "has_thermometer"],
            "fallback_value": {"has_thermometer": "no"},
            "extraction_hint": "Extraer temperature, thermometer_location, has_thermometer.",
        },
        "edad": {
            "field": "edad",
            "required_fields": ["patient_age_months", "patient_birthdate"],
            "fallback_value": {},
            "extraction_hint": "Extraer patient_age_months o patient_birthdate.",
        },
        "peso": {
            "field": "peso",
            "required_fields": ["patient_weight_kg"],
            "fallback_value": {},
            "extraction_hint": "Extraer patient_weight_kg.",
        },
        "duracion_fiebre": {
            "field": "duracion_fiebre",
            "required_fields": ["fever_duration_hours"],
            "fallback_value": {},
            "extraction_hint": "Extraer fever_duration_hours o fever_start_datetime.",
        },
        "lugar_termometro": {
            "field": "lugar_termometro",
            "required_fields": ["thermometer_location"],
            "fallback_value": {"thermometer_location": "axilar"},
            "extraction_hint": "thermometer_location: axilar/rectal/oral/frontal/oido.",
        },
        "sintomas_generales": {
            "field": "sintomas_generales",
            "required_fields": ["general_symptoms", "hydration_status", "feeding_status"],
            "fallback_value": {
                "general_symptoms": "juega:si, decaido:no",
                "hydration_status": "bebe_normal:si, orina_normal:si",
                "feeding_status": "come_normal:si",
            },
            "extraction_hint": "Extraer general_symptoms, hydration_status, feeding_status.",
        },
        "sintomas_respiratorios": {
            "field": "sintomas_respiratorios",
            "required_fields": ["respiratory_symptoms", "visual_alarm_signs"],
            "fallback_value": {
                "respiratory_symptoms": "dificultad_respirar:no, tos:no",
                "visual_alarm_signs": "palido:no, cianosis:no, rash:no",
            },
            "extraction_hint": "Extraer respiratory_symptoms y visual_alarm_signs.",
        },
        "hidratacion": {
            "field": "hidratacion",
            "required_fields": ["hydration_status"],
            "fallback_value": {"hydration_status": "bebe_normal:si"},
            "extraction_hint": "Extraer hydration_status.",
        },
        "alimentacion": {
            "field": "alimentacion",
            "required_fields": ["feeding_status"],
            "fallback_value": {"feeding_status": "come_normal:si"},
            "extraction_hint": "Extraer feeding_status.",
        },
        "signos_alarma_visual": {
            "field": "signos_alarma_visual",
            "required_fields": ["visual_alarm_signs"],
            "fallback_value": {"visual_alarm_signs": "palido:no, cianosis:no, rash:no"},
            "extraction_hint": "Extraer visual_alarm_signs.",
        },
        "medicacion_previa": {
            "field": "medicacion_previa",
            "required_fields": ["medication_given"],
            "fallback_value": {"medication_given": "no"},
            "extraction_hint": "medication_given (con dosis y tiempo) o 'no'.",
        },
        "estado_vacunal": {
            "field": "estado_vacunal",
            "required_fields": ["vaccination_status"],
            "fallback_value": {"vaccination_status": "desconocido"},
            "extraction_hint": "vaccination_status: completo/incompleto/desconocido.",
        },
        "fever_check": {
            "field": "fever_check",
            "required_fields": ["temperature", "tactile_fever_assessment", "has_thermometer"],
            "fallback_value": {},
            "extraction_hint": "Si confirma fiebre, extraer temperature o tactile. Si no, deja vacío.",
        },
        "event_followup": {
            "field": "event_followup",
            "required_fields": ["other_symptoms", "general_symptoms"],
            "fallback_value": {},
            "extraction_hint": "Extraer detalles del evento en other_symptoms o general_symptoms.",
        },
        "general_open": {
            "field": "general_open",
            "required_fields": [],
            "fallback_value": {},
            "extraction_hint": "Extraer cualquier dato clínico mencionado.",
        },
        "out_of_scope_exit": {
            "field": "out_of_scope_exit",
            "required_fields": [],
            "fallback_value": {},
            "extraction_hint": "Caso fuera de scope (no es fiebre).",
        },
    }
    meta = field_meta.get(result.target_field, field_meta["general_open"])

    return {
        "question": result.question_text.strip(),
        "priority": f"🎯 ADAPTATIVO ({result.target_field})",
        "field": meta["field"],
        "required_fields": meta["required_fields"],
        "fallback_value": meta["fallback_value"],
        "extraction_hint": meta["extraction_hint"],
        "_adaptive": True,
    }
