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

    new_state["last_intent"] = intent.primary
    new_state["detected_emotion"] = intent.detected_emotion or "neutral"
    new_state["pending_user_question"] = intent.user_question or ""
    new_state["short_acknowledgement"] = intent.short_acknowledgement or ""
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

    if primary == "user_question":
        return "answer_question"

    if primary == "emotional":
        return "empathy_response"

    if primary == "evasion":
        return "reframe_question"

    # data / mixed / unknown → receptor (clinical pipeline).
    return "receptor"
