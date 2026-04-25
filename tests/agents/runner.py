"""
Conversation runner — drives a chatbot graph with a PatientSimulator.

Iterates turns until: (a) bot reaches urgency_recommendation_given == 'yes',
(b) bot reaches recommendation_section == 'done', or (c) max_turns hit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from fever_routing.agent import make_graph

from tests.agents.patient_simulator import PatientSimulator


@dataclass
class RunResult:
    transcript: list[dict] = field(default_factory=list)
    final_state: dict = field(default_factory=dict)
    turns: int = 0
    terminated_reason: str = ""


class ConversationRunner:
    def __init__(self, max_turns: int = 12) -> None:
        self.max_turns = max_turns
        self._checkpointer = InMemorySaver()
        self._agent = make_graph({"checkpoint": self._checkpointer})

    def _bot_turn(self, message: str, thread_id: str) -> tuple[str, dict]:
        config = {"configurable": {"thread_id": thread_id}}
        response = self._agent.invoke({"messages": [HumanMessage(content=message)]}, config=config)
        last = response["messages"][-1]
        bot_text = last.content if hasattr(last, "content") else str(last)
        return bot_text, response

    def _is_done(self, state: dict) -> Optional[str]:
        if state.get("urgency_recommendation_given") == "yes":
            return "urgency_delivered"
        if state.get("recommendation_section") == "done":
            return "recommendation_delivered"
        return None

    def run(self, simulator: PatientSimulator) -> RunResult:
        thread_id = f"agentic-{uuid.uuid4().hex[:8]}"
        result = RunResult()

        opening = simulator.opening_message()
        result.transcript.append({"role": "user", "content": opening})
        bot_text, full_state = self._bot_turn(opening, thread_id)
        result.transcript.append({"role": "assistant", "content": bot_text})
        result.turns += 1
        done = self._is_done(full_state)
        if done:
            result.terminated_reason = done
            result.final_state = full_state
            return result

        while result.turns < self.max_turns:
            patient_reply = simulator.respond(result.transcript)
            result.transcript.append({"role": "user", "content": patient_reply})
            bot_text, full_state = self._bot_turn(patient_reply, thread_id)
            result.transcript.append({"role": "assistant", "content": bot_text})
            result.turns += 1
            done = self._is_done(full_state)
            if done:
                result.terminated_reason = done
                break

        if not result.terminated_reason:
            result.terminated_reason = "max_turns_reached"
        result.final_state = full_state
        return result

    @staticmethod
    def format_transcript(transcript: list[dict]) -> str:
        lines = []
        for i, t in enumerate(transcript, start=1):
            who = "👤 Padre" if t["role"] == "user" else "🩺 Bot"
            lines.append(f"[{i:02d}] {who}: {t['content']}")
        return "\n".join(lines)
