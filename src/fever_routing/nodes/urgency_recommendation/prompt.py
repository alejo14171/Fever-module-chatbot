"""
Urgency prompt — short, firm, calm. ≤120 words.
"""

from langchain_core.prompts import PromptTemplate


URGENCY_TEMPLATE = """\
Eres un PEDIATRA colombiano dándole instrucciones URGENTES a una mamá/papá por teléfono.

# CASO
{{ patient_name }}, {{ age_display }}, {{ patient_weight_kg }} kg.
Temperatura: {{ temperature }}°C. Duración: {{ fever_duration_display }}.
Síntomas: {{ general_symptoms_display }}. Respiratorio: {{ respiratory_symptoms_display }}. Otros: {{ other_symptoms }}.

# REGLAS DE FORMATO (CRÍTICAS)
- Máximo 120 palabras EN TOTAL.
- 4 frases concretas, sin viñetas largas, sin emojis, sin disclaimers.
- Tono firme pero calmado. Hablas tuteando, como pediatra real.

# QUÉ DEBES DECIR (en este orden, en frases cortas)
1. Una frase: "tienen que llevar a {{ patient_name }} ahora mismo a urgencias pediátricas" — y por qué (ej. "porque a esta edad la fiebre puede ser una infección seria").
2. Una frase: cómo ir (en carro tranquilos, o ambulancia SÓLO si hay dificultad respiratoria, cianosis, no responde, convulsiona).
3. Una frase: qué llevar — carnet de vacunas, hora de inicio de la fiebre, lista de medicamentos dados.
4. Una frase de cierre: tranquilízalos, dales el espacio para preguntar ("¿tienes alguna duda antes de salir?").

NO recetes medicamentos. NO digas que esperen. Genera SÓLO el mensaje al padre, sin meta-comentarios."""


def get_age_display(age_months_str: str) -> str:
    try:
        m = int(age_months_str)
    except (ValueError, TypeError):
        return "edad no especificada"
    if m <= 0:
        return "edad no especificada"
    if m < 12:
        return f"{m} {'mes' if m == 1 else 'meses'}"
    years = m // 12
    rem = m % 12
    if rem == 0:
        return f"{years} {'año' if years == 1 else 'años'}"
    return f"{years} año{'s' if years > 1 else ''} {rem} mes{'es' if rem > 1 else ''}"


def get_fever_duration_display(fever_duration_str: str) -> str:
    try:
        hours = float(fever_duration_str)
    except (ValueError, TypeError):
        return "desconocida"
    if hours < 1:
        return "menos de 1 hora"
    if hours < 24:
        return f"{int(hours)} horas"
    if hours < 48:
        return f"{int(hours)} horas (1 día)"
    if hours < 72:
        return f"{int(hours)} horas (2 días)"
    days = int(hours / 24)
    return f"{int(hours)} horas ({days} días)"


def safe_display(value: str, default: str = "No especificado") -> str:
    if not value or not str(value).strip() or str(value).strip() in {"desconocido", "0"}:
        return default
    return value


prompt_template = PromptTemplate(
    input_variables=[
        "today",
        "patient_name",
        "patient_age_months",
        "age_display",
        "patient_weight_kg",
        "temperature",
        "fever_duration_display",
        "general_symptoms_display",
        "respiratory_symptoms_display",
        "other_symptoms",
    ],
    template=URGENCY_TEMPLATE,
    template_format="jinja2",
)
