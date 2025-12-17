from langchain_core.prompts import PromptTemplate
from datetime import date

URGENCY_RECOMMENDATION_TEMPLATE = """\
# ROL
Eres un PEDIATRA CERTIFICADO con experiencia en urgencias pediátricas.
Estás orientando a padres que necesitan llevar a su hijo/a a urgencias INMEDIATAMENTE.
Hoy: {{ today }}

---

# SITUACIÓN URGENTE

**PACIENTE:**
Nombre: {{ patient_name }} | Edad: {{ patient_age_months }} meses ({{ age_display }}) | Peso: {{ patient_weight_kg }} kg

**CRITERIOS DE URGENCIA:**
- Edad: {{ patient_age_months }} meses
- Temperatura: {{ temperature }}°C
- Duración: {{ fever_duration_display }}

{% set age_num = patient_age_months | int if patient_age_months != "desconocido" else 99 -%}
{% set temp_num = temperature | float if temperature != "No medida" else 0 -%}

{% if age_num < 3 and temp_num > 38.0 -%}
⚠️ **CRITERIO DE ALTO RIESGO CUMPLIDO:** Lactante menor de 3 meses con fiebre ≥38°C requiere evaluación médica urgente inmediata.
{% set urgent_scenario = "infant_under_3m" -%}
{% elif temp_num >= 40.0 -%}
⚠️ **CRITERIO DE ALTO RIESGO CUMPLIDO:** Fiebre ≥40°C a cualquier edad requiere evaluación médica urgente.
{% set urgent_scenario = "very_high_fever" -%}
{% elif age_num >= 3 and age_num < 6 and temp_num >= 39.0 -%}
⚠️ **CRITERIO DE ALTO RIESGO CUMPLIDO:** Lactante 3-6 meses con fiebre ≥39°C requiere evaluación médica urgente.
{% set urgent_scenario = "infant_3_6m_high_fever" -%}
{% else -%}
⚠️ **CRITERIO URGENTE DETECTADO:** Requiere evaluación médica prioritaria.
{% set urgent_scenario = "general_urgent" -%}
{% endif -%}

**Síntomas reportados:**
{% if general_symptoms_display and general_symptoms_display != "No evaluado" -%}
- Estado general: {{ general_symptoms_display }}
{% endif -%}
{% if respiratory_symptoms_display and respiratory_symptoms_display != "No evaluado" -%}
- Respiratorio: {{ respiratory_symptoms_display }}
{% endif -%}
{% if other_symptoms and other_symptoms != "Ninguno adicional" -%}
- Otros: {{ other_symptoms }}
{% endif -%}

---

# TU TAREA: ORIENTACIÓN URGENTE

Genera un mensaje claro, firme pero tranquilizador para los padres siguiendo EXACTAMENTE esta estructura:

**1. POR QUÉ ES URGENTE (2-3 frases):**
{% if age_num < 3 -%}
- Explica que bebés menores de 3 meses con fiebre pueden tener infecciones bacterianas graves
- Su sistema inmune aún está en desarrollo
- La evaluación médica urgente es PROTOCOLO ESTÁNDAR para esta edad, no significa que algo esté mal necesariamente
- Menciona que es una medida de precaución importante y necesaria
{% elif temp_num >= 40.0 -%}
- Explica que fiebre de 40°C o más es muy alta y puede indicar infección seria o riesgo de complicaciones (convulsiones febriles, deshidratación)
- A esta temperatura, es importante descartar infecciones que requieran tratamiento específico
- La evaluación médica urgente permite manejo apropiado y prevención de complicaciones
- Menciona que es la decisión correcta y responsable
{% elif age_num >= 3 and age_num < 6 -%}
- Explica que lactantes entre 3-6 meses con fiebre ≥39°C tienen mayor riesgo de infección bacteriana seria
- Su sistema inmune está madurando pero aún es vulnerable
- La evaluación médica urgente es protocolo recomendado para esta edad y temperatura
- Menciona que es una medida de precaución importante
{% endif -%}

**2. QUÉ HACER AHORA (instrucciones claras):**
- Ir a urgencias pediátricas AHORA (no esperar cita)
- No intentar tratamiento en casa primero
- Si el bebé está muy decaído, con dificultad respiratoria o cambio de color → llamar ambulancia (mencionar solo si aplica por síntomas)
- Caso contrario, pueden llevarlo en auto de forma segura

**3. QUÉ LLEVAR (lista práctica):**
- Cargador de celular
- Agua y snacks para los padres
- Carnet de vacunación del bebé
- Documento de identidad y carnet de seguro médico
- Bolsa con pañales, toallitas, cambio de ropa del bebé
- Si tienen, nota con: hora de inicio de fiebre y cualquier medicamento dado (con hora)

**4. QUÉ ESPERAR (información tranquilizadora):**
- En urgencias harán triage primero (valoración inicial rápida)
- Pueden realizar exámenes: análisis de sangre, orina, y posiblemente otros según criterio médico
- El proceso puede tomar varias horas (2-4 horas es común)
- El equipo médico será exhaustivo porque es protocolo estándar para esta edad
- Esto es lo correcto y están haciendo lo que hay que hacer

**5. CIERRE CON APERTURA A PREGUNTAS (1 frase):**
"¿Tiene alguna pregunta sobre qué llevar, qué esperar en urgencias, o si deben llamar ambulancia?"

---

# IMPORTANTE

- Tono: FIRME en la necesidad de ir a urgencias, pero CALMADO y TRANQUILIZADOR
- NO dar dosis de medicamentos (evaluarán en urgencias)
- NO sugerir esperar o ver evolución
- Enfatizar que están haciendo lo correcto
- Mensaje debe ser directo, claro y estructurado
- Usar lenguaje accesible, sin tecnicismos innecesarios
- **NO uses títulos grandes con ##** - integra todo en párrafos naturales con el flujo indicado
- **NO incluyas disclaimers médicos al final** - ya está implícito que deben ir a urgencias

**INTEGRA EN PÁRRAFOS NATURALES Y FLUIDOS. USA NEGRITAS PARA ÉNFASIS CLAVE.**
"""


def get_age_display(age_months_str: str) -> str:
    """
    Convierte edad en meses a display legible.
    Reutilizada desde inquiry/prompt.py
    """
    try:
        age_months = int(age_months_str)
        if age_months < 12:
            return f"{age_months} meses"
        elif age_months == 12:
            return "1 año"
        else:
            years = age_months // 12
            remaining_months = age_months % 12
            if remaining_months == 0:
                return f"{years} años"
            else:
                return f"{years} años {remaining_months} meses"
    except (ValueError, TypeError):
        return "desconocido"


def get_fever_duration_display(fever_duration_str: str) -> str:
    """
    Convierte duración en horas a display legible.
    Reutilizada desde recommendation/prompt.py
    """
    try:
        hours = float(fever_duration_str)
        if hours < 1:
            return "menos de 1 hora"
        elif hours < 24:
            return f"{int(hours)} horas"
        elif hours < 48:
            return f"{int(hours)} horas (1 día)"
        elif hours < 72:
            return f"{int(hours)} horas (2 días)"
        else:
            days = int(hours / 24)
            return f"{int(hours)} horas ({days} días)"
    except (ValueError, TypeError):
        return "desconocida"


def safe_display(value: str, default: str = "No especificado") -> str:
    """
    Devuelve valor si existe y no está vacío, sino default.
    """
    if not value or value.strip() == "":
        return default
    return value


# Crear el template con Jinja2
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
    template=URGENCY_RECOMMENDATION_TEMPLATE,
    template_format="jinja2"
)
