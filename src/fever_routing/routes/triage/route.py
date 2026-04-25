from typing import Literal
import json

from fever_routing.state import State
from fever_routing.utils.logging import debug_print


# ========== HELPER FUNCTIONS ==========

def safe_parse_int(value: str, default: int = 0) -> int:
    """Parsea un string a int de forma segura, retornando default si falla"""
    if not value or value == "desconocido" or value == "":
        return default
    try:
        return int(float(value))  # float primero para manejar "24.5" → 24
    except (ValueError, TypeError):
        return default


def safe_parse_float(value: str, default: float = 0.0) -> float:
    """Parsea un string a float de forma segura, retornando default si falla"""
    if not value or value == "desconocido" or value == "":
        return default
    try:
        debug_print(f"  ℹ️ safe_parse_float: {value}")
        debug_print(f"  ℹ️ safe_parse_float: {float(value)}")
        return float(value)
    except (ValueError, TypeError):
        return default


def calculate_checklist_completion(state: State) -> dict:
    """
    Calcula qué porcentaje del checklist pediátrico está completo usando PESOS ADAPTATIVOS.

    WEIGHTED SCORING:
    - Critical fields (must have): 50% weight - edad, temperatura, duración
    - Important fields (should have): 35% weight - síntomas, hidratación, antecedentes
    - Nice to have (optional): 15% weight - vacunación, medicación previa

    Ready for recommendation when:
    - All critical fields (100%) + Most important fields (≥60%) = weighted score ≥0.70
    OR
    - Urgency detected (handled by assess_urgency)

    Returns:
        dict con:
            - score: float 0.0-1.0 (weighted score)
            - raw_score: float 0.0-1.0 (simple percentage)
            - completed: int cantidad de campos completos
            - total: int cantidad total de campos
            - missing: list[str] nombres de campos faltantes
            - has_critical_data: bool si tiene todos los campos críticos
            - critical_complete: bool all critical fields filled
            - important_complete_pct: float % of important fields filled
            - ready_for_recommendation: bool ready based on weighted criteria
    """
    # Helper para verificar si un campo está completo
    def is_complete(field_value):
        """
        Verifica si un campo tiene información válida.

        IMPORTANTE: "no" es una respuesta VÁLIDA y COMPLETA.
        Ejemplos:
        - medication_given: "no" → Completo ✅
        - medical_history: "no" → Completo ✅
        - general_symptoms: "vomitos:no" → Completo ✅

        Solo son INCOMPLETOS:
        - Vacío: ""
        - Desconocido: "desconocido"
        - Sin responder: "0"
        """
        if not field_value:
            return False

        # Valores que indican campo incompleto
        incomplete_values = ["desconocido", "", "0"]

        return field_value not in incomplete_values

    # Temperatura: medida = ideal. Tactile sólo cuenta si NO hay termómetro disponible.
    # Si el padre tiene termómetro pero aún no dio número, NO consideramos temp completa
    # — el inquiry seguirá pidiendo el valor exacto.
    def has_temperature_data():
        has_measured_temp = is_complete(state.get("temperature", ""))
        if has_measured_temp:
            return True
        has_tactile = is_complete(state.get("tactile_fever_assessment", ""))
        if not has_tactile:
            return False
        # Tactile only acceptable when thermometer unavailable.
        has_thermometer = state.get("has_thermometer", "").lower()
        return has_thermometer == "no"

    # Construir checklist con logging de valores "no"
    medication_given_val = state.get("medication_given", "")
    recent_antibiotics_val = state.get("recent_antibiotics", "")
    home_measures_val = state.get("home_measures_taken", "")

    # CRITICAL FIELDS (must have - 50% total weight)
    critical_fields = {
        "edad": is_complete(state.get("patient_birthdate", "")),
        "temperatura": has_temperature_data(),
        "duracion_fiebre": is_complete(state.get("fever_duration_hours", "")),
    }

    # IMPORTANT FIELDS (should have - 35% total weight)
    important_fields = {
        "peso": is_complete(state.get("patient_weight_kg", "")),
        "antecedentes": is_complete(state.get("medical_history", "")),
        "sintomas_generales": is_complete(state.get("general_symptoms", "")),
        "sintomas_respiratorios": is_complete(state.get("respiratory_symptoms", "")),
        "hidratacion": is_complete(state.get("hydration_status", "")),
        "signos_alarma_visual": is_complete(state.get("visual_alarm_signs", "")),
    }

    # NICE TO HAVE FIELDS (optional - 15% total weight)
    optional_fields = {
        "lugar_termometro": is_complete(state.get("thermometer_location", "")) or is_complete(state.get("tactile_fever_assessment", "")),
        "medicacion_previa": is_complete(medication_given_val),
        "alimentacion": is_complete(state.get("feeding_status", "")),
        "estado_vacunal": is_complete(state.get("vaccination_status", "")),
    }

    # Debug: Log de campos con valor "no" que son considerados completos
    if medication_given_val == "no":
        debug_print(f"  ℹ️ medication_given='no' considerado COMPLETO")
    if recent_antibiotics_val == "no":
        debug_print(f"  ℹ️ recent_antibiotics='no' considerado COMPLETO")
    if home_measures_val == "no":
        debug_print(f"  ℹ️ home_measures_taken='no' considerado COMPLETO")

    # Calculate completion rates
    critical_completed = sum(1 for v in critical_fields.values() if v)
    critical_total = len(critical_fields)
    critical_complete_pct = critical_completed / critical_total if critical_total > 0 else 0.0

    important_completed = sum(1 for v in important_fields.values() if v)
    important_total = len(important_fields)
    important_complete_pct = important_completed / important_total if important_total > 0 else 0.0

    optional_completed = sum(1 for v in optional_fields.values() if v)
    optional_total = len(optional_fields)
    optional_complete_pct = optional_completed / optional_total if optional_total > 0 else 0.0

    # Calculate weighted score
    weighted_score = (
        critical_complete_pct * 0.50 +  # Critical: 50% weight
        important_complete_pct * 0.35 +  # Important: 35% weight
        optional_complete_pct * 0.15      # Optional: 15% weight
    )

    # Combined checklist for legacy compatibility
    checklist = {**critical_fields, **important_fields, **optional_fields}

    completed = sum(1 for v in checklist.values() if v)
    total = len(checklist)
    raw_score = completed / total if total > 0 else 0.0

    missing = [k for k, v in checklist.items() if not v]

    # Critical data check
    critical_complete = all(critical_fields.values())
    has_critical_data = critical_complete

    # Ready for recommendation: 
    # ANTES: All critical + ≥60% important = weighted ≥0.70
    # AHORA: Queremos preguntar TODOS los síntomas, así que exigimos completitud total en importantes.
    # Cambiamos la condición para que solo pase a recomendación si important_complete_pct es 1.0 (o muy cercano)
    
    # Opción estricta: exigir 100% en critical y 100% en important
    ready_for_recommendation = critical_complete and important_complete_pct >= 0.99

    debug_print(f"\n📊 WEIGHTED CHECKLIST SCORING:")
    debug_print(f"  Critical ({critical_completed}/{critical_total}): {critical_complete_pct:.0%} × 50% = {critical_complete_pct * 0.50:.2f}")
    debug_print(f"  Important ({important_completed}/{important_total}): {important_complete_pct:.0%} × 35% = {important_complete_pct * 0.35:.2f}")
    debug_print(f"  Optional ({optional_completed}/{optional_total}): {optional_complete_pct:.0%} × 15% = {optional_complete_pct * 0.15:.2f}")
    debug_print(f"  ➡️ Weighted Score: {weighted_score:.2f} (70% threshold)")
    debug_print(f"  ➡️ Ready for recommendation: {ready_for_recommendation} (MODIFICADO: Exige 100% síntomas importantes)")

    return {
        "score": weighted_score,  # Use weighted score as primary
        "raw_score": raw_score,
        "completed": completed,
        "total": total,
        "missing": missing,
        "has_critical_data": has_critical_data,
        "critical_complete": critical_complete,
        "important_complete_pct": important_complete_pct,
        "ready_for_recommendation": ready_for_recommendation
    }


