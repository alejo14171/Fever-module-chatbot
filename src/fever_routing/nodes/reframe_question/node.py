"""
Reframe — when the parent evaded the last clinical question, gently steer the
conversation back without sounding robotic. Doesn't advance the pipeline.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()


SYSTEM = """Sos un PEDIATRA colombiano. El padre acaba de evadir tu última pregunta o cambió de tema.

Tu trabajo: retomar la pregunta SIN regaño, con calidez.

REGLAS DURAS:
- Máximo 2 frases, ≤30 palabras.
- 1ra frase: micro-validación o transición ("Vale.", "Te entiendo.", "Antes de avanzar te ayudo con eso, pero…").
- 2da frase: la pregunta original, fraseada con un poco más de contexto si ayuda.
- Tutear. Sin "como pediatra…". Sin emojis. Sin reproche.

Devolvé SOLO el mensaje al padre."""


def reframe_question_node(state: State):
    new_state: State = {}
    last_q = state.get("last_inquiry_question", "") or ""
    history = state.get("messages", []) or []
    last_user = ""
    for msg in reversed(history):
        if msg.__class__.__name__ == "HumanMessage":
            last_user = msg.content if isinstance(msg.content, str) else str(msg.content)
            break

    user_prompt = (
        f"Última pregunta que hiciste: \"{last_q or '(no hubo)'}\"\n"
        f"Respuesta del padre que la evadió: \"{last_user}\"\n\n"
        f"Reformulá tu pregunta amablemente. Si no hubo última pregunta, pedí UN dato base "
        f"(edad, temperatura o nombre)."
    )

    try:
        response = _llm.invoke([("system", SYSTEM), ("user", user_prompt)])
        text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        debug_print(f"❌ Reframe LLM error: {exc}")
        text = last_q or "Cuéntame: ¿qué edad tiene tu hijo y la temperatura que tiene?"

    new_state["messages"] = [AIMessage(content=text.strip())]
    new_state["last_intent"] = ""
    new_state["pending_user_question"] = ""
    new_state["short_acknowledgement"] = ""
    return new_state
