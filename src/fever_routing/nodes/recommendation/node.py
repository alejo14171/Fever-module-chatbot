from fever_routing.nodes.recommendation.prompt import (
    prompt_template, get_fever_duration_display, safe_display,
    calculate_acetaminofen_dose, calculate_ibuprofen_dose
)
from fever_routing.state import State
from fever_routing.routes.triage.route import detect_red_flags
from fever_routing.nodes.inquiry.prompt import get_age_display
from fever_routing.utils.logging import debug_print
from fever_routing.utils import ModelFactory
from langchain_core.messages import AIMessage
import json

llm = ModelFactory.get_recommendation_model()


# ========== FUNCIONES HELPER ==========

def detect_current_medication(medication_given: str) -> dict:
    """
    Detecta si el paciente ya está tomando algún medicamento.
    
    Args:
        medication_given: Campo de medicación del estado
        
    Returns:
        dict con:
            - taking_medication: bool
            - medication_name: str (nombre del medicamento)
    """
    if not medication_given or medication_given.lower() in ["no", "ninguno", "nada", "desconocido", "ninguno reportado"]:
        return {
            "taking_medication": False,
            "medication_name": ""
        }
    
    return {
        "taking_medication": True,
        "medication_name": medication_given
    }


def extract_user_message(history: list) -> str:
    """
    Extrae el último mensaje del usuario del historial, manejando diferentes formatos.
    
    Args:
        history: Lista de mensajes
        
    Returns:
        str: Contenido del último mensaje del usuario
    """
    last_user_message = ""
    
    for msg in reversed(history):
        if hasattr(msg, '__class__') and msg.__class__.__name__ == "HumanMessage":
            # Manejar diferentes formatos de contenido
            if isinstance(msg.content, str):
                last_user_message = msg.content
            elif isinstance(msg.content, list):
                # Buscar texto en lista de diccionarios
                for item in msg.content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        last_user_message = item.get('text', '')
                        break
                # Si no se encontró, usar string representation
                if not last_user_message:
                    last_user_message = str(msg.content)
            else:
                last_user_message = str(msg.content)
            break
    
    return last_user_message


def build_decision_prompt(user_message: str, current_section: str, sections: dict) -> str:
    """
    Construye el prompt para que el LLM decida si continuar o responder pregunta.
    
    Args:
        user_message: Mensaje del usuario
        current_section: "1" o "2"
        sections: Diccionario con section_1, section_2, section_3
        
    Returns:
        str: Prompt formateado
    """
    section_1 = sections.get("section_1", "")
    section_2 = sections.get("section_2", "")
    
    if current_section == "1":
        context = f"""SECCIÓN 1 ENVIADA (Evaluación inicial):
{section_1}"""
    else:  # current_section == "2"
        context = f"""SECCIONES ENVIADAS:
1) Evaluación inicial: {section_1[:300]}...

2) Indicaciones de tratamiento: {section_2[:300]}..."""
    
    prompt = f"""# ROL
Eres un PEDIATRA CERTIFICADO en una conversación de seguimiento.

# CONTEXTO
Has proporcionado una evaluación médica dividida en secciones.
Acabas de enviar la sección {current_section}.

{context}

# MENSAJE DEL PADRE/MADRE:
"{user_message}"

# TU TAREA
Analiza el mensaje y determina:

**¿Es una CONFIRMACIÓN SIMPLE para continuar?**
- Ejemplos: "ok", "sí", "adelante", "entendido", "no tengo preguntas", "continúa"
- Acción: Continuar con siguiente sección

**¿Es una PREGUNTA o COMENTARIO específico?**
- Ejemplos: "¿cada cuántas horas?", "¿puedo darle los dos medicamentos?", "pero si vomita ¿qué hago?"
- Acción: Responder específicamente antes de continuar

# FORMATO DE RESPUESTA

Responde ÚNICAMENTE en formato JSON válido (sin markdown, sin backticks):

{{"action": "continue", "response": ""}}

O si es pregunta:

{{"action": "answer_question", "response": "[Tu respuesta breve y directa (2-3 frases máximo)]"}}

IMPORTANTE: 
- Responde SOLO con el JSON válido, nada más
- Si el mensaje es ambiguo o poco claro, asume que es confirmación ("continue")
- Las respuestas deben ser breves, directas y profesionales
- No uses formato markdown en la respuesta"""

    return prompt


