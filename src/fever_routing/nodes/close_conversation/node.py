"""
Close — short warm goodbye after recommendation/urgency/off-scope was delivered.
Uses LLM for natural variation anchored on the parent's last message.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()


SYSTEM = """Sos un PEDIATRA colombiano cerrando una conversación de WhatsApp.

REGLAS DURAS:
- 1 frase, ≤20 palabras.
- Si el padre agradeció, despídete cálido y deseale lo mejor.
- Si el padre todavía duda, podés repetir brevemente el mensaje clave (1 frase).
- Hablás tuteando, sin emojis, sin disclaimers, sin "como pediatra...".
- Variá las muletillas turno a turno. NO repitas frase exacta del turno anterior.

Devolvé SOLO el mensaje al padre."""


def close_conversation_node(state: State):
    rec_action = state.get("recommended_action") or ""
    urgency_given = (state.get("urgency_recommendation_given") or "") == "yes"

    history = state.get("messages", []) or []
    last_user = ""
    for msg in reversed(history):
        if msg.__class__.__name__ == "HumanMessage":
            last_user = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    if rec_action == "off_scope":
        context_note = "(caso fuera de scope: no es fiebre, ya derivamos a pediatra)"
    elif urgency_given:
        context_note = "(ya enviamos a urgencias)"
    else:
        context_note = "(ya dimos recomendación de manejo en casa)"

    user_prompt = (
        f"Contexto: {context_note}\n"
        f"Último mensaje del padre: \"{last_user}\"\n\n"
        f"Generá tu mensaje de cierre (1 frase)."
    )
    try:
        response = _llm.invoke([("system", SYSTEM), ("user", user_prompt)])
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Close LLM error: {exc}")
        text = "Cualquier cosa, escríbeme de nuevo. Suerte."

    return {
        "messages": [AIMessage(content=text.strip())],
        "last_intent": "",
        "pending_user_question": "",
        "short_acknowledgement": "",
    }
