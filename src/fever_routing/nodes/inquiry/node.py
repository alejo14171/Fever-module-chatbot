from fever_routing.nodes.inquiry.prompt import prompt_template, get_age_display, format_missing_items
from fever_routing.state import State
from fever_routing.routes.triage.route import calculate_checklist_completion, detect_red_flags
from fever_routing.utils.logging import debug_print
from fever_routing.utils import ModelFactory, format_history
from langchain_core.messages import AIMessage
import json

llm = ModelFactory.get_inquiry_model()


def get_next_question(state: State, missing: list[str]) -> dict:
    """
    Calcula LA pregunta exacta que debe hacerse según prioridad DINÁMICA.

    CAMBIO: Prioridad ahora es adaptativa basada en:
    1. Urgencia detectada (edad + temperatura críticas)
    2. Clustering de síntomas relacionados
    3. Información ya proporcionada por el usuario
    4. Red flags potenciales

    Returns:
        dict con:
            - question: str - La pregunta exacta
            - priority: str - Nivel de prioridad
            - field: str - Campo que se va a recopilar
            - required_fields: list[str] - Campos que DEBEN llenarse
            - fallback_value: dict - Valores por defecto si no se extrae
            - extraction_hint: str - Instrucción para RECEPTOR sobre cómo extraer
    """
    patient_name = state.get("patient_name", "su hijo/a")
    if patient_name == "desconocido":
        patient_name = "su hijo/a"

    # Check urgency level to prioritize questions
    from fever_routing.routes.triage.route import assess_urgency
    urgency = assess_urgency(state)

    debug_print(f"\n🎯 DYNAMIC QUESTION SELECTION:")
    debug_print(f"  Urgency level: {urgency['level']}")
    debug_print(f"  Missing fields: {missing}")
    debug_print(f"  Already have: age={state.get('patient_age_months', 'NO')}, temp={state.get('temperature', 'NO')}")

    # ========== PRIORIDAD 0: MANEJO DE TERMÓMETRO (no bloqueante - solo si temperatura falta) ==========
    # CAMBIO: Ya no bloquea otras preguntas. Solo ofrece alternativas si necesitamos temperatura

    # Si temperatura falta Y no tiene termómetro, ofrecer evaluación táctil (pero NO bloquear)
    if "temperatura" in missing and state.get("has_thermometer") == "no" and state.get("tactile_assessment_given") != "si":
        tactile_instructions = f"""Veo que no tiene termómetro. Podemos hacer una evaluación táctil mientras:

Toque la frente, cuello y pecho de {patient_name} con el dorso de su mano y dígame:
- ¿Está caliente pero tolerable?
- ¿Muy caliente, más que usted?
- ¿Extremadamente caliente, ardiendo?"""
        return {
            "question": tactile_instructions,
            "priority": "🟡 EVALUACIÓN TÁCTIL (alternativa)",
            "field": "tactile_assessment_given",
            "required_fields": ["tactile_assessment_given", "tactile_fever_assessment"],
            "fallback_value": {"tactile_assessment_given": "si", "tactile_fever_assessment": "fiebre_moderada"},
            "extraction_hint": "Marcar tactile_assessment_given: si. Extraer tactile_fever_assessment si describe calor"
        }

    # ========== PRIORIDAD URGENTE: Detectar criterios de urgencia potencial ==========
    # Si tenemos edad <3 meses pero falta temperatura → PRIORIZAR temperatura
    # Si tenemos temp >38°C pero falta edad → PRIORIZAR edad

    age = state.get("patient_age_months", "")
    temp = state.get("temperature", "")

    try:
        age_val = int(age) if age and age != "desconocido" else -1
    except (ValueError, TypeError):
        age_val = -1

    try:
        temp_val = float(temp) if temp and temp != "desconocido" else -1.0
    except (ValueError, TypeError):
        temp_val = -1.0

    # CASO 1: Tiene edad <3 meses pero falta temperatura → URGENTE conseguir temperatura
    if age_val >= 0 and age_val < 3 and "temperatura" in missing:
        debug_print(f"  🚨 DETECCIÓN URGENTE: Lactante <3 meses (edad: {age_val}), priorizando temperatura")
        return {
            "question": f"⚠️ Como {patient_name} es menor de 3 meses, es muy importante conocer la temperatura exacta. ¿Ha podido medirla? En ese caso, ¿cuál es el valor actual y dónde la midió (frente, axila, oído)?",
            "priority": "🚨 URGENTE - Temperatura (lactante <3m)",
            "field": "temperatura",
            "required_fields": ["has_thermometer", "temperature", "thermometer_location"],
            "fallback_value": {"has_thermometer": "no", "temperature": "desconocido", "thermometer_location": "desconocido"},
            "extraction_hint": "Extraer has_thermometer: si/no. Si menciona temperatura, extraer temperature: valor en °C y thermometer_location: axilar/rectal/oral/frontal/oido."
        }

    # CASO 2: Tiene temperatura >38°C pero falta edad → URGENTE conocer edad
    if temp_val > 0 and temp_val > 38.0 and "edad" in missing:
        debug_print(f"  🚨 DETECCIÓN URGENTE: Fiebre >38°C (temp: {temp_val}), priorizando edad")
        return {
            "question": f"⚠️ Con fiebre de {temp_val}°C, necesito saber la edad exacta de {patient_name} para orientarle correctamente. ¿Cuál es su fecha de nacimiento o cuántos meses tiene?",
            "priority": "🚨 URGENTE - Edad (fiebre >38°C)",
            "field": "edad",
            "required_fields": ["patient_birthdate", "patient_age_months"],
            "fallback_value": {},
            "extraction_hint": "Extraer patient_birthdate o patient_age_months. Si dan edad, calcular ambos."
        }

    # ========== ABSOLUTE PRIORITY: MEDICAL HISTORY FIRST, TEMPERATURE SECOND ==========
    # User requirement: Always ask medical conditions first, then temperature, regardless of other logic

    # PRIORITY 1: Antecedentes médicos (ALWAYS FIRST)
    if "antecedentes" in missing:
        debug_print(f"  🔴 PRIORITY 1: Medical history missing - asking first")
        return {
            "have_in_mind": "Ten en cuenta agradecer y recibir al padre bien si es el primer mensaje de la conversación.",
            "question": f"Antes de continuar, para hacer una evaluación segura, ¿{patient_name} tiene alguna condición médica de base, enfermedad crónica o alergias que deba conocer?",
            "priority": "🔴 PRIORIDAD 1 - Antecedentes médicos (SIEMPRE PRIMERO)",
            "field": "antecedentes",
            "required_fields": ["medical_history"],
            "fallback_value": {"medical_history": "no"},
            "extraction_hint": "Si dice 'no', 'ninguno', 'nada', 'está sano' extraer: medical_history: no. Si menciona condiciones, extraerlas."
        }

    # PRIORITY 2: Temperatura (ALWAYS SECOND)
    if "temperatura" in missing:
        debug_print(f"  🔴 PRIORITY 2: Temperature missing - asking second")

        # Check if infant is <3 months - require rectal measurement
        patient_age_months = state.get("patient_age_months", "")
        try:
            age_months = int(patient_age_months) if patient_age_months else -1
        except (ValueError, TypeError):
            age_months = -1

        if 0 < age_months < 3:
            # <3 months: Ask specifically for RECTAL temperature
            debug_print(f"  ⚠️ Infant <3 months old - asking for RECTAL temperature")
            return {
                "question": f"Para bebés menores de 3 meses, necesitamos la temperatura rectal que es la más precisa. ¿Ha podido medir la temperatura rectal de {patient_name}? Si midió en la axila, dígame el valor y yo lo tomaré en cuenta, pero la medición rectal es la más confiable para su edad.",
                "priority": "🔴 PRIORIDAD 2 - Temperatura RECTAL (<3 meses)",
                "field": "temperatura",
                "required_fields": ["has_thermometer", "temperature", "thermometer_location"],
                "fallback_value": {"has_thermometer": "no", "temperature": "desconocido", "thermometer_location": "desconocido"},
                "extraction_hint": "Extraer has_thermometer: si/no. Si menciona temperatura, extraer temperature: valor en °C y thermometer_location: rectal/axilar (NO aceptar oral/frontal/oido para <3 meses)."
            }
        else:
            # ≥3 months: Standard question
            return {
                "question": f"¿Ha podido medir la temperatura de {patient_name}? En ese caso, ¿cuál es el valor actual y dónde la midió (frente, axila, oído)?",
                "priority": "🔴 PRIORIDAD 2 - Temperatura (SIEMPRE SEGUNDO)",
                "field": "temperatura",
                "required_fields": ["has_thermometer", "temperature", "thermometer_location"],
                "fallback_value": {"has_thermometer": "no", "temperature": "desconocido", "thermometer_location": "desconocido"},
                "extraction_hint": "Extraer has_thermometer: si/no. Si menciona temperatura, extraer temperature: valor en °C y thermometer_location: axilar/rectal/oral/frontal/oido."
            }

    # ========== DYNAMIC PRIORITY: Group related questions (ONLY AFTER medical history + temp) ==========
    # IMPROVEMENT: Ask symptom clusters together instead of rigid order

    # Define symptom clusters
    SYMPTOM_CLUSTERS = {
        "estado_general": ["sintomas_generales", "hidratacion", "alimentacion"],
        "respiratorio": ["sintomas_respiratorios", "signos_alarma_visual"],
    }

    # Check if we should ask clustered questions
    missing_set = set(missing)

    # If multiple symptoms from same cluster are missing, ask them together
    for cluster_name, cluster_fields in SYMPTOM_CLUSTERS.items():
        cluster_missing = [f for f in cluster_fields if f in missing_set]
        if len(cluster_missing) >= 2:
            debug_print(f"  💡 Detected cluster: {cluster_name} with {len(cluster_missing)} missing fields")
            debug_print(f"     Will ask combined question for: {cluster_missing}")

            # Ask combined question for estado_general cluster
            if cluster_name == "estado_general" and "sintomas_generales" in cluster_missing:
                return {
                    "question": f"Para evaluar cómo está {patient_name}, dígame: ¿está jugando y activo/a como siempre, o lo/la nota decaído/a? ¿Está comiendo y tomando líquidos con normalidad?",
                    "priority": "🟡 IMPORTANTE - Estado general completo",
                    "field": "sintomas_generales",
                    "required_fields": ["general_symptoms", "hydration_status", "feeding_status"],
                    "fallback_value": {"general_symptoms": "juega:si, decaido:no", "hydration_status": "bebe_normal:si", "feeding_status": "come_normal:si"},
                    "extraction_hint": "Extraer general_symptoms, hydration_status y feeding_status en formato estructurado"
                }

            # Ask combined question for respiratorio cluster
            if cluster_name == "respiratorio" and "sintomas_respiratorios" in cluster_missing:
                return {
                    "question": f"¿Ha notado si {patient_name} tiene tos, mocos, dificultad para respirar, o algún cambio en el color de la piel (pálido, azulado)?",
                    "priority": "🟡 IMPORTANTE - Evaluación respiratoria y visual",
                    "field": "sintomas_respiratorios",
                    "required_fields": ["respiratory_symptoms", "visual_alarm_signs"],
                    "fallback_value": {"respiratory_symptoms": "dificultad_respirar:no, tos:no", "visual_alarm_signs": "palido:no, cianosis:no"},
                    "extraction_hint": "Extraer respiratory_symptoms y visual_alarm_signs"
                }

    # ========== REGULAR PRIORITIES (after medical history + temperature) ==========
    # Note: antecedentes and temperatura already handled above

    # 3. Edad (fecha de nacimiento)
    if "edad" in missing:
        return {
            "question": f"¿Cuál es la fecha de nacimiento de {patient_name}?",
            "priority": "🔴 CRÍTICO - Fecha de nacimiento",
            "field": "edad",
            "required_fields": ["patient_birthdate", "patient_age_months"],
            "fallback_value": {},
            "extraction_hint": "Extraer patient_birthdate o patient_age_months. Si dan edad, calcular ambos."
        }

    # 4. Peso
    if "peso" in missing:
        return {
            "question": "Para hacer un análisis completo, ¿cuánto pesa aproximadamente? Si no lo sabe exactamente, ¿cuánto pesó en su último control?",
            "priority": "🔴 CRÍTICO - Peso del paciente",
            "field": "peso",
            "required_fields": ["patient_weight_kg"],
            "fallback_value": {},
            "extraction_hint": "Extraer patient_weight_kg en formato numérico (ej: '12', '15.5')"
        }

    # 5. Duración de fiebre
    if "duracion_fiebre" in missing:
        return {
            "question": "¿Desde cuándo tiene fiebre? Puede decirme el día y hora (ej: 'desde el martes a las 10pm') o hace cuánto tiempo (ej: 'hace 2 días')",
            "priority": "🔴 CRÍTICO - Duración de la fiebre",
            "field": "duracion_fiebre",
            "required_fields": ["fever_duration_hours"],
            "fallback_value": {},
            "extraction_hint": "Extraer fever_start_datetime si da fecha/hora específica (ej: 'martes 10pm'), o fever_duration_hours si da duración directa (ej: 'hace 48 horas'). Python calculará las horas automáticamente."
        }

    # 6. Lugar de termómetro (solo si ya tienen temperatura pero no mencionaron dónde)
    if "lugar_termometro" in missing and state.get("temperature") not in ["desconocido", "", None]:
        return {
            "question": "¿Dónde le midió la temperatura? ¿En la frente, la axila, el oído?",
            "priority": "🟡 IMPORTANTE - Método de medición",
            "field": "lugar_termometro",
            "required_fields": ["thermometer_location"],
            "fallback_value": {"thermometer_location": "axilar"},
            "extraction_hint": "Extraer thermometer_location: axilar/rectal/oral/frontal/oido"
        }

    # 7. Síntomas generales
    if "sintomas_generales" in missing:
        return {
            "question": "¿Cómo lo/la ve en general? ¿Está jugando y activo/a como siempre, o lo/la nota más decaído/a de lo normal?",
            "priority": "🟡 IMPORTANTE - Estado general",
            "field": "sintomas_generales",
            "required_fields": ["general_symptoms"],
            "fallback_value": {"general_symptoms": "juega:si, decaido:no"},
            "extraction_hint": "Extraer general_symptoms en formato 'clave:valor, clave:valor' (rechaza_alimento, vomitos, decaido, juega)"
        }

    # 8. Síntomas respiratorios
    if "sintomas_respiratorios" in missing:
        return {
            "question": "¿Ha notado si tiene tos, mocos o alguna dificultad para respirar?",
            "priority": "🟡 IMPORTANTE - Síntomas respiratorios",
            "field": "sintomas_respiratorios",
            "required_fields": ["respiratory_symptoms"],
            "fallback_value": {"respiratory_symptoms": "dificultad_respirar:no, tos:no"},
            "extraction_hint": "Si dice 'no' extraer: respiratory_symptoms: dificultad_respirar:no, tos:no. Si menciona síntomas, extraerlos."
        }

    # 9. Hidratación
    if "hidratacion" in missing:
        return {
            "question": f"¿{patient_name} está tomando líquidos con normalidad? ¿Ha notado si orina como siempre o ha orinado menos?",
            "priority": "🟡 IMPORTANTE - Estado de hidratación",
            "field": "hidratacion",
            "required_fields": ["hydration_status"],
            "fallback_value": {"hydration_status": "bebe_normal:si, orina_normal:si"},
            "extraction_hint": "Extraer hydration_status en formato 'clave:valor' (bebe_normal, rechaza_liquidos, orina_normal, orina_menos). Si dice 'normal' o 'bien': bebe_normal:si, orina_normal:si"
        }
    
    # 10. Alimentación
    if "alimentacion" in missing:
        return {
            "question": f"¿{patient_name} está comiendo normal o ha rechazado alimentos? ¿Ha vomitado?",
            "priority": "🟡 IMPORTANTE - Estado de alimentación",
            "field": "alimentacion",
            "required_fields": ["feeding_status"],
            "fallback_value": {"feeding_status": "come_normal:si, rechaza_alimento:no, vomita:no"},
            "extraction_hint": "Extraer feeding_status en formato 'clave:valor' (come_normal, rechaza_alimento, vomita). Si dice 'come bien' o 'normal': come_normal:si, rechaza_alimento:no, vomita:no"
        }

    # 11. Signos de alarma visual
    if "signos_alarma_visual" in missing:
        return {
            "question": f"¿Ha notado algún cambio en el color de la piel de {patient_name}? ¿Pálido, azulado, o alguna erupción o manchas?",
            "priority": "🟡 IMPORTANTE - Signos visuales de alarma",
            "field": "signos_alarma_visual",
            "required_fields": ["visual_alarm_signs"],
            "fallback_value": {"visual_alarm_signs": "palido:no, rash:no, cianosis:no"},
            "extraction_hint": "Si dice 'no' extraer: visual_alarm_signs: palido:no, rash:no, cianosis:no. Si menciona signos, extraerlos."
        }

    # 12. Medicación previa
    if "medicacion_previa" in missing:
        return {
            "question": "¿Le ha dado algún medicamento para la fiebre? Si es así, ¿cuál y hace cuánto tiempo?",
            "priority": "🟢 COMPLEMENTARIO - Tratamiento previo",
            "field": "medicacion_previa",
            "required_fields": ["medication_given"],
            "fallback_value": {"medication_given": "no"},
            "extraction_hint": "Si dice 'no', 'nada', 'ninguno' extraer: medication_given: no. Si menciona medicamentos, extraer con dosis y tiempo."
        }

    # 13. Estado vacunal
    if "estado_vacunal" in missing:
        return {
            "question": "¿Tiene las vacunas al día según su edad?",
            "priority": "🟢 COMPLEMENTARIO - Estado de vacunación",
            "field": "estado_vacunal",
            "required_fields": ["vaccination_status"],
            "fallback_value": {"vaccination_status": "desconocido"},
            "extraction_hint": "Extraer vaccination_status: completo/incompleto/desconocido"
        }

    # Si no hay nada faltante (no debería llegar aquí)
    return {
        "question": "¿Hay algún otro síntoma o algo más que deba saber?",
        "priority": "ℹ️ INFORMACIÓN ADICIONAL",
        "field": "other",
        "required_fields": ["other_symptoms"],
        "fallback_value": {},
        "extraction_hint": "Extraer any information mencionada"
    }


