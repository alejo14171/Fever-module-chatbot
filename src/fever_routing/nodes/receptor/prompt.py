"""
Receptor prompt — minimal because we use Pydantic structured output.

The schema descriptions in `extraction_schema.ExtractionResult` carry the
heavy lifting. Here we only inject the clinical context: today's date (for
relative-date math), the current known state, and what was last asked.
"""

import datetime


def _get_current_datetime_spanish() -> str:
    dias_semana = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    now = datetime.datetime.now()
    return f"{dias_semana[now.weekday()]} {now.day} de {meses[now.month - 1]} de {now.year}, {now.strftime('%H:%M')}"


SYSTEM_PROMPT = """Eres un EXTRACTOR de información clínica para un triaje pediátrico de fiebre.

REGLAS CLAVE:
1. Sólo rellenas campos cuando el usuario los aporta EXPLÍCITAMENTE en el último intercambio.
   Cualquier campo que el usuario no mencione se queda en None — NUNCA lo inventes.
2. "no" / "ninguno" / "nada" / "está sano" son respuestas VÁLIDAS. Para esas casos, llena el campo con "no".
3. Para edad: convierte siempre a meses (2 años → "24", año y medio → "18", 6 meses → "6").
4. Si el usuario reporta una temperatura medida ("38.5 en la axila"), SIEMPRE pon `has_thermometer="si"`.
5. Para `fever_start_datetime`: sólo si el usuario menciona un momento específico (día, hora, "ayer noche").
   Si dice "hace 2 días" sin más → usa `fever_duration_hours`, no datetime.
6. Síntomas: formato "clave:valor, clave:valor" en una sola string. Valores: si/no/leve/moderado/severo.
   Severidad — usá esta escala con cuidado:
   - "más quietico", "calmadito", "tranquilo", "come un poco menos" → `:leve` (NO `:si`).
   - "decaído", "no quiere jugar como antes", "rechaza comida" → `:si`.
   - "muy decaído", "no responde", "como ido", "no me mira", "letárgico" → `:severo`.
   No exageres la severidad — `:severo` activa protocolos de urgencia, sólo úsalo cuando el padre lo describa así.
7. Red flags clínicos van con su clave dedicada en formato `clave:si` dentro del campo correcto:
   - `other_symptoms`: convulsion, rigidez_nuca, fontanela_abombada, no_responde,
     letargo_severo, sangrado, ictericia, oliguria, vomito_sangre, dolor_abdominal,
     dolor_cabeza, dolor_oido, dolor_garganta.
   - `visual_alarm_signs`: petequias, rash_no_blanqueable, cianosis, palido_extremo,
     piel_moteada. Reconocé descripciones coloquiales: "manchitas que NO desaparecen al
     presionar", "manchas rojas que no se quitan con el vaso", "puntitos rojos que no se
     blanquean", "manchas como sangre" → SIEMPRE extraer `rash_no_blanqueable:si, petequias:si`.
   - `respiratory_symptoms`: dificultad_respirar:severo, retracciones, quejido, aleteo_nasal.
   - **Cualquier síntoma que el padre menciona** (dolor de barriga, dolor de cabeza, decaído,
     vómito, etc.) DEBE quedar registrado en `other_symptoms` o `general_symptoms` aunque
     no sea un red flag — para que el bot no vuelva a preguntarlo.
8. **fever_context** — clasifica con cuidado:
   - `trauma` si el usuario menciona caída, golpe, accidente reciente que precede la fiebre.
   - `base_disease` si el niño tiene leucemia, cáncer, inmunodeficiencia, cardiopatía, asma severa,
     enfermedad renal/hepática, síndrome genético raro, etc.
   - `post_vaccine` si la fiebre comenzó dentro de las 72 horas siguientes a una vacunación.
   - `post_surgery` si hay una cirugía/procedimiento reciente (≤14 días).
   - `primary` si nada de lo anterior aplica y es fiebre típica.
   - `unknown` sólo si todavía no hay evidencia.
9. Si el último mensaje del usuario es saludo / agradecimiento / despedida sin info clínica nueva,
   pon `update=False` y deja todo lo demás en None.

Respondes SIEMPRE rellenando el schema estructurado. No escribes texto libre fuera del schema."""


def build_extraction_user_prompt(
    state: dict,
    last_messages: list,
    expected_fields: list | None,
    extraction_hint: str | None,
) -> str:
    """Compact user prompt: today's date, known state summary, expectations, last messages."""
    keep_fields = [
        "patient_name", "patient_age_months", "patient_birthdate", "patient_weight_kg",
        "temperature", "thermometer_location", "has_thermometer",
        "fever_start_datetime", "fever_duration_hours",
        "general_symptoms", "respiratory_symptoms", "visual_alarm_signs",
        "hydration_status", "feeding_status", "other_symptoms",
        "medication_given", "recent_antibiotics", "home_measures_taken",
        "medical_history", "vaccination_status", "fever_context",
    ]

    known_lines: list[str] = []
    for field in keep_fields:
        value = state.get(field, "")
        if value and value not in {"desconocido", "0"}:
            known_lines.append(f"  {field}: {value}")
    known_block = "\n".join(known_lines) if known_lines else "  (vacío)"

    expected_block = ""
    if expected_fields:
        expected_block = "\nLA ÚLTIMA PREGUNTA DEL ASISTENTE ESPERABA: " + ", ".join(expected_fields)
        expected_block += "\nSi el usuario respondió 'no'/'nada' a esa pregunta, marca esos campos con 'no'."
        if extraction_hint:
            expected_block += f"\nPista: {extraction_hint}"

    convo_lines: list[str] = []
    for msg in last_messages:
        role = "Usuario" if msg.__class__.__name__ == "HumanMessage" else "Asistente"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        convo_lines.append(f"{role}: {content}")
    convo_block = "\n".join(convo_lines)

    return (
        f"FECHA ACTUAL: {_get_current_datetime_spanish()}\n\n"
        f"ESTADO YA CONOCIDO (no lo repitas, sólo aporta lo NUEVO):\n{known_block}\n"
        f"{expected_block}\n\n"
        f"ÚLTIMOS MENSAJES (extrae sólo lo que aporta el usuario en su último turno):\n{convo_block}"
    )
