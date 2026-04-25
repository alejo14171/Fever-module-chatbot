"""
Recommendation prompt — single-shot, pediatrician-brief.

Replaces the 3-separator state machine with one short message: assessment +
treatment + alarms + closing question. Targets ≤180 words.
"""

from datetime import date

from langchain_core.prompts import PromptTemplate


RECOMMENDATION_TEMPLATE = """\
Eres un PEDIATRA colombiano dando una recomendación corta por teléfono. Tono cálido, tuteas.

# PACIENTE
{{ patient_name }}, {{ age_display }}, {{ patient_weight_kg }} kg.
Temperatura: {% if "evaluación táctil" in temperature %}{{ temperature }}{% elif temperature in ["No medida", "desconocido", "no_medida"] %}NO se midió ({{ tactile_fever_assessment or "sin evaluación táctil" }}){% else %}{{ temperature }}°C ({{ thermometer_location }}){% endif %}.
Duración: {{ fever_duration_display }}.
Medicación previa: {{ medication_info }}.
Síntomas: estado general → {{ general_symptoms_display }}; respiratorio → {{ respiratory_symptoms_display }}; piel → {{ visual_alarm_signs_display }}.
Antecedentes: {{ medical_history_display }}. Vacunas: {{ vaccination_status }}.
Contexto fiebre: {{ fever_context }}.
{% if red_flags_display %}Signos detectados: {{ red_flags_display }}.{% endif %}

# DOSIS YA CALCULADAS POR EL SISTEMA (úsalas TAL CUAL si recomiendas medicar)
{% if not acetaminofen_dose.error %}Acetaminofén: {{ acetaminofen_dose.dose_ml_suspension }} ml de jarabe 160mg/5ml cada {{ acetaminofen_dose.interval_hours }} horas (máximo {{ acetaminofen_dose.max_daily_mg }} mg/día).{% else %}Acetaminofén: {{ acetaminofen_dose.warning }}{% endif %}
{% if ibuprofen_dose.contraindicated %}Ibuprofeno: NO en este paciente — {{ ibuprofen_dose.warning }}{% elif not ibuprofen_dose.error %}Ibuprofeno (alternativa): {{ ibuprofen_dose.dose_ml_suspension }} ml de jarabe 100mg/5ml cada {{ ibuprofen_dose.interval_hours }} horas.{% endif %}

# REGLAS DE FORMATO (CRÍTICAS — un mensaje corto, no un manual)
- Máximo 180 palabras EN TOTAL.
- 2 párrafos cortos + 3 viñetas máximo de signos de alarma + 1 frase de cierre con invitación a preguntar.
- Sin encabezados, sin emojis, sin disclaimers legales, sin "como pediatra...".
- Hablas como un médico real en consulta, no como ChatGPT. Frases concretas.
- NO saludes — esta es la continuación de la conversación, no es un mensaje nuevo.
- Si {{ patient_name }} es "el niño/a" o "desconocido", refiérete a él/ella como "tu hijo", "tu hija", "el peque" — NUNCA inventes un nombre.

# QUÉ DEBE INCLUIR
1. Frase de evaluación: si tiene fiebre real, si necesita evaluación presencial y cuándo (hoy mismo / 12-24h / observar en casa). Justifica brevemente con edad + duración.
2. Manejo concreto: si conviene antipirético, di la dosis EXACTA arriba calculada. Si no, di por qué (ej. <38°C no es fiebre, no toca medicar).
3. Tres signos de alarma específicos para este caso (no genéricos).
4. {% if fever_context == "trauma" %}Como hubo un golpe antes, menciona explícitamente vigilar somnolencia, vómitos repetidos, asimetría pupilar — y umbral bajo para urgencias.{% elif fever_context == "base_disease" %}Como tiene enfermedad de base, recuérdale contactar a su especialista de cabecera además del pediatra.{% elif fever_context == "post_vaccine" %}Como es post-vacunal, normaliza la fiebre las primeras 48-72h pero indica cuándo SÍ consultar.{% elif fever_context == "post_surgery" %}Como hubo cirugía reciente, advierte que cualquier fiebre tras cirugía requiere comunicar al cirujano.{% endif %}
5. Cierre: invitación corta a preguntar dudas.

Genera SÓLO el mensaje al padre/madre, sin meta-comentarios.
"""