def check_needs_no_fever_clarification(state: State, messages: list, questions_asked: list) -> dict:
    """
    Verifica si necesitamos aclarar que la temperatura NO es fiebre.

    Criterios:
    - Usuario mencionó "fiebre" o "fever" en la conversación
    - Temperatura fue RECIENTEMENTE medida (temperatura en questions_asked) y es <38°C
    - NO hemos dado clarificación previa (verificar mensajes del asistente)

    Returns:
        dict con:
            - needs_clarification: bool
            - temp_value: float
            - clarification_text: str (mensaje a prepend)
    """
    # 1. Verificar si tenemos temperatura <38°C
    temp_str = state.get("temperature", "")
    try:
        temp = float(temp_str) if temp_str and temp_str != "desconocido" else -1.0
    except (ValueError, TypeError):
        temp = -1.0

    if temp <= 0 or temp >= 38.0:
        return {"needs_clarification": False, "temp_value": temp, "clarification_text": ""}

    # 2. Verificar si temperatura fue RECIENTEMENTE recolectada
    # Si "temperatura" está en questions_asked, significa que ya preguntamos por ella
    # Y ahora tenemos el valor, así que fue recientemente recolectada
    if "temperatura" not in questions_asked:
        # Aún no hemos preguntado por temperatura, no dar clarificación
        return {"needs_clarification": False, "temp_value": temp, "clarification_text": ""}

    # 3. Verificar si usuario mencionó "fiebre" o "fever"
    fever_mentioned = False
    for msg in messages:
        if hasattr(msg, '__class__') and msg.__class__.__name__ == "HumanMessage":
            content_str = ""
            if isinstance(msg.content, str):
                content_str = msg.content.lower()
            elif isinstance(msg.content, list):
                content_str = " ".join([str(item) for item in msg.content if isinstance(item, (str, int, float))]).lower()

            if "fiebre" in content_str or "fever" in content_str:
                fever_mentioned = True
                break

    if not fever_mentioned:
        return {"needs_clarification": False, "temp_value": temp, "clarification_text": ""}

    # 4. Verificar si ya dimos la clarificación antes
    # Buscamos en los mensajes del asistente si ya dijimos "NO es fiebre"
    for msg in messages:
        if hasattr(msg, '__class__') and msg.__class__.__name__ == "AIMessage":
            content_str = ""
            if isinstance(msg.content, str):
                content_str = msg.content.lower()

            if "no es fiebre" in content_str or "not fever" in content_str:
                # Ya dimos la clarificación antes
                debug_print(f"\n⏭️ Clarificación 'NO FIEBRE' ya fue dada anteriormente, omitiendo")
                return {"needs_clarification": False, "temp_value": temp, "clarification_text": ""}

    # 5. Generar mensaje de clarificación
    patient_name = state.get("patient_name", "su bebé")
    if patient_name == "desconocido":
        patient_name = "su bebé"

    if temp < 37.5:
        temp_category = "temperatura normal"
    elif temp < 38.0:
        temp_category = "febrícula (temperatura ligeramente elevada)"
    else:
        temp_category = "temperatura normal"

    clarification = f"""Gracias por la medición. Quiero tranquilizarle: **{temp}°C NO es fiebre**. La fiebre se define como temperatura ≥38°C. {patient_name.capitalize()} tiene {temp_category}.

Para orientarle mejor sobre qué puede estar pasando y si necesita algo, """

    debug_print(f"\n✅ CLARIFICACIÓN 'NO FIEBRE' DETECTADA:")
    debug_print(f"  Temperatura: {temp}°C (<38°C)")
    debug_print(f"  Usuario mencionó 'fiebre': Sí")
    debug_print(f"  Temperatura fue recientemente preguntada: Sí")
    debug_print(f"  No se dio clarificación previa: Sí")
    debug_print(f"  Categoría: {temp_category}")

    return {
        "needs_clarification": True,
        "temp_value": temp,
        "clarification_text": clarification
    }


