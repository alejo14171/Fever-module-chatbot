"""
Empathy response — short contention message, then re-anchors the user to the
last clinical question. Does NOT advance the clinical pipeline.

Triggered when conversation_manager classifies the turn as 'emotional'.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()


SYSTEM = """Sos un PEDIATRA colombiano hablando por WhatsApp con una mamá/papá ASUSTADO.

El padre acaba de decirte algo cargado de emoción (miedo, pánico, frustración, agotamiento).

TU JOB en este turno: contención específica. NO sigues con el checklist.

REGLAS DURAS:
- Máximo 2 frases, ≤30 palabras EN TOTAL.
- 1ra frase: validás el sentimiento CONCRETAMENTE (nombrá la emoción del padre, no genérico). Ej:
  "Sé que estás temblando del susto, es normal." / "Entiendo el miedo, tu pelado se va a recuperar."
- 2da frase: depende del contexto:
  * SI YA dimos urgencias y el padre sigue en pánico → reassurance ("Ya vas para urgencias, allá la
    cuidan bien. Concéntrate en llegar tranquila."). NO más preguntas clínicas.
  * SI NO hay última pregunta hecha (primer turno) → pedí 1 dato esencial corto.
  * SI hay última pregunta clínica → retomála suave ("Cuando puedas, ¿pudiste medir la temperatura?").
- Hablás tuteando, español colombiano natural.
- NO uses "como pediatra", "entiendo su preocupación" tipo guion.
- NO des recomendación clínica acá — eso es otro nodo.
- Variá las muletillas turno a turno.

Devolvé SOLO el mensaje al padre, sin meta-comentarios."""


def empathy_response_node(state: State):
    new_state: State = {}
    last_q = state.get("last_inquiry_question", "") or ""
    emotion = state.get("detected_emotion", "neutral") or "neutral"
    ack_seed = state.get("short_acknowledgement", "") or ""
    patient_name = state.get("patient_name") or ""
    if patient_name == "desconocido":
        patient_name = ""

    # Reconstruct context for the LLM
    history = state.get("messages", []) or []
    last_user = ""
    for msg in reversed(history):
        if msg.__class__.__name__ == "HumanMessage":
            last_user = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    urgency_given = state.get("urgency_recommendation_given", "") == "yes"
    rec_done = (state.get("recommendation_section", "") or "") == "done"
    user_prompt = (
        f"Emoción detectada: {emotion}\n"
        f"Acknowledgement sugerido (úsalo o reformulá): {ack_seed or '(ninguno)'}\n"
        f"Nombre del niño/a (si lo sabés): {patient_name or '(no lo sé)'}\n"
        f"Última pregunta clínica que hiciste: {last_q or '(ninguna — es el primer turno)'}\n"
        f"Estado: {'urgencia ya recomendada — el padre va camino a urgencias' if urgency_given else ('recomendación ya entregada' if rec_done else 'aún recolectando datos')}\n"
        f"Mensaje emocional del padre: \"{last_user}\"\n\n"
        f"Generá tu mensaje (2 frases máximo). "
        f"{'CRÍTICO: ya recomendaste urgencias. NO repitas info clínica. Contené y dale fuerza para llegar.' if urgency_given else ''}"
    )

    try:
        response = _llm.invoke([("system", SYSTEM), ("user", user_prompt)])
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Empathy LLM error: {exc}")
        if last_q:
            text = f"Tranquila, entiendo el susto. {last_q}"
        else:
            text = "Tranquila, estoy aquí. Cuéntame, ¿qué edad tiene tu hijo y la temperatura que tiene?"

    new_state["messages"] = [AIMessage(content=text.strip())]
    # Reset transient intent so next turn re-classifies fresh.
    new_state["last_intent"] = ""
    new_state["pending_user_question"] = ""
    new_state["short_acknowledgement"] = ""
    return new_state
