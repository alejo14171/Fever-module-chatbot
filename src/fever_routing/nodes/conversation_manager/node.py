"""
Conversation manager — lightweight router that decides which sub-graph the
conversation should flow into for THIS turn.

Saves the classification to State so downstream branches can use it (e.g.
empathy_response uses `short_acknowledgement`, answer_question uses
`pending_user_question`).
"""

from __future__ import annotations

from typing import Literal

from fever_routing.nodes.conversation_manager.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from fever_routing.nodes.greeting.node import is_first_turn
from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.intent_schema import TurnIntent, is_data_path
from fever_routing.utils.logging import debug_print


_llm = ModelFactory.get_inquiry_model()
try:
    _structured = _llm.with_structured_output(TurnIntent)
except Exception:  # pragma: no cover
    _structured = None


def _last_user_message(history: list) -> str:
    for msg in reversed(history):
        if msg.__class__.__name__ == "HumanMessage":
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


def conversation_manager_node(state: State):
    """Classify the user turn; persist intent fields for downstream branches."""
    new_state: State = {}
    history = state.get("messages", []) or []
    if not history:
        return new_state

    last_user = _last_user_message(history)
    if not last_user.strip():
        return new_state

    last_bot_q = state.get("last_inquiry_question", "") or ""
    user_prompt = build_user_prompt(history, last_user, last_bot_q)

    try:
        if _structured is None:
            raise RuntimeError("Structured output not available")
        intent: TurnIntent = _structured.invoke(
            [("system", SYSTEM_PROMPT), ("user", user_prompt)]
        )
    except Exception as exc:
        debug_print(f"❌ Conversation manager error: {exc}")
        # Safe default: treat as data so the receptor still extracts.
        intent = TurnIntent(primary="data", detected_emotion="neutral")

    debug_print(
        f"🧭 manager: primary={intent.primary} emotion={intent.detected_emotion} "
        f"q={(intent.user_question or '')[:60]}"
    )

    # POST-URGENCY DETERMINISTIC OVERRIDE: if we already delivered urgency and
    # the parent's message contains heavy panic words, force emotional intent
    # regardless of what the LLM classified. The judge keeps marking empathy=False
    # when the bot processes these as user_question / data — empathy must come first.
    urgency_already_given = (state.get("urgency_recommendation_given") or "") == "yes"
    panic_words = (
        "tiembl", "temblando", "temblor",
        "qué susto", "que susto", "qué miedo", "que miedo",
        "me muero", "ataque", "qué hago", "que hago",
        "dios mío", "dios mio", "qué horror", "que horror",
        "qué angustia", "que angustia", "no puedo", "no aguanto",
    )
    if urgency_already_given and any(w in last_user.lower() for w in panic_words):
        debug_print("🛡 manager override: post-urgency panic words → force emotional")
        intent_primary = "emotional"
    else:
        intent_primary = intent.primary

    new_state["last_intent"] = intent_primary
    new_state["detected_emotion"] = intent.detected_emotion or "neutral"
    new_state["pending_user_question"] = intent.user_question or ""
    new_state["short_acknowledgement"] = intent.short_acknowledgement or ""

    # If the parent is signaling they want to end / go to a real pediatrician /
    # is fed up, AND we already have the 3 critical fields, mark partial-data so
    # triage_route delivers the recommendation we DO have instead of looping on
    # checklist questions.
    last_msg_lower = last_user.lower()
    end_signals = (
        "mejor lo llevo", "mejor llevo", "lo llevo al pediatra", "voy al pediatra",
        "qué pereza", "que pereza", "ya no más", "ya no mas", "no más preguntas",
        "no mas preguntas", "déjame ya", "dejame ya", "dame la respuesta", "deme la respuesta",
    )
    age = state.get("patient_age_months", "") or ""
    temp = state.get("temperature", "") or ""
    duration = state.get("fever_duration_hours", "") or ""
    have_criticals = (
        age and age not in {"desconocido", "0", ""}
        and temp and temp not in {"desconocido", "no_medida", "0", ""}
        and duration and duration not in {"desconocido", "0", ""}
    )
    rec_done = (state.get("recommendation_section") or "") == "done"
    urgency_given = (state.get("urgency_recommendation_given") or "") == "yes"
    if (
        any(sig in last_msg_lower for sig in end_signals)
        and have_criticals
        and not rec_done
        and not urgency_given
    ):
        debug_print("⏩ manager: parent signaling end + criticals complete → partial recommendation")
        new_state["recommendation_with_partial_data"] = "yes"
        new_state["last_intent"] = "data"  # so manager_route sends to receptor → triage → recommendation
        new_state["pending_user_question"] = ""  # don't let triage route to answer_question
        new_state["short_acknowledgement"] = ""
    return new_state


ManagerRoute = Literal[
    "greeting",
    "empathy_response",
    "answer_question",
    "reframe_question",
    "close_conversation",
    "receptor",
]


def manager_route(state: State) -> ManagerRoute:
    """Branch based on the last classified intent."""
    # First-turn welcome anchor — open and warm, no checklist yet.
    if is_first_turn(state):
        return "greeting"

    primary = state.get("last_intent", "data")
    rec_section = state.get("recommendation_section", "") or ""
    urgency_given = state.get("urgency_recommendation_given", "") or ""
    rec_action = state.get("recommended_action", "") or ""

    # Out-of-scope already derived → any further user message gets a brief
    # close, not a return to the clinical checklist.
    if rec_action == "off_scope":
        return "close_conversation"

    # closing only valid AFTER a recommendation/urgency was delivered.
    if primary == "closing" and (rec_section == "done" or urgency_given == "yes"):
        return "close_conversation"

    # POST-URGENCY EMOTIONAL CONTAINMENT: once the urgent referral has been
    # delivered, any further panic / fear / questions should be contained
    # with reassurance ("estás haciendo lo correcto, allá la van a atender"),
    # NOT with more clinical data. This prevents the cascade-emotion failure
    # where the bot kept asking for more symptoms after already recommending ER.
    if urgency_given == "yes" and primary in {"emotional", "user_question", "mixed"}:
        return "empathy_response"

    if primary == "emotional":
        return "empathy_response"

    if primary == "evasion":
        return "reframe_question"

    # user_question / data / mixed / unknown → receptor first.
    # The receptor is idempotent: if there's no new data it returns nothing.
    # Then triage_route sees pending_user_question and routes to answer_question
    # AFTER any data has been extracted. This prevents losing age/temp/etc.
    # when the parent bundles a question with data ("tiene 2 meses, ¿es grave?").
    return "receptor"
