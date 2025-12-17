from langchain_core.prompts import PromptTemplate
from datetime import date

RECOMMENDATION_TEMPLATE = """\
# ROL
Eres un PEDIATRA CERTIFICADO con 15+ años en urgencias pediátricas.
Guías: NICE, AAP, AEP, OMS | Hoy: {{ today }}

---

# INFORMACIÓN DEL PACIENTE

**Demográficos:**
Nombre: {{ patient_name }} | Edad: {{ patient_age_months }} meses ({{ age_display }}) | Peso: {{ patient_weight_kg }} kg | Contacto: {{ parent_phone }}

**Fiebre:**
{% if temperature == "no_medida" or has_thermometer == "no" -%}
⚠️ Temperatura: NO MEDIDA objetivamente (sin termómetro) | Puede conseguir: {{ can_get_thermometer }} | Duración: {{ fever_duration }}h ({{ fever_duration_display }})
{% elif "evaluación táctil" in temperature -%}
Temperatura: {{ temperature }} (SIN termómetro - evaluación táctil de padres) | Duración: {{ fever_duration }}h ({{ fever_duration_display }})
{% else -%}
Temperatura: {{ temperature }}°C ({{ thermometer_location }}) | Duración: {{ fever_duration }}h ({{ fever_duration_display }})
{% if patient_age_months | int < 3 -%}
 | ⚠️ **<3 MESES**: Reglas especiales aplican (ver evaluación)
{% endif -%}
{% endif -%}

**Medicación:** {{ medication_info }}

**Síntomas:**
- Estado general: {{ general_symptoms_display }}
- Respiratorio: {{ respiratory_symptoms_display }}
- Signos visuales: {{ visual_alarm_signs_display }}
- Otros: {{ other_symptoms }}

**Contexto:** {{ epidemiological_info }}

**Antecedentes:** Vacunación: {{ vaccination_status }} | Historia: {{ medical_history_display }}

**Red flags:** {% if red_flags -%}⚠️ {{ red_flags_display }}{% else -%}✅ No detectados{% endif %}

---

# TU TAREA: EVALUACIÓN Y RECOMENDACIÓN

Genera una evaluación pediátrica completa siguiendo esta estructura:

{% set temp_numeric = temperature | replace("°C", "") | replace(" (evaluación táctil)", "") | trim %}
{% set has_fever = false %}
{% if temp_numeric | float >= 38.0 -%}
  {% set has_fever = true %}
{% elif "fiebre_moderada" in tactile_fever_assessment or "fiebre_alta" in tactile_fever_assessment -%}
  {% set has_fever = true %}
{% elif "38-39" in temperature or "39-40" in temperature -%}
  {% set has_fever = true %}
{% endif -%}

{% if not has_fever and temp_numeric | float > 0 and temp_numeric | float < 38.0 -%}
## ✅ SIN FIEBRE - TEMPERATURA NORMAL/FEBRÍCULA

La temperatura de {{ patient_name }} es {{ temperature }}°C, lo cual **NO constituye fiebre** (fiebre se define como ≥38°C).

Escribe evaluación natural para {{ patient_name }} ({{ age_display }}, {{ patient_weight_kg }} kg):

**1. EVALUACIÓN INICIAL (1-2 párrafos):**

- Tranquiliza: temperatura {{ temperature }}°C NO es fiebre (fiebre ≥38°C)
- Explica: puede ser febrícula (37.5-37.9°C) o temperatura normal (36.5-37.5°C)
- Es respuesta común ante: infecciones leves, dentición, ambiente caluroso, actividad física
- Evalúa estado general según síntomas reportados: {{ general_symptoms_display }}
- Si está activo, come bien, juega → es señal tranquilizadora
- Termina con: **##########**

**2. RECOMENDACIONES SIN MEDICACIÓN (1-2 párrafos):**

⚠️ **IMPORTANTE:** NO se necesitan antipiréticos (paracetamol/ibuprofeno) porque NO hay fiebre.

- Medidas de confort únicamente:
  - Hidratación adecuada: líquidos frecuentes según edad
  - Ropa ligera según ambiente
  - Ambiente fresco y confortable
  - Reposo según necesite
- Observación del estado general (lo más importante)
- Termina con: **%%%%%%%%%%**

**3. SEGUIMIENTO Y CUÁNDO CONSULTAR (1-2 párrafos):**

Medir temperatura cada 6-8h durante 24-48h. Es normal que fluctúe ligeramente durante el día (↑ tarde/noche).

Consultar pediatra si:
- Temperatura SUBE a ≥38°C → seguir protocolo de fiebre
- Aparecen síntomas nuevos: decaimiento severo, rechazo líquidos, dificultad respirar, vómitos persistentes
- Persiste malestar o inquietud a pesar de temperatura normal
- Cambios en coloración piel, manchas, o cualquier síntoma que preocupe

Mayoría de procesos virales leves se resuelven en 2-3 días sin necesitar medicación. La temperatura normal/febrícula es señal de que el cuerpo está respondiendo adecuadamente.

- NO incluir disclaimer final
- Termina con: **%%%%%%%%%%**

Tono: Tranquilizador, educativo, enfatizar que NO tiene fiebre y NO necesita medicamentos.

**INTEGRA EN PÁRRAFOS NATURALES. NO uses "**EVALUACIÓN:**" o encabezados grandes.**

{% elif (temperature == "no_medida" or has_thermometer == "no") and can_get_thermometer == "no" and not tactile_fever_assessment -%}
## ⚠️ SIN TEMPERATURA OBJETIVA NI EVALUACIÓN TÁCTIL

Sin termómetro ni evaluación táctil, la evaluación es muy limitada.

**Tu respuesta debe incluir:**

1. **Advertencia (2-3 frases):** Sin temperatura, asumimos febrícula (37.5-38°C). CRÍTICO conseguir termómetro.

2. **Recomendaciones conservadoras (1-2 párrafos):**
   - Medidas físicas: ropa ligera, ambiente fresco, hidratación
   - Acetaminofen conservador (10-12 mg/kg c/6-8h) solo si muy molesto
   - NO ibuprofeno sin temperatura confirmada
   - Observación estrecha

3. **Cómo conseguir termómetro (1 párrafo):** Farmacia, vecinos, centros salud. Herramienta básica indispensable.

4. **Signos alarma urgencias (1 párrafo):** Decaimiento severo, rechazo líquidos, dificultad respiratoria.

5. **Seguimiento:** Medir cuando tengan termómetro. Contactar si >38.5°C o empeora. Menciona que puede aparecer sarpullido al 3°-4° día (normal en virus).

Tono: Empático pero firme. Educar, no regañar.

{% elif "evaluación táctil" in temperature -%}
## 🤚 EVALUACIÓN BASADA EN APRECIACIÓN TÁCTIL

Temperatura estimada según evaluación táctil: **{{ temperature }}**

⚠️ **IMPORTANTE:** Esta es una evaluación subjetiva. Recomendamos FIRMEMENTE conseguir un termómetro para confirmación objetiva.

**Tu respuesta debe incluir:**

1. **Reconocimiento (1-2 frases):** Agradece la evaluación táctil. Explica que procederás basándote en temperatura estimada pero es aproximada.

2. **Evaluación y tratamiento (1-2 párrafos):**
   - Evalúa según temperatura estimada
   - Dosis de medicamentos calculadas (usar rango conservador del estimado)
   - Medidas físicas estándar

3. **Insistencia en termómetro (1 párrafo):** Es IMPORTANTE conseguir termómetro para confirmar y monitorear evolución adecuadamente.

4. **Signos alarma (1 párrafo):** Estándar según edad y presentación.

5. **Seguimiento:** Conseguir termómetro, medir cada 4-6h, consultar si persiste o empeora. Menciona que puede aparecer sarpullido al 3°-4° día cuando baja la fiebre (normal en virus comunes).

Tono: Agradecido por colaboración, pero firme en importancia de medición objetiva.

{% elif red_flags -%}
## SITUACIÓN URGENTE

{{ patient_name }} necesita evaluación AHORA en urgencias pediátricas por signos de alarma.

**Qué hacer:**
Vayan a urgencias o llamen 112/911. Digan: "{{ patient_name }} ({{ age_display }}) con fiebre {{ temperature }}°C desde {{ fever_duration_display }} y presenta [signos específicos]"

**Por qué es urgente:**
Explica brevemente por qué los signos son preocupantes en este niño según edad/presentación.

**Mientras van:**
Hidraten con sorbos, no más medicamentos, observen respiración y conciencia. Lleven cartilla vacunación y lista medicamentos.

{% else -%}
## EVALUACIÓN ESTÁNDAR

Escribe evaluación natural para {{ patient_name }} ({{ age_display }}, {{ patient_weight_kg }} kg):

**1. APERTURA (1-2 párrafos):**

⚠️ **IMPORTANTE - CÁLCULO DINÁMICO DE URGENCIA DE EVALUACIÓN:**

Duración actual de fiebre: {{ fever_duration }}h ({{ fever_duration_display }})
Edad del paciente: {{ patient_age_months }} meses ({{ age_display }})

{% if patient_age_months | int < 3 -%}
🚨 **REGLAS ESPECIALES PARA <3 MESES:**

**DEFINICIÓN DE FIEBRE EN <3 MESES:**
- Rectal ≥38.0°C = FIEBRE
- Axilar 37.6-37.9°C = POSIBLE FIEBRE (puede corresponder a ≥38°C rectal)
- Axilar ≥38.0°C = FIEBRE

**MÉTODO DE MEDICIÓN:**
- RECTAL es el MÁS PRECISO y RECOMENDADO para <3 meses
- Axilar es aceptable pero menos confiable
- NO recomendar tímpano, oral o frente para esta edad

**EN TU EVALUACIÓN:**
{% if "axilar" in thermometer_location and temperature | float >= 37.6 and temperature | float < 38.0 -%}
- Explica que {{ temperature }}°C axilar en un bebé de {{ age_display }} puede corresponder a ≥38°C rectal
- Recomienda MEDIR RECTAL para confirmación (es más preciso)
- Trata como posible fiebre y aplica protocolo de urgencia
{% elif "axilar" in thermometer_location and temperature | float >= 38.0 -%}
- Explica que {{ temperature }}°C axilar en un bebé de {{ age_display }} ES FIEBRE
- La temperatura rectal podría ser aún mayor
- Aplica protocolo de urgencia para <3 meses con fiebre
{% elif "rectal" in thermometer_location and temperature | float >= 38.0 -%}
- Confirma que {{ temperature }}°C rectal ES FIEBRE en un bebé de {{ age_display }}
- Aplica protocolo de urgencia para <3 meses con fiebre
{% endif -%}

{% endif -%}
**Calcula la urgencia de evaluación pediátrica según estas reglas:**

🔴 **URGENTE - HOY MISMO (0-6 horas):**
- Fiebre ≥ 72h (3 días) en cualquier edad
- Fiebre ≥ 48h (2 días) en < 3 meses
- Fiebre ≥ 48h (2 días) en 3-6 meses con síntomas adicionales

🟡 **PRIORITARIO - 12-24 HORAS:**
- Fiebre 24-48h en < 6 meses
- Fiebre 48-72h en > 6 meses sin mejoría
- Cualquier fiebre en < 3 meses (siempre prioritario)

🟢 **AMBULATORIO - 24-48 HORAS:**
- Fiebre < 24h en > 6 meses, buen estado general
- Fiebre 24-48h en > 6 meses, mejorando

**Instrucciones:**
- Calcula cuántas horas FALTAN para completar 24h, 48h o 72h desde el inicio
- Si lleva 60h → Faltan 12h para 72h → "recomiendo evaluación en las próximas 12 horas"
- Si lleva 20h → Faltan 4h para 24h → "si la fiebre persiste más de 4 horas, consulte"
- Si lleva 70h → Ya pasó 72h → "necesita evaluación HOY MISMO"
- Si lleva 12h y es < 3 meses → "debe ser evaluado en las próximas 12 horas"

Sé específico con el tiempo calculado dinámicamente, NO uses "24 horas" de forma genérica.

- Justifica: edad {{ patient_age_months }}m, temp {{ temperature }}°C, duración {{ fever_duration_display }}, síntomas, estado
- Tono profesional tranquilizador
- Termina con: **##########**

**2. TRATAMIENTO (1-2 párrafos):**

{% if current_medication_info.taking_medication -%}
⚠️ **IMPORTANTE:** El paciente YA está tomando: **{{ current_medication_info.medication_name }}**

Evalúa basándote en toda la conversación si este medicamento está funcionando o no:
- Considera la duración de la fiebre ({{ fever_duration_display }})
- Considera la temperatura actual ({{ temperature }}°C)
- Considera el estado general del niño ({{ general_symptoms_display }})

**Si el medicamento parece estar funcionando:**
- Recomienda CONTINUAR con {{ current_medication_info.medication_name }}
- Verifica/corrige la dosis según el peso ({{ patient_weight_kg }} kg)
- Explica que está bien seguir con ese tratamiento

**Si el medicamento NO está funcionando bien:**
- Recomienda cambiar o ALTERNAR con otro antipirético
- Explica las opciones: acetaminofen cada 6h, ibuprofeno cada 6-8h, o alternar ambos
- Proporciona dosis correctas según peso

{% else -%}
**El paciente NO ha tomado antipiréticos.**

Recomienda medicación apropiada:
{% endif -%}

{% if not acetaminofen_dose.error -%}
Acetaminofen: {{ acetaminofen_dose.dose_ml_suspension }}ml suspensión 160mg/5ml c/{{ acetaminofen_dose.interval_hours }}h (o {{ acetaminofen_dose.dose_ml_drops }}ml gotas 100mg/ml). Máx 4 dosis/día. Jeringa dosificadora.
{% if acetaminofen_dose.warning -%}⚠️ {{ acetaminofen_dose.warning }}{% endif %}
{% else -%}
{{ acetaminofen_dose.warning }} Consultar farmacéutico.
{% endif -%}

{% if ibuprofen_dose.contraindicated -%}
{{ ibuprofen_dose.warning }}
{% elif not ibuprofen_dose.error -%}
Ibuprofeno (alternativa): {{ ibuprofen_dose.dose_ml_suspension }}ml suspensión 100mg/5ml c/{{ ibuprofen_dose.interval_hours }}h. Máx 3 dosis/día.
{% endif -%}

Hidratación c/30-60min, ropa ligera, ambiente fresco. No baños fríos ni alcohol.
- Termina con: **%%%%%%%%%%**

**3. SIGNOS ALARMA Y SEGUIMIENTO (1-2 párrafos):**
Urgencias si: fiebre >40°C, decaimiento severo, rechazo líquidos, no orina 8-12h, dificultad respirar, manchas no desaparecen, convulsiones, vómitos persistentes.

Temperatura c/4-6h. Observar entre fiebres. Pediatra si persiste >3 días o nuevos síntomas. Mayoría virales, resuelven 3-5 días.

⚠️ **IMPORTANTE - BROTE CUTÁNEO:** Menciona que es NORMAL que aparezca un brote cutáneo (sarpullido/erupción) al 3°-4° día cuando baja la fiebre. Esto es típico de infecciones virales comunes (roséola, otros virus). NO es alarma si el niño mejora. Es alarma si aparece CON fiebre alta y no desaparece al presionar (petequias/púrpura).

- NO incluir disclaimer final
- Termina con: **%%%%%%%%%%**

**INTEGRA EN PÁRRAFOS NATURALES. NO uses "**TRATAMIENTO:**" o encabezados grandes.**

{% endif %}

# TONO Y ESTILO

**Escribe como PEDIATRA REAL, no documento médico formal.**

Estilo:
- Natural y conversacional (mensaje a padres)
- Sin formateo excesivo (evita emojis, viñetas exageradas, negritas innecesarias)
- Conciso pero completo
- Lenguaje directo: "Dele paracetamol..." NO "**Dosis calculada:**"
- Humano: reconoce preocupación, mantén tono profesional cercano

Estructura flexible:
1. Apertura (1 párr): situación, nivel preocupación
2. Qué hacer (1-2 párr): medicación con dosis, medidas caseras
3. Cuándo preocuparse (1 párr): signos alarma claros
4. Seguimiento (1 párr): qué esperar, cuándo consultar

Ejemplos según duración de fiebre:

**Ejemplo 1 (fiebre de 18h):**
"Alejo tiene fiebre alta pero sin alarmas inmediatas. Como lleva 18 horas con fiebre, si persiste más de 6 horas (completando 24h), debe ser evaluado por pediatra.
##########
Mientras, dele acetaminofen: 4.7ml suspensión 160mg/5ml c/6h. Jeringa dosificadora. Líquidos frecuentes, ropa ligera.
%%%%%%%%%%
Urgencias si: muy decaído, no bebe, manchas que no desaparecen, cuesta respirar. Es normal que al tercer o cuarto día aparezca un sarpullido cuando baja la fiebre, típico de virus comunes.
%%%%%%%%%%"

**Ejemplo 2 (fiebre de 60h):**
"María lleva 60 horas con fiebre. Aunque está estable, recomiendo evaluación pediátrica en las próximas 12 horas, antes de completar 72 horas de fiebre.
##########
[tratamiento...]
%%%%%%%%%%"

**Ejemplo 3 (fiebre de 75h):**
"Pedro lleva más de 3 días con fiebre (75 horas). Necesita evaluación pediátrica HOY MISMO, idealmente en las próximas 6 horas.
##########
[tratamiento...]
%%%%%%%%%%"

Evita: listas largas emojis, secciones numeradas excesivas, formateo tipo manual médico, disclaimers legales largos.

**Genera evaluación como pediatra, no documento.**
"""