def ask_llm_to_decide(state: State, user_message: str, current_section: str, sections: dict) -> dict:
    """
    Pregunta al LLM si debe continuar con siguiente sección o responder pregunta.
    
    Args:
        state: Estado actual
        user_message: Mensaje del usuario
        current_section: "1" o "2"
        sections: Diccionario con las secciones
        
    Returns:
        dict: {"action": "continue" | "answer_question", "response": "..."}
    """
    debug_print(f"\n🤖 Preguntando al LLM qué hacer con mensaje del usuario...")
    debug_print(f"  Sección actual: {current_section}")
    debug_print(f"  Mensaje usuario: '{user_message[:100]}...'")
    
    # Construir prompt
    prompt = build_decision_prompt(user_message, current_section, sections)
    
    # Invocar LLM
    try:
        response = llm.invoke([
            ("system", prompt),
            ("user", user_message)
        ])
        
        debug_print(f"\n📋 Respuesta LLM raw: {response.content[:200]}...")
        
        # Limpiar respuesta (eliminar markdown si existe)
        content = response.content.strip()
        if content.startswith("```"):
            # Eliminar bloques de código markdown
            lines = content.split("\n")
            content = "\n".join([l for l in lines if not l.startswith("```")])
            content = content.strip()
        
        # Parsear JSON
        decision = json.loads(content)
        
        debug_print(f"  ✅ Decisión: {decision['action']}")
        if decision['action'] == 'answer_question':
            debug_print(f"  💬 Respuesta: {decision['response'][:100]}...")
        
        return decision
        
    except json.JSONDecodeError as e:
        debug_print(f"  ⚠️ Error parseando JSON: {e}")
        debug_print(f"  🔄 Asumiendo que la respuesta completa es una respuesta a pregunta")
        # Fallback: si no es JSON válido, asumir que es una respuesta
        return {
            "action": "answer_question",
            "response": response.content
        }
    except Exception as e:
        debug_print(f"  ❌ Error invocando LLM: {e}")
        # Fallback seguro: continuar
        return {
            "action": "continue",
            "response": ""
        }


def parse_recommendation_sections(full_response: str) -> dict:
    """
    Parsea la recomendación completa en 3 secciones usando los separadores.

    Returns:
        dict con keys: section_1, section_2, section_3
    """
    # Los separadores que usa el LLM
    separator_1 = "##########"
    separator_2 = "%%%%%%%%%%"

    sections = {
        "section_1": "",
        "section_2": "",
        "section_3": ""
    }

    try:
        # Dividir por el primer separador (##########)
        if separator_1 in full_response:
            parts = full_response.split(separator_1, 1)
            sections["section_1"] = parts[0].strip()
            remaining = parts[1] if len(parts) > 1 else ""
        else:
            # Si no hay separadores, toda la respuesta es sección 1
            sections["section_1"] = full_response.strip()
            return sections

        # Dividir por el segundo separador (%%%%%%%%%%)
        if separator_2 in remaining:
            parts = remaining.split(separator_2, 1)
            sections["section_2"] = parts[0].strip()
            remaining = parts[1] if len(parts) > 1 else ""
        else:
            sections["section_2"] = remaining.strip()
            return sections

        # El resto es la sección 3 (puede tener otro separador al final)
        if separator_2 in remaining:
            parts = remaining.split(separator_2, 1)
            sections["section_3"] = parts[0].strip()
        else:
            sections["section_3"] = remaining.strip()

    except Exception as e:
        debug_print(f"⚠️ Error parseando secciones: {e}")
        # Fallback: toda la respuesta como sección 1
        sections["section_1"] = full_response.strip()

    return sections


