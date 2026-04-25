from langgraph.graph import MessagesState


class State(MessagesState):
    """
    Estado para triaje de fiebre pediátrica.
    TODOS los campos son strings para simplificar manejo y serialización.
    Los campos pueden estar vacíos ("") o "desconocido" si no se han recopilado.
    """

    # ========== DATOS CRÍTICOS INICIALES (OBLIGATORIOS) ==========
    patient_name: str  # Nombre del niño/a
    patient_birthdate: str  # Fecha de nacimiento (formato: "DD/MM/YYYY" o "YYYY-MM-DD")
    patient_age_months: str  # Edad en meses (ej: "24", "36") - CALCULADA AUTOMATICAMENTE
    patient_weight_kg: str  # Peso en kilogramos (ej: "12", "15.5")
    parent_phone: str  # Teléfono de contacto
    temperature: str  # Temperatura en °C (ej: "38.5") o "no_medida" si no tiene termómetro
    fever_start_datetime: str  # Fecha/hora inicio fiebre en formato ISO (YYYY-MM-DD HH:MM) - CALCULADA POR LLM
    fever_duration_hours: str  # Duración en horas (ej: "24", "48", "72+") - CALCULADA AUTOMATICAMENTE desde fever_start_datetime
    thermometer_location: str  # "axilar", "rectal", "oral", "frontal"
    has_thermometer: str  # "si", "no", "desconocido" - si tiene termómetro disponible
    can_get_thermometer: str  # "si", "no", "desconocido" - si puede conseguir uno

    # ========== MANEJO SIN TERMÓMETRO (NUEVO) ==========
    no_thermometer_asked: str  # "si", "no" - si ya preguntamos por conseguir termómetro
    tactile_assessment_given: str  # "si", "no" - si ya dimos guía táctil de evaluación
    tactile_fever_assessment: str  # "febricula", "fiebre_moderada", "fiebre_alta" - evaluación táctil

    # ========== MEDICACIÓN Y MANEJO PREVIO ==========
    home_measures_taken: str  # "baño, líquidos, ropa ligera" o descripción libre
    medication_given: str  # "paracetamol 250mg hace 4h, ibuprofeno..." o "ninguno"
    recent_antibiotics: str  # "amoxicilina hace 3 días" o "no"

    # ========== SÍNTOMAS ASOCIADOS (formato estructurado en strings) ==========
    # Formato esperado: "clave:valor, clave:valor"
    # Ejemplo: "rechaza_alimento:si, vomitos:no, cefalea:si, decaido:si, juega:no"
    general_symptoms: str  # rechaza_alimento, vomitos, cefalea, decaido, juega
    respiratory_symptoms: str  # dificultad_respirar, tos, tipo_tos
    visual_alarm_signs: str  # morado, rojo, verde, otros
    
    # ========== HIDRATACIÓN Y ALIMENTACIÓN ==========
    hydration_status: str  # "bebe_normal:si, rechaza_liquidos:no, orina_normal:si" o descripción
    feeding_status: str  # "come_normal:si, rechaza_alimento:no, vomita:no" o descripción

    # ========== SÍNTOMAS ADICIONALES (libres) ==========
    other_symptoms: str  # Cualquier otro síntoma mencionado libremente

    # ========== CONTEXTO EPIDEMIOLÓGICO ==========
    epidemiological_context: str  # "familia_enferma:si, guarderia:si, viajes:no"

    # ========== ANTECEDENTES CRÍTICOS ==========
    vaccination_status: str  # "completo", "incompleto", "desconocido"
    medical_history: str  # "ITU_previas:no, inmunodeficiencia:no, otras:no" o descripción

    # ========== TRACKING DE CHECKLIST ==========
    checklist_completion: str  # JSON string: '{"edad":true, "temp":true, ...}'
    completeness_score: str  # "0.75" (75% del checklist completo)
    missing_items: str  # "duracion_fiebre, estado_vacunal, sintomas_respiratorios"

    # ========== RED FLAGS Y RIESGO ==========
    red_flags_detected: str  # "menor_3m_fiebre_alta, dificultad_respiratoria" o ""
    risk_category: str  # "bajo", "medio", "alto", "critico"

    # ========== URGENCIA INMEDIATA (TRIAJE URGENTE) ==========
    urgency_criteria_met: str  # "yes" si temp>38 AND age<3mo, "" si no aplica
    urgency_recommendation_given: str  # "yes" después del primer mensaje urgente, "" antes

    # ========== RECOMENDACIÓN ==========
    recommended_action: str  # "home_care", "consult_24h", "urgent_ed", "immediate_911"
    pediatrician_notes: str  # Notas contextuales entre nodos

    # ========== RECOMENDACIÓN INTERACTIVA ==========
    recommendation_section: str  # "0" (inicial), "1" (evaluación dada), "2" (medicamentos dados), "3" (completo)
    recommendation_section_1: str  # Texto de sección 1: Evaluación inicial
    recommendation_section_2: str  # Texto de sección 2: Medicamentos y cuidados
    recommendation_section_3: str  # Texto de sección 3: Signos de alarma y seguimiento

    # ========== TRACKING DE FLUJO PREGUNTA-EXTRACCIÓN (NUEVO) ==========
    last_inquiry_question: str  # Última pregunta hecha por INQUIRY
    expected_fields: str  # JSON: campos que RECEPTOR debe extraer obligatoriamente
    fallback_values: str  # JSON: valores por defecto si RECEPTOR no extrae
    questions_asked: str  # JSON: lista de campos ya preguntados (evita repetir)
    no_fever_clarification_given: str  # "yes" si ya dimos la aclaración de "NO es fiebre"

    # ========== CONTEXTO DE LA FIEBRE (NUEVO) ==========
    # primary | trauma | base_disease | post_vaccine | post_surgery | unknown
    fever_context: str

    # ========== ROUTER CONVERSACIONAL (conversation_manager) ==========
    last_intent: str  # data | emotional | user_question | evasion | mixed | closing
    detected_emotion: str  # panic | fear | anxiety | frustration | skepticism | exhaustion | gratitude | neutral
    pending_user_question: str  # the parent's verbatim question, if any
    short_acknowledgement: str  # 1-line warm seed for empathy / answer branches
    recommendation_with_partial_data: str  # "yes" if checklist exhausted but data thin