"""
Pydantic schema for structured extraction in the Receptor node.

The receptor LLM fills this schema instead of emitting free text. All fields are
optional — only set what the latest user turn actually conveys. Empty / unknown
fields stay as None and are NOT written to State, preserving prior values.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


FeverContext = Literal[
    "primary",         # straightforward fever, no obvious secondary cause
    "trauma",          # recent head/body trauma, fall, accident
    "base_disease",    # immunocompromise, oncology, chronic illness, congenital
    "post_vaccine",    # fever within 72h of vaccination
    "post_surgery",    # fever after recent surgery / procedure
    "unknown",         # not enough info yet to decide
]


class ExtractionResult(BaseModel):
    """Structured output from the receptor LLM."""

    update: bool = Field(
        default=True,
        description=(
            "False ONLY when the user message contains absolutely no new clinical "
            "information (e.g. plain greeting, gratitude). True otherwise."
        ),
    )

    patient_name: Optional[str] = Field(default=None, description="Child's name if mentioned.")
    patient_birthdate: Optional[str] = Field(
        default=None,
        description="DD/MM/YYYY or YYYY-MM-DD if user gave a birthdate.",
    )
    patient_age_months: Optional[str] = Field(
        default=None,
        description=(
            "Age in months as integer string. Convert from years/months phrasings "
            "(e.g. '3 años' → '36'). Leave blank if not provided."
        ),
    )
    patient_weight_kg: Optional[str] = Field(default=None, description="Weight in kg, e.g. '12' or '15.5'.")
    parent_phone: Optional[str] = Field(default=None)

    temperature: Optional[str] = Field(
        default=None,
        description=(
            "Temperature in °C as decimal string (e.g. '38.5'). Use 'no_medida' "
            "ONLY if user explicitly says they could not measure."
        ),
    )
    fever_start_datetime: Optional[str] = Field(
        default=None,
        description=(
            "ISO 'YYYY-MM-DD HH:MM' if user gave a specific start moment "
            "(e.g. 'desde el martes a las 10pm'). Otherwise leave blank."
        ),
    )
    fever_duration_hours: Optional[str] = Field(
        default=None,
        description="Hours of fever as integer string when user gives duration directly ('hace 2 días' → '48').",
    )
    thermometer_location: Optional[str] = Field(
        default=None,
        description="One of: axilar, rectal, oral, frontal, oido.",
    )
    has_thermometer: Optional[str] = Field(default=None, description="'si', 'no', or 'desconocido'.")
    can_get_thermometer: Optional[str] = Field(default=None, description="'si', 'no', or 'desconocido'.")

    tactile_assessment_given: Optional[str] = Field(default=None, description="'si' if a tactile assessment was reported.")
    tactile_fever_assessment: Optional[str] = Field(
        default=None,
        description="'febricula', 'fiebre_moderada', 'fiebre_alta' from tactile description.",
    )

    home_measures_taken: Optional[str] = Field(default=None)
    medication_given: Optional[str] = Field(
        default=None,
        description=(
            "Free-text description of meds and timing, or literally 'no' if the user denies medication."
        ),
    )
    recent_antibiotics: Optional[str] = Field(default=None)

    general_symptoms: Optional[str] = Field(
        default=None,
        description=(
            "Comma-separated key:value pairs (rechaza_alimento, vomitos, cefalea, "
            "decaido, juega, irritable). Use 'si'/'no'."
        ),
    )
    respiratory_symptoms: Optional[str] = Field(
        default=None,
        description="Key:value pairs (dificultad_respirar, tos, mocos, tipo_tos).",
    )
    visual_alarm_signs: Optional[str] = Field(
        default=None,
        description=(
            "Key:value pairs (palido, cianosis, mal_color, rash, manchas, "
            "rash_no_blanqueable, petequias). Use 'si'/'no'."
        ),
    )
    hydration_status: Optional[str] = Field(default=None)
    feeding_status: Optional[str] = Field(default=None)
    other_symptoms: Optional[str] = Field(
        default=None,
        description=(
            "Free-text additional symptoms. CRITICAL: include red-flag words verbatim "
            "(convulsion, rigidez_nuca, fontanela_abombada, no_responde, "
            "letargo_severo, sangrado, ictericia, oliguria, vomito_sangre)."
        ),
    )

    epidemiological_context: Optional[str] = Field(default=None)
    vaccination_status: Optional[str] = Field(default=None, description="completo, incompleto, desconocido.")
    medical_history: Optional[str] = Field(
        default=None,
        description=(
            "Use 'no' if user denies conditions. Otherwise list them "
            "(e.g. 'leucemia_quimio, cardiopatia_congenita, asma')."
        ),
    )

    fever_context: Optional[FeverContext] = Field(
        default=None,
        description=(
            "Set ONLY when there is BOTH (a) a confirmed fever (mentioned by parent "
            "or measured) AND (b) a contextual modifier explaining it. Otherwise leave null.\n"
            "- 'primary': fever exists, no other contextual cause.\n"
            "- 'trauma': fever exists AND recent fall/accident BEFORE the fever.\n"
            "- 'base_disease': fever exists AND child has oncology / immunocompromise / "
            "cardiac / chronic illness.\n"
            "- 'post_vaccine': fever exists AND started within 72h of a vaccine.\n"
            "- 'post_surgery': fever exists AND followed a recent procedure.\n"
            "- 'unknown': fever exists but cause unclear yet.\n"
            "DO NOT set this if the parent only mentioned an event (golpe, caída, "
            "leucemia, vacuna) without also mentioning fever or hot temperature."
        ),
    )

    def to_state_updates(self) -> dict:
        """Convert non-None fields to a dict ready to merge into LangGraph State."""
        updates: dict = {}
        for field_name, value in self.model_dump(exclude_none=True).items():
            if field_name == "update":
                continue
            if isinstance(value, str):
                stripped = value.strip()
                if not stripped or stripped.lower() in {"none", "null", "n/a", "no_aplica"}:
                    continue
                updates[field_name] = stripped
            elif value is not None:
                updates[field_name] = str(value)
        return updates
