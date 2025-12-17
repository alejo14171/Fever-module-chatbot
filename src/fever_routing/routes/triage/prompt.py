from langchain_core.prompts import PromptTemplate

TRIAGE_TEMPLATE = """\
Eres un asistente médico de IA que determina el siguiente paso en el triaje de fiebre pediátrica.

INFORMACIÓN DEL PACIENTE RECOPILADA:
{% if patient_name and patient_name != "" or patient_name != "<UNKNOWN>" -%}
✓ Nombre: {{ patient_name }}
{% else -%}
✗ Nombre: No disponible
{% endif -%}
{% if patient_age_months and patient_age_months != "0" or patient_age_months != "<UNKNOWN>" -%}
✓ Edad: {{ patient_age_months }} meses
{% else -%}
✗ Edad: No disponible
{% endif -%}
{% if parent_phone and parent_phone != "" or parent_phone != "<UNKNOWN>" -%}
✓ Teléfono: {{ parent_phone }}
{% else -%}
✗ Teléfono: No disponible
{% endif -%}
{% if temperature and temperature != "0" or temperature != "<UNKNOWN>" -%}
✓ Temperatura: {{ temperature }}°C
{% else -%}
✗ Temperatura: No disponible
{% endif %}

INFORMACIÓN CLÍNICA ADICIONAL EN EL HISTORIAL:
{% if has_clinical_info -%}
El historial de mensajes contiene información clínica adicional sobre síntomas.
{% else -%}
El historial NO contiene información clínica detallada sobre síntomas.
{% endif %}

OPCIONES:
- inquiry: Si el caso requiere hacer preguntas detalladas sobre síntomas para hacer un triaje completo (la mayoría de los casos). Usa esta opción cuando solo tenemos información básica.
- recommendation: SOLO si la información inicial ya es suficiente para dar una recomendación directa (casos muy claros o cuando el padre/madre ya proporcionó información clínica completa en el mensaje inicial).

CRITERIOS PARA DECIDIR:
- inquiry: Elegir cuando:
  * Solo tenemos datos básicos (nombre, edad, teléfono, posiblemente temperatura)
  * No hay información sobre síntomas específicos (convulsiones, dificultad respiratoria, erupciones, etc.)
  * No sabemos la duración de la fiebre
  * No conocemos el comportamiento del niño (irritabilidad, somnolencia, hidratación)
  * Falta información sobre medicamentos administrados

- recommendation: Elegir SOLO cuando:
  * Ya tenemos toda la información necesaria para dar una recomendación directa.
  * No hay necesidad de hacer preguntas adicionales.

"""

prompt_template = PromptTemplate.from_template(
    TRIAGE_TEMPLATE, 
    template_format="jinja2"
)