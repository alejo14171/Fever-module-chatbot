"""
Receptor node — extracts structured clinical fields from the latest user turn.

Replaces the legacy regex parser with a Pydantic structured-output call so the
LLM cannot drift from the format. Sends only the last few messages to keep the
prompt compact (avoids the previous full-history bloat).
"""

from __future__ import annotations

import json
from datetime import datetime

from fever_routing.nodes.receptor.prompt import (
    SYSTEM_PROMPT,
    build_extraction_user_prompt,
)
from fever_routing.state import State
from fever_routing.utils import ModelFactory
from fever_routing.utils.extraction_schema import ExtractionResult
from fever_routing.utils.logging import debug_print


_LAST_N_MESSAGES = 6

_llm = ModelFactory.get_receptor_model()
try:
    _structured = _llm.with_structured_output(ExtractionResult)
except Exception:
    _structured = None


def calculate_age_in_months(birthdate_str: str) -> str:
    if not birthdate_str or birthdate_str.lower() in {"desconocido", "unknown", ""}:
        return ""
    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]
    birthdate = None
    for fmt in formats:
        try:
            birthdate = datetime.strptime(birthdate_str.strip(), fmt)
            break
        except ValueError:
            continue
    if birthdate is None:
        return ""
    today = datetime.now()
    months = (today.year - birthdate.year) * 12 + (today.month - birthdate.month)
    if today.day < birthdate.day:
        months -= 1
    if months < 0 or months > 240:
        return ""
    return str(months)


def calculate_birthdate_from_age(age_months_str: str) -> str:
    if not age_months_str or age_months_str.lower() in {"desconocido", "", "0"}:
        return ""
    try:
        age_months = int(age_months_str)
    except (ValueError, TypeError):
        return ""
    if age_months < 0 or age_months > 240:
        return ""
    today = datetime.now()
    birth_year = today.year - (age_months // 12)
    birth_month = today.month - (age_months % 12)
    if birth_month <= 0:
        birth_month += 12
        birth_year -= 1
    return f"15/{birth_month:02d}/{birth_year}"


def calculate_duration_from_datetime(fever_start_str: str) -> str:
    if not fever_start_str or fever_start_str in {"desconocido", ""}:
        return ""
    try:
        fever_start = datetime.strptime(fever_start_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return ""
    hours = int((datetime.now() - fever_start).total_seconds() / 3600)
    if 0 <= hours <= 480:
        return str(hours)
    return ""


def _apply_expected_fallbacks(
    state: State,
    extracted: dict,
    expected_fields: list[str],
    fallback_values: dict,
) -> dict:
    """If inquiry expected certain fields but the LLM didn't fill them, apply defaults.

    Only for fields that are not already present in the existing State."""
    filled = dict(extracted)
    for field in expected_fields:
        if field in extracted and extracted[field]:
            continue
        if state.get(field):
            continue
        fallback = fallback_values.get(field)
        if fallback:
            filled[field] = fallback
            debug_print(f"  ↩️ fallback {field}={fallback}")
    return filled


def receptor_node(state: State):
    """Extract structured updates from the latest user turn."""
    messages = state["messages"]
    new_state: State = {}

    if not messages:
        return new_state

    expected_fields = []
    fallback_values: dict = {}
    try:
        expected_fields = json.loads(state.get("expected_fields", "[]") or "[]")
    except json.JSONDecodeError:
        expected_fields = []
    try:
        fallback_values = json.loads(state.get("fallback_values", "{}") or "{}")
    except json.JSONDecodeError:
        fallback_values = {}

    extraction_hint = ""
    last_inquiry_question = state.get("last_inquiry_question", "")
    if expected_fields:
        debug_print(f"📌 expected_fields={expected_fields}")
        extraction_hint = f"Pregunta previa del asistente: {last_inquiry_question[:160]}"

    last_msgs = messages[-_LAST_N_MESSAGES:]
    user_prompt = build_extraction_user_prompt(
        state, last_msgs, expected_fields, extraction_hint
    )

    debug_print("📥 RECEPTOR — invocando LLM con structured output")
    try:
        if _structured is None:
            raise RuntimeError("Structured output not supported by current LLM")
        result: ExtractionResult = _structured.invoke(
            [("system", SYSTEM_PROMPT), ("user", user_prompt)]
        )
    except Exception as exc:
        debug_print(f"❌ Receptor LLM error: {exc}")
        return new_state

    if not result.update:
        debug_print("📭 Receptor: usuario no aportó info nueva (update=false)")
        if expected_fields:
            for field in expected_fields:
                if field not in state or not state.get(field):
                    fb = fallback_values.get(field)
                    if fb:
                        new_state[field] = fb
        return new_state

    extracted_updates = result.to_state_updates()
    debug_print(f"📥 Extraído: {list(extracted_updates.keys())}")

    if expected_fields:
        extracted_updates = _apply_expected_fallbacks(
            state, extracted_updates, expected_fields, fallback_values
        )

    for field, value in extracted_updates.items():
        new_state[field] = value

    if "patient_birthdate" in extracted_updates:
        age_months = calculate_age_in_months(extracted_updates["patient_birthdate"])
        if age_months:
            new_state["patient_age_months"] = age_months

    if (
        "patient_age_months" in extracted_updates
        and "patient_birthdate" not in extracted_updates
        and not state.get("patient_birthdate")
    ):
        bd = calculate_birthdate_from_age(extracted_updates["patient_age_months"])
        if bd:
            new_state["patient_birthdate"] = bd

    if "fever_start_datetime" in extracted_updates:
        duration = calculate_duration_from_datetime(extracted_updates["fever_start_datetime"])
        if duration:
            new_state["fever_duration_hours"] = duration

    return new_state
