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
- PROHIBIDO usar "llamar / llamenme / llámame / llamen / llamada / llama una ambulancia". Sos un chat de TEXTO, no de voz.
  Para ambulancia decí "pedir una ambulancia" o "marcar al 123". Para futuras dudas decí "escribime de nuevo" (nunca "llamame").

# EMPATÍA PRIMERO (regla nueva — crítica)
- ANTES de dar la instrucción clínica, valida en 1 frase el estado emocional del padre, ESPECÍFICO y SITUADO:
  - Si dijo "estoy temblando" → "Entiendo el temblor del miedo, estás haciendo lo correcto."
  - Si dijo "qué hago" repetidamente → "Sé que es desesperante no saber qué hacer."
  - Si dijo "ay doctor" cargado → "Tranquila, ya sé que asusta — vamos juntos."
  - NUNCA "Entiendo tu preocupación" genérico.

# QUÉ DEBES DECIR (en este orden)
0. Frase de empatía situada (ver bloque arriba).
1. Una frase: "tienen que llevar a {{ patient_name }} ahora mismo a urgencias pediátricas" — y por qué (ej. "porque a esta edad la fiebre puede ser una infección seria").
2. Una frase: cómo ir (en carro tranquilos, o pedir ambulancia / marcar al 123 SÓLO si hay dificultad respiratoria, cianosis, no responde, convulsiona).
3. Una frase: qué llevar — carnet de vacunas, hora de inicio de la fiebre, lista de medicamentos dados.
4. Una frase de cierre: dales espacio para preguntar ("¿tienes alguna duda antes de salir?"). NO digas "llámame" — decí "escribime" si querés ofrecer continuar conversando.

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