def recommendation_node(state: State):
    """
    Nodo de recommendation: genera evaluación pediátrica completa y recomendaciones.
    Actúa como un pediatra certificado proporcionando assessment final de forma INTERACTIVA.

    Primera vez (section=0): Genera todas las secciones, retorna sección 1 + pregunta
    Segunda vez (section=1): Retorna sección 2 + pregunta
    Tercera vez (section=2): Retorna sección 3 (final)
    """
    new_state: State = {}

    history = state["messages"]
    current_section = state.get("recommendation_section", "0")

    debug_print("\n" + "🩺" * 80)
    debug_print("🩺 RECOMMENDATION NODE - INICIO")
    debug_print("=" * 80)
    debug_print(f"📊 Total mensajes en conversación: {len(history)}")
    debug_print(f"📍 Sección actual: {current_section}")

    # Detectar red flags para condicionar el tipo de recomendación
    red_flags = detect_red_flags(state)

    debug_print("\n🚨 ANÁLISIS DE RIESGO:")
    if red_flags:
        debug_print(f"  ⚠️ RED FLAGS DETECTADOS: {', '.join(red_flags)}")
        debug_print(f"  ⚠️ Tipo de recomendación: URGENTE (assessment completo con signos de alarma)")
        debug_print(f"  ℹ️ Se completó el assessment antes de recomendar para tener contexto completo")
    else:
        debug_print(f"  ✅ Sin red flags detectados")
        debug_print(f"  ℹ️ Tipo de recomendación: Evaluación estándar (prioritario/ambulatorio)")

    # Obtener todos los datos del estado (siempre con defaults seguros)
    patient_name = safe_display(state.get("patient_name", ""), "No especificado")
    patient_age_months = safe_display(state.get("patient_age_months", ""), "desconocido")
    patient_weight_kg = safe_display(state.get("patient_weight_kg", ""), "desconocido")
    parent_phone = safe_display(state.get("parent_phone", ""), "No proporcionado")
    temperature = safe_display(state.get("temperature", ""), "No medida")
    thermometer_location = safe_display(state.get("thermometer_location", ""), "no especificado")
    fever_duration = safe_display(state.get("fever_duration_hours", ""), "desconocida")
    has_thermometer = safe_display(state.get("has_thermometer", ""), "desconocido")
    can_get_thermometer = safe_display(state.get("can_get_thermometer", ""), "desconocido")

    # Manejo de evaluación táctil cuando no hay termómetro
    tactile_fever_assessment = state.get("tactile_fever_assessment", "")
    if tactile_fever_assessment and temperature == "No medida":
        # Mapear evaluación táctil a temperatura estimada
        tactile_temp_map = {
            "febricula": "37.5-38",
            "fiebre_moderada": "38-39",
            "fiebre_alta": "39-40"
        }
        temperature = f"{tactile_temp_map.get(tactile_fever_assessment, '38')} (evaluación táctil)"
        thermometer_location = "evaluación táctil"
        debug_print(f"  ℹ️ Usando evaluación táctil: {tactile_fever_assessment} → {temperature}")
    elif tactile_fever_assessment:
        debug_print(f"  ℹ️ Evaluación táctil disponible pero ya hay temperatura medida: {temperature}")

    # Medicación y manejo
    medication_given = safe_display(state.get("medication_given", ""), "Ninguno reportado")
    home_measures = safe_display(state.get("home_measures_taken", ""), "Ninguna reportada")
    antibiotics = safe_display(state.get("recent_antibiotics", ""), "No")
    
    # Detectar si ya está tomando medicación
    current_medication = detect_current_medication(state.get("medication_given", ""))
    debug_print(f"  🔍 Detección medicación:")
    debug_print(f"    - Tomando medicación: {current_medication['taking_medication']}")
    if current_medication['taking_medication']:
        debug_print(f"    - Medicamento: {current_medication['medication_name']}")

    # Síntomas
    general_symptoms = safe_display(state.get("general_symptoms", ""), "No evaluado")
    respiratory_symptoms = safe_display(state.get("respiratory_symptoms", ""), "No evaluado")
    visual_alarm_signs = safe_display(state.get("visual_alarm_signs", ""), "No evaluado")
    other_symptoms = safe_display(state.get("other_symptoms", ""), "Ninguno adicional")

    # Contexto y antecedentes
    epidemiological = safe_display(state.get("epidemiological_context", ""), "No especificado")
    vaccination_status = safe_display(state.get("vaccination_status", ""), "No confirmado")
    medical_history = safe_display(state.get("medical_history", ""), "No especificado")

    debug_print("\n🗄️ DATOS COMPLETOS DEL PACIENTE (desde state):")
    debug_print(f"  Nombre: {patient_name}")
    debug_print(f"  Edad: {patient_age_months} meses")
    debug_print(f"  Peso: {patient_weight_kg} kg")
    debug_print(f"  Teléfono: {parent_phone}")
    debug_print(f"  Temperatura: {temperature}°C ({thermometer_location})")
    debug_print(f"  Duración fiebre: {fever_duration} horas")
    debug_print(f"  Medicación: {medication_given}")
    debug_print(f"  Medidas caseras: {home_measures}")
    debug_print(f"  Síntomas generales: {general_symptoms}")
    debug_print(f"  Síntomas respiratorios: {respiratory_symptoms}")
    debug_print(f"  Signos visuales: {visual_alarm_signs}")
    debug_print(f"  Vacunación: {vaccination_status}")
    debug_print(f"  Antecedentes: {medical_history}")

    # Generar displays legibles
    age_display = get_age_display(patient_age_months)
    fever_duration_display = get_fever_duration_display(fever_duration)

    # Calcular dosis de medicamentos
    acetaminofen_dose = calculate_acetaminofen_dose(patient_weight_kg, patient_age_months)
    ibuprofen_dose = calculate_ibuprofen_dose(patient_weight_kg, patient_age_months)
    
    debug_print("\n💊 CÁLCULO DE DOSIS DE MEDICAMENTOS:")
    if not acetaminofen_dose["error"]:
        debug_print(f"  Paracetamol (Acetaminofen):")
        debug_print(f"    - Dosis por toma: {acetaminofen_dose['dose_mg']} mg")
        debug_print(f"    - En suspensión (160mg/5ml): {acetaminofen_dose['dose_ml_suspension']} ml")
        debug_print(f"    - En gotas (100mg/ml): {acetaminofen_dose['dose_ml_drops']} ml")
        debug_print(f"    - Cada {acetaminofen_dose['interval_hours']} horas")
        debug_print(f"    - Máximo diario: {acetaminofen_dose['max_daily_mg']} mg")
        if acetaminofen_dose["warning"]:
            debug_print(f"    {acetaminofen_dose['warning']}")
    else:
        debug_print(f"  Paracetamol: {acetaminofen_dose['warning']}")
    
    if not ibuprofen_dose["error"] and not ibuprofen_dose["contraindicated"]:
        debug_print(f"  Ibuprofeno:")
        debug_print(f"    - Dosis por toma: {ibuprofen_dose['dose_mg']} mg")
        debug_print(f"    - En suspensión (100mg/5ml): {ibuprofen_dose['dose_ml_suspension']} ml")
        debug_print(f"    - Cada {ibuprofen_dose['interval_hours']} horas")
        debug_print(f"    - Máximo diario: {ibuprofen_dose['max_daily_mg']} mg")
    elif ibuprofen_dose["contraindicated"]:
        debug_print(f"  Ibuprofeno: {ibuprofen_dose['warning']}")
    else:
        debug_print(f"  Ibuprofeno: {ibuprofen_dose['warning']}")
    debug_print("=" * 80)

    # Formatear información de medicación
    medication_info = f"- Medicamentos: {medication_given}\n- Medidas caseras: {home_measures}\n- Antibióticos recientes: {antibiotics}"

    # Formatear red flags
    red_flags_display = ""
    if red_flags:
        red_flag_descriptions = {
            "menor_3m_fiebre_alta": "⚠️ Menor de 3 meses con fiebre ≥38°C (CRITERIO DE ALTO RIESGO)",
            "3_6m_fiebre_muy_alta": "⚠️ Lactante 3-6 meses con fiebre ≥39°C",
            "fiebre_mayor_40": "⚠️ Fiebre >40°C",
            "decaimiento_severo": "⚠️ Decaimiento severo reportado",
            "letargo_posible": "⚠️ Posible letargo (no juega + decaído)",
            "dificultad_respiratoria_severa": "🚨 Dificultad respiratoria severa",
            "alteracion_coloracion_piel": "⚠️ Alteración de coloración de piel",
            "rash_requiere_evaluacion": "⚠️ Rash/erupciones que requieren evaluación",
            "convulsiones": "🚨 CONVULSIONES reportadas",
            "convulsiones_posibles": "⚠️ Posibles convulsiones/temblores",
            "rigidez_nuca": "🚨 Rigidez de nuca",
            "letargo_extremo": "🚨 Letargo extremo/no responde",
            "manifestaciones_sangrado": "🚨 Manifestaciones de sangrado",
            "rash_no_blanqueable": "🚨 Rash que NO blanquea (petequias/púrpura)",
            "quejido_respiratorio": "🚨 Quejido respiratorio",
        }
        red_flags_display = "\n".join([red_flag_descriptions.get(flag, f"- {flag}") for flag in red_flags])

    # Formatear el prompt con TODA la información
    formatted_prompt = prompt_template.format(
        # Datos demográficos
        patient_name=patient_name,
        patient_age_months=patient_age_months,
        patient_weight_kg=patient_weight_kg,
        age_display=age_display,
        parent_phone=parent_phone,

        # Datos de fiebre
        temperature=temperature,
        thermometer_location=thermometer_location,
        fever_duration=fever_duration,
        fever_duration_display=fever_duration_display,
        has_thermometer=has_thermometer,
        can_get_thermometer=can_get_thermometer,
        tactile_fever_assessment=tactile_fever_assessment,

        # Medicación
        medication_info=medication_info,
        current_medication_info=current_medication,

        # Dosis calculadas
        acetaminofen_dose=acetaminofen_dose,
        ibuprofen_dose=ibuprofen_dose,

        # Síntomas
        general_symptoms_display=general_symptoms,
        respiratory_symptoms_display=respiratory_symptoms,
        visual_alarm_signs_display=visual_alarm_signs,
        other_symptoms=other_symptoms,

        # Contexto y antecedentes
        epidemiological_info=epidemiological,
        vaccination_status=vaccination_status,
        medical_history_display=medical_history,

        # Red flags
        red_flags=red_flags,
        red_flags_display=red_flags_display,
    )

    debug_print("\n🤖 PREPARANDO PROMPT FINAL PARA LLM:")
    debug_print(f"  Variables clave inyectadas:")
    debug_print(f"    - Paciente: {patient_name}, {age_display}")
    debug_print(f"    - Temperatura: {temperature}°C ({thermometer_location})")
    debug_print(f"    - Duración: {fever_duration_display}")
    debug_print(f"    - Red flags: {', '.join(red_flags) if red_flags else 'Ninguno'}")
    debug_print("=" * 80)

    # ========== LÓGICA INTERACTIVA POR SECCIONES ==========

    # CASO 1: Primera vez - Generar todas las secciones
    if current_section in ["0", ""]:
        debug_print("\n📄 PROMPT FORMATEADO (primeros 2000 caracteres):")
        debug_print(formatted_prompt[:2000])
        debug_print("\n... [prompt continúa con instrucciones de evaluación] ...")
        debug_print("=" * 80)

        debug_print("\n🤖 Invocando LLM para generar evaluación completa (todas las secciones)...")
        ai_response = llm.invoke([
            ("system", formatted_prompt),
            ("user", "Por favor, genera la evaluación pediátrica completa y recomendaciones basadas en la información proporcionada.")
        ])

        full_response = ai_response.content
        debug_print(f"\n💬 RECOMENDACIÓN COMPLETA GENERADA ({len(full_response)} caracteres)")
        debug_print("=" * 80)

        # Parsear las 3 secciones
        sections = parse_recommendation_sections(full_response)
        debug_print("\n📦 SECCIONES PARSEADAS:")
        debug_print(f"  Sección 1: {len(sections['section_1'])} caracteres")
        debug_print(f"  Sección 2: {len(sections['section_2'])} caracteres")
        debug_print(f"  Sección 3: {len(sections['section_3'])} caracteres")

        # Guardar secciones en el estado
        new_state["recommendation_section_1"] = sections["section_1"]
        new_state["recommendation_section_2"] = sections["section_2"]
        new_state["recommendation_section_3"] = sections["section_3"]

        # Preparar respuesta con sección 1 + pregunta adaptada según si hay fiebre o no
        # Check if temperature is below 38°C (no fever case)
        temp_str = state.get("temperature", "")
        try:
            temp_value = float(temp_str) if temp_str and temp_str != "desconocido" else 38.0
        except (ValueError, TypeError):
            temp_value = 38.0

        # Determine appropriate follow-up question
        if temp_value < 38.0:
            # NO FEVER case - ask about management recommendations
            follow_up_question = "¿Tienes preguntas sobre esto o pasamos a hablar de cómo manejar esta situación y cuándo consultar?"
            debug_print(f"  ℹ️ NO FEVER case detected ({temp_value}°C) - using non-fever follow-up question")
        else:
            # FEVER case - ask about fever medication
            follow_up_question = "¿Tienes preguntas sobre esto o pasamos a mis recomendaciones de qué deberías darle para la fiebre?"
            debug_print(f"  ℹ️ FEVER case detected ({temp_value}°C) - using standard follow-up question")

        section_1_with_question = (
            f"{sections['section_1']}\n\n"
            f"{follow_up_question}"
        )

        ai_message = AIMessage(content=section_1_with_question)
        new_state["messages"] = [ai_message]
        new_state["recommendation_section"] = "1"

        debug_print("\n✅ Sección 1 enviada con pregunta")
        debug_print(f"  Contenido: {section_1_with_question[:200]}...")

    # CASO 2: Segunda interacción - LLM decide si continuar o responder
    elif current_section == "1":
        debug_print("\n📍 Usuario respondió después de sección 1...")

        # Obtener el último mensaje del usuario
        last_user_message = extract_user_message(history)
        debug_print(f"  Último mensaje: '{last_user_message[:100]}...'")

        # Preparar contexto de secciones
        sections = {
            "section_1": state.get("recommendation_section_1", ""),
            "section_2": state.get("recommendation_section_2", ""),
            "section_3": state.get("recommendation_section_3", "")
        }

        # Preguntar al LLM qué hacer
        decision = ask_llm_to_decide(state, last_user_message, "1", sections)

        if decision["action"] == "continue":
            debug_print("  ✅ LLM decidió: CONTINUAR con sección 2")

            section_2 = sections["section_2"]
            if not section_2:
                debug_print("⚠️ Sección 2 no encontrada en estado, regenerando...")
                ai_response = llm.invoke([
                    ("system", formatted_prompt),
                    ("user", "Por favor, genera la evaluación pediátrica completa y recomendaciones basadas en la información proporcionada.")
                ])
                parsed_sections = parse_recommendation_sections(ai_response.content)
                section_2 = parsed_sections["section_2"]

            # Preparar respuesta con sección 2 + pregunta
            section_2_with_question = (
                f"{section_2}\n\n"
                f"¿Queda claro esto para pasar a advertencias?"
            )

            ai_message = AIMessage(content=section_2_with_question)
            new_state["messages"] = [ai_message]
            new_state["recommendation_section"] = "2"

            debug_print("\n✅ Sección 2 enviada con pregunta")
            debug_print(f"  Contenido: {section_2_with_question[:200]}...")

        else:
            debug_print("  ❓ LLM decidió: RESPONDER PREGUNTA")

            # Usar la respuesta del LLM
            response_content = decision["response"]
            
            # Agregar pregunta al final si no la tiene
            if not any(word in response_content.lower() for word in ["¿", "pasamos", "continuar", "siguiente"]):
                response_content += "\n\n¿Quedó claro? ¿Pasamos a las recomendaciones de tratamiento?"

            ai_message = AIMessage(content=response_content)
            new_state["messages"] = [ai_message]
            # NO cambiar recommendation_section, mantener en "1" para que vuelva aquí

            debug_print("\n✅ Respuesta a pregunta enviada")
            debug_print(f"  Contenido: {response_content[:200]}...")

    # CASO 3: Tercera interacción - LLM decide si continuar o responder
    elif current_section == "2":
        debug_print("\n📍 Usuario respondió después de sección 2...")

        # Obtener el último mensaje del usuario
        last_user_message = extract_user_message(history)
        debug_print(f"  Último mensaje: '{last_user_message[:100]}...'")

        # Preparar contexto de secciones
        sections = {
            "section_1": state.get("recommendation_section_1", ""),
            "section_2": state.get("recommendation_section_2", ""),
            "section_3": state.get("recommendation_section_3", "")
        }

        # Preguntar al LLM qué hacer
        decision = ask_llm_to_decide(state, last_user_message, "2", sections)

        if decision["action"] == "continue":
            debug_print("  ✅ LLM decidió: CONTINUAR con sección 3 (FINAL)")

            section_3 = sections["section_3"]
            if not section_3:
                debug_print("⚠️ Sección 3 no encontrada en estado, regenerando...")
                ai_response = llm.invoke([
                    ("system", formatted_prompt),
                    ("user", "Por favor, genera la evaluación pediátrica completa y recomendaciones basadas en la información proporcionada.")
                ])
                parsed_sections = parse_recommendation_sections(ai_response.content)
                section_3 = parsed_sections["section_3"]

            # Sección 3 es final, sin pregunta
            ai_message = AIMessage(content=section_3)
            new_state["messages"] = [ai_message]
            new_state["recommendation_section"] = "3"

            debug_print("\n✅ Sección 3 enviada (FINAL)")
            debug_print(f"  Contenido: {section_3[:200]}...")

        else:
            debug_print("  ❓ LLM decidió: RESPONDER PREGUNTA")

            # Usar la respuesta del LLM
            response_content = decision["response"]
            
            # Agregar pregunta al final si no la tiene
            if not any(word in response_content.lower() for word in ["¿", "pasamos", "continuar", "siguiente"]):
                response_content += "\n\n¿Quedó claro? ¿Pasamos a los signos de alarma y seguimiento?"

            ai_message = AIMessage(content=response_content)
            new_state["messages"] = [ai_message]
            # NO cambiar recommendation_section, mantener en "2" para que vuelva aquí

            debug_print("\n✅ Respuesta a pregunta enviada")
            debug_print(f"  Contenido: {response_content[:200]}...")

    # CASO 4: Sección 3 (final) - Responder preguntas adicionales
    elif current_section == "3":
        debug_print("\n📍 Usuario respondió después de sección 3 (final)...")

        # Obtener el último mensaje del usuario
        last_user_message = extract_user_message(history)
        debug_print(f"  Último mensaje: '{last_user_message[:100]}...'")

        # Preparar contexto completo de todas las secciones
        sections = {
            "section_1": state.get("recommendation_section_1", ""),
            "section_2": state.get("recommendation_section_2", ""),
            "section_3": state.get("recommendation_section_3", "")
        }

        # Crear prompt para responder con contexto completo
        final_question_prompt = f"""Eres un PEDIATRA CERTIFICADO respondiendo una pregunta final del paciente {patient_name} ({age_display}, {patient_weight_kg} kg).

CONTEXTO - Ya le diste la evaluación completa:
1) Evaluación inicial: {sections['section_1'][:300]}...
2) Recomendaciones de tratamiento: {sections['section_2'][:300]}...
3) Signos de alarma y seguimiento: {sections['section_3'][:300]}...

PREGUNTA/COMENTARIO DEL PADRE:
{last_user_message}

TU TAREA:
Responde de forma breve, directa y profesional a su pregunta específica. Puedes referenciar cualquier parte de la evaluación que ya diste.

IMPORTANTE:
- Si pregunta sobre dosis: Acetaminofen {acetaminofen_dose.get('dose_ml_suspension', 'N/A')}ml cada {acetaminofen_dose.get('interval_hours', 6)}h
- Si pregunta por ibuprofeno: {ibuprofen_dose.get('dose_ml_suspension', 'N/A')}ml cada {ibuprofen_dose.get('interval_hours', 8)}h (solo >6 meses)
- Si expresa agradecimiento, responde cordialmente y recuérdale que ante cualquier duda o emergencia debe consultar
- Mantén respuestas breves (2-4 frases)"""

        debug_print("\n🤖 Generando respuesta final...")
        ai_response = llm.invoke([
            ("system", final_question_prompt),
            ("user", last_user_message)
        ])

        ai_message = AIMessage(content=ai_response.content)
        new_state["messages"] = [ai_message]
        new_state["recommendation_section"] = "3"  # Mantener en 3

        debug_print("\n✅ Respuesta final enviada")
        debug_print(f"  Contenido: {ai_response.content[:200]}...")

    # ========== ACTUALIZAR CAMPOS FINALES ==========

    # Actualizar campos finales del estado
    new_state["red_flags_detected"] = ", ".join(red_flags) if red_flags else ""
    if red_flags:
        new_state["risk_category"] = "critico"
        new_state["recommended_action"] = "immediate_911"

    debug_print("\n📦 ESTADO FINAL ACTUALIZADO:")
    debug_print(f"  recommendation_section: {new_state.get('recommendation_section', current_section)}")
    debug_print(f"  red_flags_detected: {new_state['red_flags_detected']}")
    debug_print(f"  messages: [Mensaje agregado]")
    debug_print("=" * 80)

    # Verificar si la conversación está completa (section = "3")
    final_section = new_state.get("recommendation_section", current_section)
    if final_section == "3":
        debug_print("🏁 FIN DE LA CONVERSACIÓN - Recomendación completa entregada")
    else:
        debug_print("⏸️  Esperando respuesta del usuario para continuar...")

    debug_print("=" * 80 + "\n")

    return new_state