prompt_template = PromptTemplate.from_template(
    RECOMMENDATION_TEMPLATE,
    template_format="jinja2",
    partial_variables={"today": date.today().strftime("%Y-%m-%d")},
)


def get_fever_duration_display(hours_str: str) -> str:
    try:
        hours = int(hours_str)
    except (ValueError, TypeError):
        return "duración no especificada"
    if hours < 24:
        return f"menos de un día ({hours}h)"
    if hours < 48:
        return "aproximadamente 1 día"
    if hours < 72:
        return "aproximadamente 2 días"
    if hours < 96:
        return "aproximadamente 3 días"
    days = hours // 24
    return f"aproximadamente {days} días"


def safe_display(value: str, default: str = "No especificado") -> str:
    if not value or value in {"desconocido", "", "0"}:
        return default
    return value


def calculate_acetaminofen_dose(weight_kg: str, age_months: str) -> dict:
    try:
        weight = float(weight_kg)
        age = int(age_months) if age_months and age_months != "desconocido" else 0
    except (ValueError, TypeError):
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "dose_ml_drops": None,
            "max_daily_mg": None,
            "interval_hours": 6,
            "warning": "No se pudo calcular la dosis. Peso o edad no disponible.",
            "error": True,
        }
    if weight < 2 or weight > 100:
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "dose_ml_drops": None,
            "max_daily_mg": None,
            "interval_hours": 6,
            "warning": "Peso fuera de rango esperado. Consultar con pediatra.",
            "error": True,
        }
    # Use 15 mg/kg per dose, but cap at the safe daily/dose limits.
    # Floor (not round) to never exceed 15 mg/kg.
    import math
    dose_mg = math.floor(weight * 15)
    max_daily_mg = math.floor(weight * 60)
    dose_ml_suspension = round(dose_mg / 32, 1)
    dose_ml_drops = round(dose_mg / 100, 1)
    warning = None
    if age < 3:
        warning = "⚠️ Menor de 3 meses: consultar dosis con pediatra antes de administrar."
    elif dose_mg > 500:
        warning = "⚠️ Dosis alta. Verificar peso y consultar con pediatra."
    return {
        "dose_mg": round(dose_mg, 1),
        "dose_ml_suspension": dose_ml_suspension,
        "dose_ml_drops": dose_ml_drops,
        "max_daily_mg": round(max_daily_mg, 1),
        "interval_hours": 6,
        "warning": warning,
        "error": False,
    }


def calculate_ibuprofen_dose(weight_kg: str, age_months: str) -> dict:
    try:
        weight = float(weight_kg)
        age = int(age_months) if age_months and age_months != "desconocido" else 0
    except (ValueError, TypeError):
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "max_daily_mg": None,
            "interval_hours": 8,
            "warning": "No se pudo calcular la dosis. Peso o edad no disponible.",
            "error": True,
            "contraindicated": False,
        }
    if age < 6:
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "max_daily_mg": None,
            "interval_hours": 8,
            "warning": "NO usar ibuprofeno en menores de 6 meses. Solo paracetamol.",
            "error": True,
            "contraindicated": True,
        }
    if weight < 2 or weight > 100:
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "max_daily_mg": None,
            "interval_hours": 8,
            "warning": "Peso fuera de rango esperado. Consultar con pediatra.",
            "error": True,
            "contraindicated": False,
        }
    dose_mg = weight * 10
    max_daily_mg = weight * 30
    dose_ml_suspension = round(dose_mg / 20, 1)
    return {
        "dose_mg": round(dose_mg, 1),
        "dose_ml_suspension": dose_ml_suspension,
        "max_daily_mg": round(max_daily_mg, 1),
        "interval_hours": 8,
        "warning": None,
        "error": False,
        "contraindicated": False,
    }
