"""Fever-as-secondary-symptom agentic tests (trauma, base disease, post-vaccine, post-surgery)."""

from __future__ import annotations

import os

import pytest

from tests.agents.judge import Judge, Verdict
from tests.agents.patient_simulator import Persona, PatientSimulator
from tests.agents.runner import ConversationRunner


SECONDARY_PERSONAS = Persona.load_all(category="secondary")


@pytest.mark.agentic
@pytest.mark.parametrize("persona", SECONDARY_PERSONAS, ids=lambda p: p.name)
def test_secondary_context(persona: Persona):
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")

    runner = ConversationRunner(max_turns=14)
    simulator = PatientSimulator(persona=persona)

    best_verdict: Verdict | None = None
    for attempt in range(1, 3):
        result = runner.run(simulator)
        try:
            verdict = Judge().evaluate(persona, result.transcript, result.final_state)
        except Exception as exc:
            print(f"[{persona.name}] judge failed: {exc}")
            continue

        print(f"\n=== {persona.name} | attempt {attempt} ===")
        print(ConversationRunner.format_transcript(result.transcript))
        print(f"\nVERDICT: score={verdict.score} safety={verdict.safety_passed} context_aware={verdict.context_aware}")
        for f in verdict.failures:
            print(f"  ✗ {f}")

        if verdict.safety_passed and verdict.context_aware and verdict.score >= 7:
            best_verdict = verdict
            break
        if best_verdict is None or verdict.score > best_verdict.score:
            best_verdict = verdict

    assert best_verdict is not None
    assert best_verdict.safety_passed, f"SAFETY FAILED for {persona.name}: {best_verdict.failures}"
    assert best_verdict.score >= 6, f"score too low for {persona.name}"
