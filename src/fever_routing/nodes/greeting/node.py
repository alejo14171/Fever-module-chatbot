"""
Greeting node — the FIRST turn only.

A pediatrician's first message on the phone is warm and open: greets, validates
that the parent reached out, and asks an open question. NO clinical checklist
yet. Aligned with the 2026 best practice of "warm anchor turn before
data-gathering" used by Hartford PatientGPT and Rasa CALM.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()


def is_first_turn(state: State) -> bool:
    """True iff there's no AIMessage yet in the history (the bot hasn't spoken)."""
    history = state.get("messages", []) or []
    for msg in history:
        if msg.__class__.__name__ == "AIMessage":
            return False
    return True


SYSTEM = """Sos un PEDIATRA colombiano, primer turno de un chat de WhatsApp con un padre/madre.

Tu trabajo: RECIBIR cálido + invitar a contar, SIN checklist técnico todavía.

REGLAS DURAS:
- Máximo 2 frases, ≤25 palabras EN TOTAL.
- 1ra frase: saludo cálido y validación ("Hola, qué bueno que me escribes." / "Buenas, te ayudo con gusto.").
- 2da frase: invitación abierta o, si el padre ya mencionó algo concreto, una pregunta natural que SIGA SU LÍNEA — no saltes a otra cosa.
- Tutear. Sin "como pediatra…", sin emojis, sin disclaimers.
- Si el padre menciona síntoma → ancla en ese síntoma ("¿desde cuándo?", "¿cómo lo ves?").
- Si menciona evento (golpe, caída, vómito) → ancla en cómo está AHORA, no asumas fiebre.
- NO preguntes condiciones de base, ni edad, ni temperatura en esta primera respuesta.

Devolvé SOLO el mensaje al padre."""


def greeting_node(state: State):
    history = state.get("messages", []) or []
    last_user = ""
    for msg in reversed(history):
        if msg.__class__.__name__ == "HumanMessage":
            last_user = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    user_prompt = (
        f"Primer mensaje del padre/madre: \"{last_user}\"\n\n"
        f"Generá tu mensaje de bienvenida (2 frases máximo, ancla en lo que dijo)."
    )
    try:
        response = _llm.invoke([("system", SYSTEM), ("user", user_prompt)])
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Greeting LLM error: {exc}")
        text = "Hola, te ayudo con gusto. Cuéntame, ¿qué pasa con tu peque?"

    return {
        "messages": [AIMessage(content=text.strip())],
        "last_intent": "",
        "pending_user_question": "",
        "short_acknowledgement": "",
    }
