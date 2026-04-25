"""Manual CLI smoke test: drives the chatbot via patient simulator on selected personas."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Defaults for local smoke runs.
os.environ.setdefault("USE_MEMORY_CHECKPOINTER", "1")

from tests.agents.judge import Judge  # noqa: E402
from tests.agents.patient_simulator import Persona, PatientSimulator  # noqa: E402
from tests.agents.runner import ConversationRunner  # noqa: E402


def _run_one(name_or_path: str, max_turns: int) -> int:
    if Path(name_or_path).exists():
        persona = Persona.load(name_or_path)
    else:
        candidates = list((ROOT / "tests" / "agents" / "personas").glob(f"*{name_or_path}*.yaml"))
        if not candidates:
            print(f"❌ no persona matched '{name_or_path}'")
            return 1
        persona = Persona.load(candidates[0])

    print(f"\n=== Persona: {persona.name} ({persona.category}/{persona.dialect}/{persona.emotion}) ===")
    runner = ConversationRunner(max_turns=max_turns)
    simulator = PatientSimulator(persona=persona)
    result = runner.run(simulator)
    print(ConversationRunner.format_transcript(result.transcript))
    print(f"\n>> terminated={result.terminated_reason} turns={result.turns}\n")

    try:
        verdict = Judge().evaluate(persona, result.transcript, result.final_state)
        print(f"VERDICT: score={verdict.score} safety={verdict.safety_passed} routing={verdict.routing_correct}")
        for f in verdict.failures:
            print(f"  ✗ {f}")
        for s in verdict.notable_strengths:
            print(f"  ✓ {s}")
    except Exception as exc:
        print(f"⚠️ judge unavailable: {exc}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("personas", nargs="+", help="persona name (substring match) or path to .yaml")
    parser.add_argument("--max-turns", type=int, default=12)
    args = parser.parse_args()

    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️ GOOGLE_API_KEY not set — set it before running this script.")
        return 1

    rc = 0
    for name in args.personas:
        rc |= _run_one(name, args.max_turns)
    return rc


if __name__ == "__main__":
    sys.exit(main())