def inquiry_node(state: State):
    """
    Nodo de inquiry: genera preguntas inteligentes basadas en el checklist faltante.
    Usa el checklist para guiar qué información debe recopilar.
    """
    new_state: State = {}

    history = state["messages"]
    last_message = history[-1]

    debug_print("\n" + "🏥" * 80)
    debug_print("🏥 INQUIRY NODE - INICIO")
    debug_print("=" * 80)
    debug_print(f"📨 Último mensaje: {last_message.content}")
    debug_print(f"📊 Total mensajes: {len(history)}")

    # Calcular checklist completion y red flags
    checklist_status = calculate_checklist_completion(state)
    red_flags = detect_red_flags(state)

    debug_print("\n📋 ESTADO DEL CHECKLIST:")
    debug_print(f"  Completitud: {checklist_status['score']:.0%} ({checklist_status['completed']}/{checklist_status['total']})")
    debug_print(f"  Faltantes: {', '.join(checklist_status['missing']) if checklist_status['missing'] else 'NINGUNO'}")
    if red_flags:
        debug_print(f"  🚨 Red Flags: {', '.join(red_flags)}")

    # Obtener información del estado (siempre con valores por defecto seguros)
    patient_name = state.get("patient_name", "desconocido")
    patient_age_months = state.get("patient_age_months", "desconocido")
    parent_phone = state.get("parent_phone", "desconocido")
    temperature = state.get("temperature", "desconocido")
    fever_duration = state.get("fever_duration_hours", "desconocido")
    temp_location = state.get("thermometer_location", "desconocido")
    has_thermometer = state.get("has_thermometer", "desconocido")
    can_get_thermometer = state.get("can_get_thermometer", "desconocido")

    # Nuevos campos para manejo sin termómetro
    no_thermometer_asked = state.get("no_thermometer_asked", "no")
    tactile_assessment_given = state.get("tactile_assessment_given", "no")
    tactile_fever_assessment = state.get("tactile_fever_assessment", "")

    debug_print("\n🗄️ DATOS DEL PACIENTE EN STATE:")
    debug_print(f"  Nombre: {patient_name}")
    debug_print(f"  Edad: {patient_age_months} meses")
    debug_print(f"  Temperatura: {temperature}°C ({temp_location})")
    debug_print(f"  Duración fiebre: {fever_duration} horas")
    debug_print(f"  Síntomas generales: {state.get('general_symptoms', 'desconocido')}")
    debug_print(f"  Síntomas respiratorios: {state.get('respiratory_symptoms', 'desconocido')}")

    # Generar displays legibles
    age_display = get_age_display(patient_age_months)
    missing_items_text = format_missing_items(checklist_status['missing'])

    # ========== CALCULAR LA PREGUNTA EXACTA ==========
    # Filtrar preguntas ya hechas O campos que tienen data parcial
    questions_asked = json.loads(state.get("questions_asked", "[]"))

    # OPTIMIZATION: Skip fields that already have partial info from user's natural responses
    # Check actual state values, not just checklist completion
    fields_with_data = []
    for field in checklist_status['missing']:
        # Map checklist field names to state field names
        field_mapping = {
            "edad": "patient_age_months",
            "peso": "patient_weight_kg",
            "temperatura": "temperature",
            "duracion_fiebre": "fever_duration_hours",
            "lugar_termometro": "thermometer_location",
            "medicacion_previa": "medication_given",
            "sintomas_generales": "general_symptoms",
            "sintomas_respiratorios": "respiratory_symptoms",
            "hidratacion": "hydration_status",
            "alimentacion": "feeding_status",
            "signos_alarma_visual": "visual_alarm_signs",
            "estado_vacunal": "vaccination_status",
            "antecedentes": "medical_history"
        }

        state_field = field_mapping.get(field, field)
        value = state.get(state_field, "")

        # If field has some value (even partial), note it
        if value and value not in ["desconocido", "", "0"]:
            fields_with_data.append(field)
            debug_print(f"  ℹ️ Field '{field}' has partial data: {value[:50]}...")

    remaining_missing = [
        field for field in checklist_status['missing']
        if field not in questions_asked and field not in fields_with_data
    ]

    debug_print(f"\n🔍 FILTERING QUESTIONS:")
    debug_print(f"  Original missing: {len(checklist_status['missing'])} fields")
    debug_print(f"  Already asked: {len(questions_asked)} fields")
    debug_print(f"  Have partial data: {len(fields_with_data)} fields")
    debug_print(f"  Remaining to ask: {len(remaining_missing)} fields → {remaining_missing}")
    
    # Remove duplicate log (already printed above)
    # debug_print(f"\n📋 TRACKING DE PREGUNTAS:") - REMOVED DUPLICATE
    
    next_q = get_next_question(state, remaining_missing)

    debug_print("\n❓ PREGUNTA CALCULADA:")
    debug_print(f"  Prioridad: {next_q['priority']}")
    debug_print(f"  Campo: {next_q['field']}")
    debug_print(f"  Required fields: {next_q['required_fields']}")
    debug_print(f"  Fallback values: {next_q['fallback_value']}")
    debug_print(f"  Pregunta: {next_q['question'][:100]}...")

    # ========== DYNAMIC "NO FIEBRE" CLARIFICATION ==========
    # Check if temperature was just collected and is below 38°C
    temp_str = state.get("temperature", "")
    no_fever_clarification_given = state.get("no_fever_clarification_given", "")

    try:
        temp_value = float(temp_str) if temp_str and temp_str != "desconocido" else -1.0
    except (ValueError, TypeError):
        temp_value = -1.0

    # Check if temperature was recently asked AND it's not fever AND we haven't clarified yet
    if ("temperatura" in questions_asked and
        0 < temp_value < 38.0 and
        no_fever_clarification_given != "yes"):

        # Temperature was just collected and it's NOT fever
        debug_print(f"\n⚠️ TEMPERATURE BELOW 38°C DETECTED: {temp_value}°C")
        debug_print(f"   Will add clarification to next question")

        # Determine temperature category
        if temp_value < 37.5:
            temp_category = "temperatura normal"
        else:  # 37.5 - 37.9
            temp_category = "febrícula (temperatura ligeramente elevada)"

        # Build clarification message
        clarification = f"Gracias por la información. Quiero tranquilizarle: **{temp_value}°C NO es fiebre**. La fiebre se define como temperatura ≥38°C. {patient_name.capitalize()} tiene {temp_category}.\n\nSin embargo, para hacer una evaluación completa y orientarle sobre qué puede estar pasando, "

        # Prepend clarification to next question
        original_question = next_q['question']
        next_q['question'] = clarification + original_question.lower() if original_question[0].isupper() else clarification + original_question

        debug_print(f"   ✅ Clarification added to question")
        debug_print(f"   Category: {temp_category}")

        # Mark clarification as given (will be saved to state below)
        new_state["no_fever_clarification_given"] = "yes"

    # ========== MENSAJE DE AGRADECIMIENTO CADA 4 PREGUNTAS ==========
    appreciation_message = ""
    questions_count = len(questions_asked) + 1  # +1 porque vamos a hacer una pregunta más
    
    # Cada 4 preguntas (4, 8, 12, 16...), agregar mensaje de agradecimiento
    if questions_count > 0 and questions_count % 4 == 0:
        appreciation_messages = [
            "Agradezco mucho su paciencia con todas estas preguntas. Es importante tener toda la información para orientarle de la mejor manera.",
            "Gracias por su colaboración con estas preguntas. Sé que son muchas, pero cada detalle me ayuda a darle la mejor recomendación.",
            "Le agradezco que esté respondiendo con tanta paciencia. Esta información es fundamental para hacer una evaluación completa.",
            "Muchas gracias por tomarse el tiempo de responder. Sé que son varias preguntas, pero es para asegurarme de darle la orientación más precisa."
        ]
        # Seleccionar mensaje según el número de preguntas (rotación)
        message_index = (questions_count // 4 - 1) % len(appreciation_messages)
        appreciation_message = appreciation_messages[message_index]
        debug_print(f"\n💝 MENSAJE DE AGRADECIMIENTO (pregunta #{questions_count}):")
        debug_print(f"  {appreciation_message}")
    
    debug_print("=" * 80)

    # Formatear el prompt con TODA la información
    formatted_prompt = prompt_template.format(
        # Datos del paciente
        patient_name=patient_name,
        patient_age_months=patient_age_months,
        age_display=age_display,
        parent_phone=parent_phone,
        temperature=temperature,
        temp_location=temp_location,
        fever_duration=fever_duration,

        # Checklist status
        checklist_score=int(checklist_status['score'] * 100),
        completed=checklist_status['completed'],
        total=checklist_status['total'],
        missing_items_text=missing_items_text,

        # Pregunta calculada
        next_question=next_q['question'],
        priority_level=next_q['priority'],
        next_field=next_q['field'],
        
        # Mensaje de agradecimiento
        appreciation_message=appreciation_message,
        questions_count=questions_count,

        # Mensajes
        last_message=last_message.content,
        history_length = len(history),
        history=format_history(history),
    )

    # Debug: Mostrar el prompt formateado
    debug_print("\n🤖 PREPARANDO PROMPT PARA LLM:")
    debug_print(f"  Variables inyectadas en el template:")
    debug_print(f"    - patient_name: {patient_name}")
    debug_print(f"    - patient_age_months: {patient_age_months}")
    debug_print(f"    - age_display: {age_display}")
    debug_print(f"    - temperature: {temperature}")
    debug_print(f"    - checklist_score: {int(checklist_status['score'] * 100)}%")
    debug_print(f"    - next_question: {next_q['question'][:50]}...")
    debug_print(f"    - priority_level: {next_q['priority']}")
    debug_print("=" * 80)
    debug_print("\n📄 PROMPT FORMATEADO (primeros 1500 caracteres):")
    debug_print(formatted_prompt[:1500])
    debug_print("\n... [prompt continúa] ...")
    debug_print("=" * 80)

    # Invocar el LLM con el prompt contextual
    debug_print("\n🤖 Invocando LLM para generar pregunta...")
    ai_message = llm.invoke([("system", formatted_prompt), ("user", last_message.content)])

    debug_print(f"\n💬 RESPUESTA DEL LLM (pregunta generada):")
    debug_print(f"  {ai_message.content}")
    debug_print("=" * 80)

    new_state["messages"] = [ai_message]

    # ========== GUARDAR CONTEXTO DE PREGUNTA PARA RECEPTOR (NUEVO) ==========
    new_state["last_inquiry_question"] = next_q["question"]
    new_state["expected_fields"] = json.dumps(next_q["required_fields"])
    new_state["fallback_values"] = json.dumps(next_q["fallback_value"])
    
    # Marcar pregunta como hecha
    if next_q["field"] not in questions_asked:
        questions_asked.append(next_q["field"])
    new_state["questions_asked"] = json.dumps(questions_asked)
    
    debug_print("\n📦 CONTEXTO GUARDADO PARA RECEPTOR:")
    debug_print(f"  last_inquiry_question: {next_q['question'][:50]}...")
    debug_print(f"  expected_fields: {next_q['required_fields']}")
    debug_print(f"  fallback_values: {next_q['fallback_value']}")
    debug_print(f"  questions_asked: {questions_asked}")
    
    # Actualizar red_flags_detected SOLO si se detectaron nuevos red flags
    # NO sobrescribir con vacío para evitar borrar red flags detectados anteriormente
    if red_flags:
        new_state["red_flags_detected"] = ", ".join(red_flags)
        debug_print(f"\n⚠️ RED FLAGS DETECTADOS: {new_state['red_flags_detected']}")

    # Actualizar completeness_score y missing_items
    new_state["completeness_score"] = f"{checklist_status['score']:.2f}"
    new_state["missing_items"] = ", ".join(checklist_status['missing'])

    debug_print("\n📦 ESTADO ACTUALIZADO POR INQUIRY:")
    debug_print(f"  red_flags_detected: {new_state.get('red_flags_detected', '(sin cambios)')}")
    debug_print(f"  completeness_score: {new_state['completeness_score']}")
    debug_print(f"  missing_items: {new_state['missing_items']}")
    debug_print("  messages: [AI response agregado al historial]")
    debug_print("=" * 80 + "\n")

    return new_state