def get_fever_duration_display(hours_str: str) -> str:
    """Convierte horas a formato legible"""
    try:
        hours = int(hours_str)
        if hours < 24:
            return f"menos de un día ({hours}h)"
        elif hours < 48:
            return "aproximadamente 1 día"
        elif hours < 72:
            return "aproximadamente 2 días"
        elif hours < 96:
            return "aproximadamente 3 días"
        else:
            days = hours // 24
            return f"aproximadamente {days} días"
    except (ValueError, TypeError):
        return "duración no especificada"

def safe_display(value: str, default: str = "No especificado") -> str:
    """Retorna el valor o default si está vacío/desconocido"""
    if not value or value in ["desconocido", "", "0"]:
        return default
    return value


def calculate_acetaminofen_dose(weight_kg: str, age_months: str) -> dict:
    """
    Calcula la dosis de acetaminofen (paracetamol) según peso y edad.
    
    Dosificación estándar:
    - 15 mg/kg por dosis
    - Cada 6 horas (máximo 4 dosis/día)
    - Dosis máxima diaria: 60 mg/kg/día
    
    Presentaciones comunes:
    - Suspensión pediátrica: 160 mg/5 ml (32 mg/ml)
    - Gotas pediátricas: 100 mg/ml
    
    Returns:
        dict con:
            - dose_mg: dosis en mg
            - dose_ml_suspension: dosis en ml de suspensión (160mg/5ml)
            - dose_ml_drops: dosis en ml de gotas (100mg/ml)
            - max_daily_mg: dosis máxima diaria en mg
            - interval_hours: intervalo entre dosis
            - warning: advertencia si aplica
    """
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
            "error": True
        }
    
    # Validar peso razonable
    if weight < 2 or weight > 100:
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "dose_ml_drops": None,
            "max_daily_mg": None,
            "interval_hours": 6,
            "warning": "Peso fuera de rango esperado. Consultar con pediatra.",
            "error": True
        }
    
    # Cálculo de dosis
    dose_mg = weight * 15  # 15 mg/kg por dosis
    max_daily_mg = weight * 60  # 60 mg/kg/día máximo
    
    # Convertir a ml según presentación
    # Suspensión pediátrica: 160 mg en 5 ml → 32 mg/ml
    dose_ml_suspension = dose_mg / 32
    
    # Gotas pediátricas: 100 mg/ml
    dose_ml_drops = dose_mg / 100
    
    # Redondear a décimas
    dose_ml_suspension = round(dose_ml_suspension, 1)
    dose_ml_drops = round(dose_ml_drops, 1)
    
    # Advertencias especiales
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
        "error": False
    }


