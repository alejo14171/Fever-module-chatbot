"""
Intent classification schema for the conversation_manager node.

Each turn we classify the user's last message into one of five buckets so the
graph can branch dynamically. Modeled after the production patterns used in
Hartford PatientGPT (2026) and Rasa CALM: lightweight router agent →
specialized branches. The clinical decision logic stays deterministic in
Python — this only routes the conversation surface.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


PrimaryIntent = Literal[
    "data",            # the user is providing clinical info (age, temp, symptoms…)
    "emotional",       # expresses fear/panic/anxiety with no new clinical data
    "user_question",   # asks the bot a direct question ("¿es grave?", "¿qué hago?")
    "evasion",         # changes topic / answers off-question
    "mixed",           # data + emotion together
    "closing",         # gratitude / goodbye after recommendation given
]


DetectedEmotion = Literal[
    "panic",
    "fear",
    "anxiety",
    "frustration",
    "skepticism",
    "exhaustion",
    "gratitude",
    "neutral",
]


class TurnIntent(BaseModel):
    """Lightweight router output for the conversation_manager node."""

    primary: PrimaryIntent = Field(
        ...,
        description=(
            "Bucket the user's MOST RECENT message into one of: data, emotional, "
            "user_question, evasion, mixed, closing. If unclear, default to data."
        ),
    )
    detected_emotion: DetectedEmotion = Field(
        default="neutral",
        description=(
            "Dominant emotion in the user's last message. Use 'neutral' if no clear "
            "emotional signal."
        ),
    )
    user_question: Optional[str] = Field(
        default=None,
        description=(
            "If primary is 'user_question' or 'mixed' AND the user asked the bot "
            "something, copy that question verbatim. Otherwise null."
        ),
    )
    answer_data_too: bool = Field(
        default=False,
        description=(
            "True only when primary is 'mixed' AND the user's message contains both "
            "a question and clinical data the receptor should extract."
        ),
    )
    short_acknowledgement: Optional[str] = Field(
        default=None,
        description=(
            "If detected_emotion is panic/fear/anxiety/frustration, a 1-sentence "
            "warm acknowledgement (≤15 words) the next branch can prepend. "
            "Use natural Colombian Spanish (tutea). Null otherwise."
        ),
    )
    reasoning: str = Field(
        default="",
        description="One sentence explaining the classification (for debugging).",
    )


def is_data_path(intent: TurnIntent) -> bool:
    """Whether this intent should flow through receptor → triage."""
    if intent.primary == "data":
        return True
    if intent.primary == "mixed" and intent.answer_data_too:
        return True
    return False
