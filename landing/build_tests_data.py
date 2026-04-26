#!/usr/bin/env python3
"""
Parse pytest agentic suite log files and produce a single tests_data.json
consumed by the landing page tests view.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

LOG = Path("/tmp/fever-runs/full_v7.log")
RETRY_LOG = Path("/tmp/fever-runs/v8_retry.log")
LATEST_LOG = Path("/tmp/fever-runs/final_full.log")
OUT = Path(__file__).parent / "tests_data.json"

ATTEMPT_RE = re.compile(r"^=== (?P<name>[^|]+?) \| attempt (?P<n>\d+)(?: \| terminated=(?P<term>[^=]+))? ===\s*$")
TURN_RE = re.compile(r"^\[(?P<idx>\d+)\]\s+(?P<who>👤 Padre|🩺 Bot):\s*(?P<text>.*)$")
VERDICT_RE = re.compile(r"^VERDICT:\s*(?P<rest>.+)$")
RESULT_RE = re.compile(r"^(PASSED|FAILED)$")

CATEGORY_LABELS = {
    "01": ("critical", "Neonato 2m con fiebre", "🚨 Crítico"),
    "02": ("critical", "Lactante 5m + 39.5°C", "🚨 Crítico"),
    "03": ("critical", "Niño 4y + 41°C", "🚨 Crítico"),
    "04": ("critical", "Convulsión 2y", "🚨 Crítico"),
    "05": ("critical", "Cianosis 8m", "🚨 Crítico"),
    "06": ("critical", "Petequias 3y", "🚨 Crítico"),
    "07": ("critical", "Rigidez nuca 5y", "🚨 Crítico"),
    "08": ("critical", "No responde 2y", "🚨 Crítico"),
    "09": ("home", "Niño 5y, fiebre simple", "🏠 Manejo casa"),
    "10": ("home", "Febrícula 3y (no fiebre)", "🏠 Manejo casa"),
    "11": ("home", "Niño 7y + acetaminofén", "🏠 Manejo casa"),
    "12": ("home", "Niña 4y postvacunal", "🏠 Manejo casa"),
    "13": ("secondary", "Trauma columpio 1y", "🧒 Síntoma secundario"),
    "14": ("secondary", "Leucemia + fiebre 6y", "🧒 Síntoma secundario"),
    "15": ("secondary", "Cardiopatía 3y", "🧒 Síntoma secundario"),
    "16": ("secondary", "Post-cirugía 2y", "🧒 Síntoma secundario"),
    "17": ("ambiguous", "Sin termómetro", "🤔 Ambiguo"),
    "18": ("ambiguous", "Contradicción de edad", "🤔 Ambiguo"),
    "19": ("ambiguous", "Late seizure disclosure", "🤔 Ambiguo"),
    "20": ("ambiguous", "Skeptical minimizer", "🤔 Ambiguo"),
    "21": ("conversational", "Emotional evasion", "💬 Conversacional"),
    "22": ("conversational", "User asks back", "💬 Conversacional"),
    "23": ("conversational", "Frustration escalation", "💬 Conversacional"),
    "24": ("conversational", "Direct question first", "💬 Conversacional"),
    "25": ("conversational", "Cascade emocional", "💬 Conversacional"),
}


def parse_log(path: Path) -> dict[str, list[dict]]:
    """Return a dict {persona_name: [attempt, ...]}"""
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    result: dict[str, list[dict]] = {}
    current = None
    current_attempt = None

    i = 0
    while i < len(lines):
        line = lines[i]
        m_attempt = ATTEMPT_RE.match(line)
        if m_attempt:
            if current and current_attempt:
                result.setdefault(current, []).append(current_attempt)
            current = m_attempt.group("name").strip()
            current_attempt = {
                "attempt": int(m_attempt.group("n")),
                "terminated": (m_attempt.group("term") or "").strip(),
                "transcript": [],
                "verdict": None,
                "failures": [],
                "strengths": [],
                "result": None,
            }
            i += 1
            continue

        if current_attempt is not None:
            m_turn = TURN_RE.match(line)
            if m_turn:
                role = "user" if m_turn.group("who").startswith("👤") else "bot"
                current_attempt["transcript"].append({
                    "idx": int(m_turn.group("idx")),
                    "role": role,
                    "text": m_turn.group("text").strip(),
                })
                i += 1
                continue

            m_verdict = VERDICT_RE.match(line)
            if m_verdict:
                rest = m_verdict.group("rest")
                # Parse key=value tokens
                kv = {}
                for token in re.finditer(r"(\w+)=([\w.\-]+)", rest):
                    kv[token.group(1)] = token.group(2)
                current_attempt["verdict"] = kv

                # Read consecutive lines starting with "  ✗" or "  ✓"
                j = i + 1
                while j < len(lines):
                    detail = lines[j]
                    if detail.startswith("  ✗"):
                        current_attempt["failures"].append(detail[3:].lstrip())
                    elif detail.startswith("  ✓"):
                        current_attempt["strengths"].append(detail[3:].lstrip())
                    elif RESULT_RE.match(detail.strip()):
                        current_attempt["result"] = detail.strip()
                        i = j + 1
                        # Save attempt
                        if current:
                            result.setdefault(current, []).append(current_attempt)
                        current_attempt = None
                        break
                    elif ATTEMPT_RE.match(detail) or detail.startswith("tests/integration"):
                        # Next attempt or test starts; save current
                        if current and current_attempt:
                            result.setdefault(current, []).append(current_attempt)
                        current_attempt = None
                        i = j
                        break
                    j += 1
                else:
                    if current and current_attempt:
                        result.setdefault(current, []).append(current_attempt)
                    current_attempt = None
                    i = j
                continue

        i += 1

    if current and current_attempt:
        result.setdefault(current, []).append(current_attempt)

    return result


def merge(*sources):
    """Merge attempts from multiple log files; later sources override earlier."""
    out: dict[str, list[dict]] = {}
    for src in sources:
        for name, attempts in src.items():
            out[name] = attempts
    return out


def build_dataset() -> list[dict]:
    # Order matters: latest log overrides earlier results.
    parsed = merge(parse_log(LOG), parse_log(RETRY_LOG), parse_log(LATEST_LOG))
    dataset = []
    for name, attempts in parsed.items():
        prefix = name.split("_", 1)[0]
        category, label, badge = CATEGORY_LABELS.get(prefix, ("other", name, "•"))
        # Pick the LAST attempt as the canonical result (or the first PASS).
        best_attempt = None
        for att in attempts:
            if att.get("result") == "PASSED":
                best_attempt = att
                break
        if best_attempt is None and attempts:
            best_attempt = attempts[-1]

        if not best_attempt:
            continue

        verdict = best_attempt.get("verdict") or {}
        score = verdict.get("score", "?")
        try:
            score_num = int(score)
        except (TypeError, ValueError):
            score_num = None

        dataset.append({
            "id": name,
            "prefix": prefix,
            "label": label,
            "badge": badge,
            "category": category,
            "result": best_attempt.get("result", "UNKNOWN"),
            "score": score_num,
            "verdict": verdict,
            "transcript": best_attempt.get("transcript", []),
            "failures": best_attempt.get("failures", []),
            "strengths": best_attempt.get("strengths", []),
            "attempts": len(attempts),
            "terminated": best_attempt.get("terminated", ""),
        })

    # Sort by prefix
    dataset.sort(key=lambda x: int(x["prefix"]) if x["prefix"].isdigit() else 999)
    return dataset


if __name__ == "__main__":
    data = build_dataset()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ wrote {OUT} with {len(data)} personas")