def calculate_ibuprofen_dose(weight_kg: str, age_months: str) -> dict:
    """
    Calcula la dosis de ibuprofeno según peso y edad.
    
    Dosificación estándar:
    - 10 mg/kg por dosis
    - Cada 8 horas (máximo 3 dosis/día)
    - Dosis máxima diaria: 30 mg/kg/día
    - Solo en mayores de 6 meses
    
    Presentaciones comunes:
    - Suspensión pediátrica: 100 mg/5 ml (20 mg/ml)
    
    Returns:
        dict con información de dosificación o advertencia si no aplica
    """
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
            "contraindicated": False
        }
    
    # Contraindicado en menores de 6 meses
    if age < 6:
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "max_daily_mg": None,
            "interval_hours": 8,
            "warning": "❌ NO usar ibuprofeno en menores de 6 meses. Solo paracetamol.",
            "error": True,
            "contraindicated": True
        }
    
    # Validar peso razonable
    if weight < 2 or weight > 100:
        return {
            "dose_mg": None,
            "dose_ml_suspension": None,
            "max_daily_mg": None,
            "interval_hours": 8,
            "warning": "Peso fuera de rango esperado. Consultar con pediatra.",
            "error": True,
            "contraindicated": False
        }
    
    # Cálculo de dosis
    dose_mg = weight * 10  # 10 mg/kg por dosis
    max_daily_mg = weight * 30  # 30 mg/kg/día máximo
    
    # Suspensión pediátrica: 100 mg en 5 ml → 20 mg/ml
    dose_ml_suspension = dose_mg / 20
    dose_ml_suspension = round(dose_ml_suspension, 1)
    
    return {
        "dose_mg": round(dose_mg, 1),
        "dose_ml_suspension": dose_ml_suspension,
        "max_daily_mg": round(max_daily_mg, 1),
        "interval_hours": 8,
        "warning": None,
        "error": False,
        "contraindicated": False
    }

prompt_template = PromptTemplate.from_template(
    RECOMMENDATION_TEMPLATE,
    template_format="jinja2",
    partial_variables={"today": date.today().strftime("%Y-%m-%d")}
)