def detect_red_flags(state: State) -> list[str]:
    """
    Detecta signos de alarma rojos que requieren atención prioritaria.

    IMPORTANTE: Los red flags detectados se guardan en el estado pero NO fuerzan
    salida inmediata a RECOMMENDATION. El sistema completa el assessment (≥80% checklist)
    antes de dar recomendaciones, incluso con red flags presentes.

    Basado en guías internacionales (NICE, AAP, AEP) y criterios clínicos:
    
    CRITERIOS DE EDAD:
    - Menor de 3 meses con fiebre ≥38°C
    - 3-6 meses con fiebre ≥39°C
    - Fiebre >40°C cualquier edad
    
    INESTABILIDAD HEMODINÁMICA:
    - Piel fría, húmeda, moteada
    - Llenado capilar lento
    - Signos de shock
    
    ALTERACIÓN DEL ESTADO MENTAL:
    - Letargo severo, confusión
    - No responde, irritabilidad extrema
    - Mirada perdida, muy apagado
    
    DIFICULTAD RESPIRATORIA SEVERA:
    - Retracciones, quejido, tiraje
    - Cianosis (azulado)
    - Aleteo nasal
    
    SIGNOS NEUROLÓGICOS:
    - Convulsiones
    - Rigidez de nuca
    - Fontanela abombada
    - Fotofobia
    
    SIGNOS EN PIEL CRÍTICOS:
    - Rash no blanqueable (petequias/púrpura)
    - Alteración coloración severa
    
    DISFUNCIÓN ORGÁNICA:
    - Oliguria/no orina
    - Ictericia
    - Manifestaciones de sangrado

    Returns:
        list[str]: Lista de red flags detectados
    """
    red_flags = []

    # Parsear edad y temperatura de forma segura
    age = safe_parse_int(state.get("patient_age_months", "0"), 0)
    temp = safe_parse_float(state.get("temperature", "0"), 0.0)
    temp_location = state.get("thermometer_location", "").lower()

    # RED FLAG 1: Edad menor de 3 meses con fiebre
    # SPECIAL RULES for <3 months:
    # - Rectal ≥38.0°C = fever
    # - Axillary 37.6-37.9°C = possible fever (may be ≥38°C rectal)
    # - Axillary ≥38.0°C = fever
    if age > 0 and age < 3:
        is_fever = False

        if "rectal" in temp_location and temp >= 38.0:
            is_fever = True
            debug_print(f"  🚨 <3mo: Rectal temp {temp}°C ≥38°C → FEVER")
        elif "axilar" in temp_location:
            if temp >= 38.0:
                is_fever = True
                debug_print(f"  🚨 <3mo: Axillary temp {temp}°C ≥38°C → FEVER")
            elif 37.6 <= temp < 38.0:
                is_fever = True
                debug_print(f"  ⚠️ <3mo: Axillary temp {temp}°C (37.6-37.9°C) → POSSIBLE FEVER (may be ≥38°C rectal)")
        elif temp >= 38.0:
            # Unknown location but temp ≥38°C
            is_fever = True
            debug_print(f"  🚨 <3mo: Temp {temp}°C ≥38°C (location: {temp_location}) → FEVER")

        if is_fever:
            red_flags.append("menor_3m_fiebre_alta")

    # RED FLAG 2: Edad 3-6 meses con fiebre ≥39°C
    if age >= 3 and age < 6 and temp >= 39.0:
        red_flags.append("3_6m_fiebre_muy_alta")

    # RED FLAG 3: Fiebre muy alta en cualquier edad (>40°C)
    if temp >= 40.0:
        red_flags.append("fiebre_mayor_40")

    # Analizar síntomas estructurados
    general_symp = state.get("general_symptoms", "").lower()
    resp_symp = state.get("respiratory_symptoms", "").lower()
    visual = state.get("visual_alarm_signs", "").lower()
    other_symp = state.get("other_symptoms", "").lower()

    # RED FLAG CRITICAL: Convulsiones (check in ALL symptom fields)
    # CRITICAL: Parents may mention convulsions anywhere, so check all fields
    if any(x in general_symp or x in other_symp or x in resp_symp for x in ["convulsion", "convulsiona", "convulsiones:si", "temblor", "tiembla", "sacudidas"]):
        red_flags.append("convulsiones")
        debug_print(f"  🚨 CRITICAL: Convulsiones detected in symptoms!")

    # RED FLAG 4: Estado general comprometido — solo "severo" o "decaído + no juega"
    # cuentan como red flag. "decaido:leve" o "más quietico" NO son red flag.
    if "decaido:severo" in general_symp:
        red_flags.append("decaimiento_severo")
    if "juega:no" in general_symp and "decaido:si" in general_symp:
        red_flags.append("letargo_posible")

    # Nuevos: Alteración mental severa
    if any(x in general_symp or x in other_symp for x in ["letargo_severo:si", "confuso:si", "no_responde:si", "irritable_extremo:si"]):
        red_flags.append("alteracion_estado_mental_severa")

    # RED FLAG 5: Dificultad respiratoria severa
    if "dificultad_respirar:si" in resp_symp or "dificultad_respirar:severo" in resp_symp:
        debug_print(f"  ℹ️ general_symp: {general_symp}")
        debug_print(f"  ℹ️ other_symp: {other_symp}")
        debug_print(f"  ℹ️ resp_symp: {resp_symp}")
        debug_print(f"  ℹ️ visual: {visual}")
        debug_print(f"  ℹ️ dificultad_respirar='si' considerado RED FLAG")
        red_flags.append("dificultad_respiratoria_severa")
    
    # Nuevos: Signos respiratorios críticos
    if any(x in resp_symp or x in visual for x in ["cianosis:si", "quejido:si", "retracciones:si", "azulado:si"]):
        red_flags.append("signos_respiratorios_criticos")

    # RED FLAG 6: Alteraciones visuales de alarma
    if "mal_color:si" in visual or "palido:si" in visual:
        red_flags.append("alteracion_coloracion_piel")
    if "erupciones:si" in visual or "manchas:si" in visual:
        red_flags.append("rash_requiere_evaluacion")
    
    # Nuevos: Inestabilidad hemodinámica
    if any(x in visual or x in other_symp for x in ["piel_fria:si", "piel_moteada:si", "llenado_capilar_lento:si", "palido_extremo:si"]):
        red_flags.append("inestabilidad_hemodinamica")
    
    # Nuevos: Rash no blanqueable (específico)
    if any(x in visual for x in ["rash_no_blanqueable:si", "petequias:si", "purpura:si"]):
        red_flags.append("rash_no_blanqueable")
    
    # RED FLAG 7: Signos neurológicos críticos
    if any(x in other_symp for x in ["convulsiones:si", "rigidez_nuca:si", "fontanela_abombada:si", "fotofobia:si"]):
        red_flags.append("signos_neurologicos_criticos")
    
    # RED FLAG 8: Signos de disfunción orgánica
    if any(x in other_symp for x in ["oliguria:si", "no_orina:si", "ictericia:si", "sangrado:si", "vomito_sangre:si"]):
        red_flags.append("disfuncion_organica")

    # OPTIMIZATION: Search keywords only in user messages (not in all conversation)
    # This is more efficient and avoids false positives from assistant echoing symptoms
    # NOTE: Keyword search is commented out in original code, keeping structure for future use

    # Uncomment below if keyword search is needed:
    # messages = state.get("messages", [])
    # user_text = " ".join([
    #     msg.content.lower() if isinstance(msg.content, str) else str(msg.content).lower()
    #     for msg in messages
    #     if hasattr(msg, '__class__') and msg.__class__.__name__ == "HumanMessage"
    # ])
    #
    # CRITICAL_KEYWORDS = {
    #     "convulsion": "convulsiones",
    #     "convulsión": "convulsiones",
    #     "rigidez": "rigidez_nuca",
    #     "no despierta": "letargo_extremo",
    #     "no responde": "letargo_extremo",
    #     "sangr": "manifestaciones_sangrado",
    #     "petequias": "rash_no_blanqueable",
    #     "no blanquea": "rash_no_blanqueable",
    #     "azul": "signos_respiratorios_criticos",
    #     "cianosis": "signos_respiratorios_criticos",
    # }
    #
    # for keyword, flag in CRITICAL_KEYWORDS.items():
    #     if keyword in user_text and flag not in red_flags:
    #         red_flags.append(flag)

    return red_flags


