"""Smoke test: scripted dialog turns to verify the new greeting + dynamic flow."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

os.environ.setdefault("USE_MEMORY_CHECKPOINTER", "1")

from langchain_core.messages import HumanMessage  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from fever_routing.agent import make_graph  # noqa: E402


def run(messages: list[str]) -> None:
    saver = InMemorySaver()
    agent = make_graph({"checkpoint": saver})
    cfg = {"configurable": {"thread_id": f"smoke-{uuid.uuid4().hex[:8]}"}}

    for i, text in enumerate(messages, start=1):
        print(f"[{i:02d}] 👤 Padre: {text}")
        result = agent.invoke({"messages": [HumanMessage(content=text)]}, config=cfg)
        last = result["messages"][-1]
        print(f"     🩺 Bot:   {last.content if hasattr(last, 'content') else str(last)}")
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # CLI args = list of user messages
        run(sys.argv[1:])
    else:
        # default: the bug-scenario the user reported
        run([
            "hola",
            "mi hija se golpeo",
            "se cayó del columpio hace una hora, le salió un chichón",
            "tiene 3 años y pesa 14 kilos",
            "no ha vomitado, está despiertita",
        ])
