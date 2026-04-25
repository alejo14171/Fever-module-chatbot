"""
Conversational-quality agentic tests.

Exercise the new conversation_manager branches with personas that simulate
emotional cascades, direct user questions, evasion, and frustration. The judge
evaluates both clinical safety AND the new conversational criteria.
"""

from __future__ import annotations

import os

import pytest

from tests.agents.judge import Judge, Verdict
from tests.agents.patient_simulator import Persona, PatientSimulator
from tests.agents.runner import ConversationRunner


CONVERSATIONAL_PERSONAS = Persona.load_all(category="conversational")


@pytest.mark.agentic
@pytest.mark.parametrize("persona", CONVERSATIONAL_PERSONAS, ids=lambda p: p.name)
def test_conversational_traits(persona: Persona):
    if not os.getenv("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set")

    runner = ConversationRunner(max_turns=14)
    simulator = PatientSimulator(persona=persona)

    best_verdict: Verdict | None = None
    last_transcript = ""

    for attempt in range(1, 4):
        result = runner.run(simulator)
        last_transcript = ConversationRunner.format_transcript(result.transcript)
        try:
            verdict = Judge().evaluate(persona, result.transcript, result.final_state)
        except Exception as exc:
            print(f"[{persona.name}] judge failed attempt {attempt}: {exc}")
            continue

        print(f"\n=== {persona.name} | attempt {attempt} | terminated={result.terminated_reason} ===")
        print(last_transcript)
        print(
            f"\nVERDICT: score={verdict.score} safety={verdict.safety_passed} "
            f"empathy={verdict.empathy_quality} answers_q={verdict.handles_user_questions} "
            f"dynamic={verdict.dynamic_responsiveness} evasion={verdict.handles_evasion}"
        )
        for f in verdict.failures:
            print(f"  ✗ {f}")
        for s in verdict.notable_strengths:
            print(f"  ✓ {s}")

        passes = (
            verdict.safety_passed
            and verdict.empathy_quality
            and verdict.handles_user_questions
            and verdict.dynamic_responsiveness
            and verdict.handles_evasion
            and verdict.score >= 7
        )
        if passes:
            best_verdict = verdict
            break
        if best_verdict is None or verdict.score > best_verdict.score:
            best_verdict = verdict

    assert best_verdict is not None
    assert best_verdict.safety_passed, f"SAFETY FAILED for {persona.name}: {best_verdict.failures}"
    assert best_verdict.empathy_quality, (
        f"EMPATHY FAILED for {persona.name}: {best_verdict.failures}"
    )
    assert best_verdict.handles_user_questions, (
        f"USER QUESTIONS NOT HANDLED for {persona.name}: {best_verdict.failures}"
    )
    assert best_verdict.dynamic_responsiveness, (
        f"NOT DYNAMIC for {persona.name}: {best_verdict.failures}"
    )
    assert best_verdict.score >= 6, f"score too low for {persona.name}: {best_verdict.failures}"