def assess_urgency(state: State) -> dict:
    """
    UNIFIED urgency assessment combining age/temp criteria with red flag detection.

    Returns urgency level: "critical" > "urgent" > "standard"

    CRITICAL (immediate 911/ER - bypass ALL checklist):
    - Convulsions/seizures
    - Severe respiratory distress (cyanosis, grunting, retractions)
    - Hemodynamic instability (cold/mottled skin, shock signs)
    - Non-blanching rash (petechiae/purpura)
    - Extreme lethargy/unresponsive
    - Organ dysfunction (no urine, bleeding, jaundice in neonate)

    URGENT (fast-track to recommendation, complete minimal checklist):
    - Age < 3 months with fever > 38°C
    - Fever ≥ 40°C any age
    - Age 3-6 months with fever ≥ 39°C
    - Moderate red flags (severe lethargy, persistent vomiting)

    STANDARD (normal flow):
    - No critical or urgent criteria met

    Returns:
        dict with:
            - level: "critical" | "urgent" | "standard"
            - reasons: list[str] - All flags/criteria that triggered this level
            - has_required_data: bool - Has age + temp for basic assessment
            - missing_for_assessment: list[str] - Data needed for full assessment
            - age: int - Patient age in months
            - temp: float - Temperature in °C
    """
    age = safe_parse_int(state.get("patient_age_months", ""), -1)
    temp = safe_parse_float(state.get("temperature", ""), -1.0)

    # Check if we have basic data
    has_age = age >= 0
    has_temp = temp > 0
    missing = []
    if not has_age:
        missing.append("edad")
    if not has_temp:
        missing.append("temperatura")

    has_required_data = has_age and has_temp

    # Detect all red flags
    red_flags = detect_red_flags(state)

    # Categorize red flags by severity
    CRITICAL_FLAGS = {
        "convulsiones", "signos_neurologicos_criticos", "rigidez_nuca",
        "signos_respiratorios_criticos", "cianosis", "quejido_respiratorio",
        "inestabilidad_hemodinamica", "rash_no_blanqueable",
        "letargo_extremo", "alteracion_estado_mental_severa",
        "disfuncion_organica", "manifestaciones_sangrado"
    }

    URGENT_FLAGS = {
        "dificultad_respiratoria_severa", "decaimiento_severo",
        "letargo_posible", "alteracion_coloracion_piel",
        "rash_requiere_evaluacion",
        "menor_3m_fiebre_alta",  # <3 months with fever ≥38°C (or 37.6-37.9°C axillary)
        "3_6m_fiebre_muy_alta",  # 3-6 months with fever ≥39°C
        "fiebre_mayor_40"  # Any age with fever ≥40°C
    }

    reasons = []

    # Check for CRITICAL red flags
    critical_red_flags = [flag for flag in red_flags if flag in CRITICAL_FLAGS]
    if critical_red_flags:
        return {
            "level": "critical",
            "reasons": critical_red_flags,
            "has_required_data": has_required_data,
            "missing_for_assessment": missing,
            "age": age,
            "temp": temp,
            "red_flags": red_flags
        }

    # Check for URGENT criteria (age + temp)
    if has_required_data:
        if age < 3 and temp > 38.0:
            reasons.append("lactante_menor_3m_fiebre")
        elif temp >= 40.0:
            reasons.append("fiebre_muy_alta_40")
        elif age >= 3 and age < 6 and temp >= 39.0:
            reasons.append("lactante_3_6m_fiebre_alta")

    # Check for URGENT red flags
    urgent_red_flags = [flag for flag in red_flags if flag in URGENT_FLAGS]
    if urgent_red_flags:
        reasons.extend(urgent_red_flags)

    # Determine level
    if reasons:
        return {
            "level": "urgent",
            "reasons": reasons,
            "has_required_data": has_required_data,
            "missing_for_assessment": missing,
            "age": age,
            "temp": temp,
            "red_flags": red_flags
        }

    # STANDARD case
    return {
        "level": "standard",
        "reasons": [],
        "has_required_data": has_required_data,
        "missing_for_assessment": missing,
        "age": age,
        "temp": temp,
        "red_flags": red_flags
    }


