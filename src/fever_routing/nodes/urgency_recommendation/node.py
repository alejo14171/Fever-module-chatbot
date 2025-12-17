from fever_routing.nodes.urgency_recommendation.prompt import (
    prompt_template, get_age_display, get_fever_duration_display, safe_display
)
from fever_routing.state import State
from fever_routing.utils.logging import debug_print
from fever_routing.utils import ModelFactory
from langchain_core.messages import AIMessage

llm = ModelFactory.get_urgency_recommendation_model()


def extract_user_message(history: list) -> str:
    """
    Extrae el último mensaje del usuario del historial.

    Args:
        history: Lista de mensajes

    Returns:
        str: Contenido del último mensaje del usuario
    """
    last_user_message = ""

    for msg in reversed(history):
        if hasattr(msg, '__class__') and msg.__class__.__name__ == "HumanMessage":
            if isinstance(msg.content, str):
                last_user_message = msg.content
            elif isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        last_user_message = item.get('text', '')
                        break
                if not last_user_message:
                    last_user_message = str(msg.content)
            else:
                last_user_message = str(msg.content)
            break

    return last_user_message


def urgency_recommendation_node(state: State):
    """
    Nodo de recomendación urgente para lactantes <3 meses con fiebre >38°C.

    Este nodo se activa cuando se cumplen criterios de urgencia inmediata:
    - Edad < 3 meses
    - Temperatura > 38°C

    Primera vez: Genera mensaje urgente comprensivo (por qué, qué hacer, qué llevar, qué esperar)
    Veces subsecuentes: Responde preguntas de seguimiento
    """
    new_state: State = {}

    history = state["messages"]
    urgency_given = state.get("urgency_recommendation_given", "")

    debug_print("\n" + "🚨" * 80)
    debug_print("🚨 URGENCY RECOMMENDATION NODE - INICIO")
    debug_print("=" * 80)
    debug_print(f"📊 Total mensajes en conversación: {len(history)}")
    debug_print(f"⚠️ CRITERIO URGENTE: Lactante <3 meses con fiebre >38°C")
    debug_print(f"📍 Recomendación urgente ya dada: {'SÍ' if urgency_given == 'yes' else 'NO'}")

    # Obtener datos del estado con valores seguros
    patient_name = safe_display(state.get("patient_name", ""), "el bebé")
    patient_age_months = safe_display(state.get("patient_age_months", ""), "desconocido")
    patient_weight_kg = safe_display(state.get("patient_weight_kg", ""), "desconocido")
    temperature = safe_display(state.get("temperature", ""), "No medida")
    fever_duration = safe_display(state.get("fever_duration_hours", ""), "desconocida")

    # Síntomas (opcionales para contexto)
    general_symptoms = safe_display(state.get("general_symptoms", ""), "No evaluado")
    respiratory_symptoms = safe_display(state.get("respiratory_symptoms", ""), "No evaluado")
    other_symptoms = safe_display(state.get("other_symptoms", ""), "Ninguno adicional")

    debug_print("\n🗄️ DATOS DEL PACIENTE:")
    debug_print(f"  Nombre: {patient_name}")
    debug_print(f"  Edad: {patient_age_months} meses")
    debug_print(f"  Peso: {patient_weight_kg} kg")
    debug_print(f"  Temperatura: {temperature}°C")
    debug_print(f"  Duración fiebre: {fever_duration} horas")
    debug_print(f"  Síntomas generales: {general_symptoms}")
    debug_print(f"  Síntomas respiratorios: {respiratory_symptoms}")
    debug_print(f"  Otros síntomas: {other_symptoms}")

    # Generar displays legibles
    age_display = get_age_display(patient_age_months)
    fever_duration_display = get_fever_duration_display(fever_duration)

    debug_print("\n📋 DISPLAYS GENERADOS:")
    debug_print(f"  Edad display: {age_display}")
    debug_print(f"  Duración display: {fever_duration_display}")
    debug_print("=" * 80)

    # ========== CASO 1: Primera vez - Generar mensaje urgente ==========
    if urgency_given != "yes":
        debug_print("\n🚨 PRIMERA VEZ - Generando mensaje urgente...")

        # Formatear el prompt con toda la información
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")

        formatted_prompt = prompt_template.format(
            today=today,
            patient_name=patient_name,
            patient_age_months=patient_age_months,
            age_display=age_display,
            patient_weight_kg=patient_weight_kg,
            temperature=temperature,
            fever_duration_display=fever_duration_display,
            general_symptoms_display=general_symptoms,
            respiratory_symptoms_display=respiratory_symptoms,
            other_symptoms=other_symptoms,
        )

        debug_print("\n📄 PROMPT FORMATEADO (primeros 1500 caracteres):")
        debug_print(formatted_prompt[:1500])
        debug_print("\n... [prompt continúa con instrucciones] ...")
        debug_print("=" * 80)

        debug_print("\n🤖 Invocando LLM para generar mensaje urgente...")
        ai_response = llm.invoke([
            ("system", formatted_prompt),
            ("user", "Por favor, genera el mensaje de orientación urgente para estos padres.")
        ])

        urgent_message = ai_response.content
        debug_print(f"\n💬 MENSAJE URGENTE GENERADO ({len(urgent_message)} caracteres)")
        debug_print(f"  Primeros 300 chars: {urgent_message[:300]}...")
        debug_print("=" * 80)

        # Preparar respuesta
        ai_message = AIMessage(content=urgent_message)
        new_state["messages"] = [ai_message]
        new_state["urgency_recommendation_given"] = "yes"
        new_state["urgency_criteria_met"] = "yes"

        # Actualizar campos de riesgo
        new_state["risk_category"] = "critico"
        new_state["recommended_action"] = "urgent_ed"
        new_state["red_flags_detected"] = "menor_3m_fiebre_alta"

        debug_print("\n✅ Mensaje urgente enviado")
        debug_print(f"  urgency_recommendation_given: yes")
        debug_print(f"  urgency_criteria_met: yes")
        debug_print(f"  risk_category: critico")
        debug_print(f"  recommended_action: urgent_ed")

    # ========== CASO 2: Subsecuente - Responder preguntas ==========
    else:
        debug_print("\n❓ PREGUNTA DE SEGUIMIENTO - Respondiendo...")

        # Extraer último mensaje del usuario
        last_user_message = extract_user_message(history)
        debug_print(f"  Último mensaje: '{last_user_message[:100]}...'")

        # Crear prompt para responder con contexto completo
        followup_prompt = f"""Eres un PEDIATRA CERTIFICADO que acaba de informar a los padres de {patient_name} ({age_display}, {patient_age_months} meses) que deben ir a urgencias INMEDIATAMENTE porque es un lactante menor de 3 meses con fiebre de {temperature}°C.

CONTEXTO - Ya les diste orientación urgente que incluía:
1. Por qué es urgente (lactante <3 meses con fiebre necesita evaluación inmediata)
2. Qué hacer (ir a urgencias pediátricas ahora)
3. Qué llevar (cargador, agua, carnet vacunas, pañales, documentos, nota con timeline)
4. Qué esperar (triage, exámenes de sangre/orina, 2-4 horas, protocolo estándar)

PREGUNTA/COMENTARIO DE LOS PADRES:
"{last_user_message}"

TU TAREA:
Responde de forma breve, clara y tranquilizadora a su pregunta específica.

CASOS COMUNES:
- Si preguntan sobre ambulancia: Solo si bebé está muy decaído, con dificultad respiratoria o cambio de color. Sino, pueden llevarlo en auto de forma segura.
- Si preguntan sobre medicamentos: No dar nada ahora, evaluarán en urgencias y darán tratamiento según necesidad.
- Si preguntan si es realmente necesario: SÍ, es protocolo médico estándar y obligatorio para lactantes <3 meses con fiebre. Es precaución importante.
- Si preguntan qué hospital: Urgencias pediátricas de cualquier hospital con servicio pediátrico. Si tienen pediatra de confianza, pueden ir a ese hospital.
- Si preguntan sobre tiempo: El proceso puede tomar 2-4 horas porque hacen evaluación completa (análisis, observación). Esto es normal.
- Si expresan miedo: Es completamente normal sentir miedo, pero están haciendo exactamente lo correcto. El equipo médico está preparado para estos casos.
- Si agradecen: Responde cordialmente y refuerza que están tomando la decisión correcta.

IMPORTANTE:
- Mantén el tono FIRME en urgencia pero CALMADO y TRANQUILIZADOR
- Respuestas breves (2-4 frases máximo)
- Enfatiza que están haciendo lo correcto
- No minimices la urgencia ni sugieras esperar
"""

        debug_print("\n🤖 Generando respuesta a pregunta de seguimiento...")
        ai_response = llm.invoke([
            ("system", followup_prompt),
            ("user", last_user_message)
        ])

        followup_message = ai_response.content
        debug_print(f"\n💬 RESPUESTA GENERADA ({len(followup_message)} caracteres)")
        debug_print(f"  Contenido: {followup_message[:200]}...")
        debug_print("=" * 80)

        # Preparar respuesta
        ai_message = AIMessage(content=followup_message)
        new_state["messages"] = [ai_message]
        # No cambiar urgency_recommendation_given, mantener en "yes"

    debug_print("\n📦 ESTADO FINAL ACTUALIZADO:")
    debug_print(f"  urgency_recommendation_given: {new_state.get('urgency_recommendation_given', urgency_given)}")
    debug_print(f"  messages: [Mensaje agregado]")
    debug_print("=" * 80)
    debug_print("🚨 URGENCY RECOMMENDATION NODE - FIN")
    debug_print("=" * 80 + "\n")

    return new_state