def triage_route(
    state: State,
) -> Literal["inquiry", "recommendation", "urgency_recommendation", "answer_question"]:
    """
    Determina el siguiente paso en el triaje basándose en:
    0. URGENCIA INMEDIATA: Si temp >38°C AND edad <3 meses → urgency_recommendation
    1. Si estamos en recomendación interactiva (section 1 o 2) → volver a recommendation
    2. Checklist completion ≥ 80% → recommendation (AUNQUE HAYA RED FLAGS, completar assessment primero)
    3. Tiene datos críticos pero falta info → inquiry (continuar recopilando)
    4. Falta información básica → inquiry

    NOTA: Los red flags se detectan y guardan en el estado, pero NO fuerzan salida inmediata.
    Esto permite completar el assessment antes de dar recomendaciones.

    Esta es la función de ROUTING del grafo.
    """

    # DECISIÓN 0X: si el padre hizo una pregunta directa además de aportar data,
    # después de extraer respondemos la pregunta antes de seguir el script.
    pending_q = state.get("pending_user_question", "") or ""
    if pending_q.strip():
        debug_print(f"📩 pending user question after receptor → answer_question: {pending_q[:60]}")
        return "answer_question"

    # DECISIÓN 0A: Si ya estamos en urgency_recommendation, continuar ahí
    urgency_given = state.get("urgency_recommendation_given", "")
    if urgency_given == "yes":
        debug_print("\n" + "🚨" * 80)
        debug_print("🔄 TRIAGE ROUTE - RECOMENDACIÓN URGENTE EN PROGRESO")
        debug_print("=" * 80)
        debug_print("✅ DECISIÓN: Continuar respondiendo preguntas urgentes → Ir a URGENCY_RECOMMENDATION")
        debug_print("=" * 80 + "\n")
        return "urgency_recommendation"

    # DECISIÓN 0B: Si estamos en medio de una recomendación interactiva, volver a recommendation
    current_section = state.get("recommendation_section", "0")
    if current_section in ["1", "2"]:
        debug_print("\n" + "🩺" * 80)
        debug_print("🔄 TRIAGE ROUTE - RECOMENDACIÓN INTERACTIVA EN PROGRESO")
        debug_print("=" * 80)
        debug_print(f"📍 Sección actual: {current_section}")
        debug_print("✅ DECISIÓN: Continuar con recomendación interactiva → Ir a RECOMMENDATION")
        debug_print("=" * 80 + "\n")
        return "recommendation"

    # DECISIÓN 0C: VERIFICAR URGENCIA (unificada: age/temp + red flags)
    urgency = assess_urgency(state)

    debug_print("\n" + "🚨" * 80)
    debug_print("🔍 TRIAGE ROUTE - EVALUACIÓN DE URGENCIA UNIFICADA")
    debug_print("=" * 80)
    debug_print(f"📊 Datos del paciente:")
    debug_print(f"  Edad: {urgency['age']} meses" if urgency['age'] >= 0 else "  Edad: NO DISPONIBLE")
    debug_print(f"  Temperatura: {urgency['temp']}°C" if urgency['temp'] > 0 else "  Temperatura: NO DISPONIBLE")
    debug_print(f"  Datos completos: {'SÍ' if urgency['has_required_data'] else 'NO'}")
    debug_print(f"\n🚦 NIVEL DE URGENCIA: {urgency['level'].upper()}")

    if urgency['level'] == "critical":
        debug_print(f"\n🚨🚨🚨 URGENCIA CRÍTICA - BYPASS TOTAL DEL CHECKLIST 🚨🚨🚨")
        debug_print(f"  Red flags críticos detectados:")
        for reason in urgency['reasons']:
            debug_print(f"    🚨 {reason}")
        debug_print(f"  ⚠️ PROTOCOLO: Evaluación de emergencia inmediata (911/ER)")
        debug_print("=" * 80)
        debug_print("✅ DECISIÓN: CRÍTICO → Ir a URGENCY_RECOMMENDATION")
        debug_print("=" * 80 + "\n")
        return "urgency_recommendation"

    elif urgency['level'] == "urgent":
        debug_print(f"\n🚨 URGENCIA ALTA - FAST-TRACK")
        debug_print(f"  Razones:")
        for reason in urgency['reasons']:
            debug_print(f"    ⚠️ {reason}")
        debug_print(f"  ⚠️ PROTOCOLO: Completar checklist mínimo y recomendar")
        debug_print("=" * 80)
        debug_print("✅ DECISIÓN: URGENTE → Ir a URGENCY_RECOMMENDATION")
        debug_print("=" * 80 + "\n")
        return "urgency_recommendation"

    elif not urgency['has_required_data']:
        debug_print(f"\n⚠️ Faltan datos básicos para evaluar urgencia: {', '.join(urgency['missing_for_assessment'])}")
        debug_print("  → Se recopilarán prioritariamente en INQUIRY")
    else:
        debug_print(f"\n✅ Nivel estándar (edad: {urgency['age']}m, temp: {urgency['temp']}°C)")
        debug_print("  → Continuar con flujo normal")
    debug_print("=" * 80 + "\n")

    # Calcular completitud del checklist
    checklist_status = calculate_checklist_completion(state)

    # Obtener red flags del estado (si fueron detectados previamente)
    red_flags_text = state.get("red_flags_detected", "")
    red_flags = [flag.strip() for flag in red_flags_text.split(",") if flag.strip()]

    # Actualizar el estado con la información de checklist (para que inquiry la use)
    # NOTA: No podemos modificar state aquí directamente en routing,
    # pero podemos usarlo para tomar decisiones

    # DEBUG: Mostrar información de decisión
    debug_print("\n" + "🩺" * 80)
    debug_print("🔍 TRIAGE ROUTE - EVALUACIÓN DE COMPLETITUD Y RIESGO")
    debug_print("=" * 80)
    debug_print(f"📊 Checklist Score: {checklist_status['score']:.0%} ({checklist_status['completed']}/{checklist_status['total']})")

    debug_print("\n✅ CAMPOS COMPLETOS:")
    all_fields = ["edad", "peso", "temperatura", "duracion_fiebre", "lugar_termometro", "medicacion_previa",
                  "sintomas_generales", "sintomas_respiratorios", "hidratacion", "alimentacion", 
                  "signos_alarma_visual", "estado_vacunal", "antecedentes"]
    for field in all_fields:
        if field not in checklist_status['missing']:
            debug_print(f"  ✓ {field}")

    debug_print("\n❓ CAMPOS FALTANTES:")
    if checklist_status['missing']:
        for field in checklist_status['missing']:
            debug_print(f"  ✗ {field}")
    else:
        debug_print("  (Ninguno - checklist completo)")

    debug_print(f"\n🚨 RED FLAGS DETECTADOS:")
    if red_flags:
        for flag in red_flags:
            debug_print(f"  ⚠️ {flag}")
        debug_print("  ℹ️ Red flags presentes pero se completará assessment antes de recomendar")
    else:
        debug_print("  ✅ Ninguno")

    debug_print(f"\n🔑 DATOS CRÍTICOS: {'✅ COMPLETOS (edad, temp, duración)' if checklist_status['has_critical_data'] else '❌ INCOMPLETOS'}")
    debug_print("=" * 80)

    # PARTIAL-DATA SHORTCUT: if inquiry signaled it has nothing more to ask,
    # advance to recommendation/urgency with what we have. Safety still applies
    # (urgency was already handled above for critical/urgent cases).
    if state.get("recommendation_with_partial_data") == "yes":
        debug_print("✅ DECISIÓN: partial-data flag → RECOMMENDATION")
        return "recommendation"

    # DECISIÓN 1: Checklist suficientemente completo (weighted score ≥0.70) → RECOMMENDATION
    # Uses ready_for_recommendation flag (all critical + ≥60% important)
    if checklist_status["ready_for_recommendation"]:
        if red_flags:
            debug_print("✅ DECISIÓN: Checklist completo CON RED FLAGS → Ir a RECOMMENDATION")
            debug_print(f"    Weighted score: {checklist_status['score']:.2f} (≥0.70)")
            debug_print(f"    Red flags detectados: {', '.join(red_flags)}")
            debug_print("    Assessment completo permite recomendación informada")
        else:
            debug_print("✅ DECISIÓN: Checklist completo sin red flags → Ir a RECOMMENDATION")
            debug_print(f"    Weighted score: {checklist_status['score']:.2f} (≥0.70)")
        debug_print("=" * 80 + "\n")
        return "recommendation"

    # DECISIÓN 2: Tiene datos críticos pero falta información → INQUIRY
    # Continuar recopilando aunque haya red flags
    if checklist_status["has_critical_data"]:
        if red_flags:
            debug_print("📋 DECISIÓN: RED FLAGS presentes pero checklist incompleto → Continuar INQUIRY")
            debug_print(f"    Red flags: {', '.join(red_flags)}")
            debug_print(f"    Completando assessment: {', '.join(checklist_status['missing'][:3])}")
        else:
            debug_print("📋 DECISIÓN: Datos críticos OK, completando checklist → Ir a INQUIRY")
            debug_print(f"    Recopilar: {', '.join(checklist_status['missing'][:3])}")
        debug_print("=" * 80 + "\n")
        return "inquiry"

    # DECISIÓN 3: Falta información básica → INQUIRY
    debug_print("❓ DECISIÓN: Faltan datos críticos → Ir a INQUIRY")
    debug_print(f"    Necesita: edad, temperatura, duración")
    debug_print("=" * 80 + "\n")
    return "inquiry"
