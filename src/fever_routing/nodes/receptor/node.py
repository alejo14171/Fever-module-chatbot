from fever_routing.nodes.receptor.prompt import SYSTEM_PROMPT, build_extraction_prompt
from fever_routing.state import State
from fever_routing.utils.logging import debug_print
from fever_routing.utils import ModelFactory
import re
import json
from datetime import datetime

# LLM sin structured output
llm = ModelFactory.get_receptor_model()

def calculate_age_in_months(birthdate_str: str) -> str:
    """
    Calcula la edad en meses a partir de una fecha de nacimiento.
    
    Acepta formatos:
    - DD/MM/YYYY (ej: "15/03/2023")
    - YYYY-MM-DD (ej: "2023-03-15")
    - DD-MM-YYYY (ej: "15-03-2023")
    
    Retorna la edad en meses como string, o "" si hay error.
    """
    if not birthdate_str or birthdate_str.lower() in ["desconocido", "unknown", ""]:
        return ""
    
    try:
        # Intentar diferentes formatos
        birthdate = None
        formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"]
        
        for fmt in formats:
            try:
                birthdate = datetime.strptime(birthdate_str.strip(), fmt)
                break
            except ValueError:
                continue
        
        if not birthdate:
            debug_print(f"⚠️ No se pudo parsear la fecha de nacimiento: {birthdate_str}")
            return ""
        
        # Calcular edad en meses
        today = datetime.now()
        months = (today.year - birthdate.year) * 12 + (today.month - birthdate.month)
        
        # Ajustar si aún no ha cumplido el mes actual
        if today.day < birthdate.day:
            months -= 1
        
        # Validar que sea razonable (0-216 meses = 0-18 años)
        if months < 0 or months > 216:
            debug_print(f"⚠️ Edad calculada fuera de rango: {months} meses")
            return ""
        
        debug_print(f"✅ Edad calculada: {months} meses (desde {birthdate_str})")
        return str(months)
        
    except Exception as e:
        debug_print(f"⚠️ Error calculando edad: {e}")
        return ""


def calculate_birthdate_from_age(age_months_str: str) -> str:
    """
    Calcula la fecha de nacimiento aproximada a partir de la edad en meses.

    Args:
        age_months_str: Edad en meses como string (ej: "24", "18")

    Returns:
        str: Fecha de nacimiento en formato DD/MM/YYYY (ej: "15/10/2022")
             Retorna "" si hay error.

    Nota: La fecha calculada es aproximada (usa día 15 del mes).
    """
    if not age_months_str or age_months_str.lower() in ["desconocido", "unknown", "", "0"]:
        return ""

    try:
        age_months = int(age_months_str)

        # Validar que sea razonable (0-216 meses = 0-18 años)
        if age_months < 0 or age_months > 216:
            debug_print(f"⚠️ Edad fuera de rango para calcular fecha: {age_months} meses")
            return ""

        # Calcular fecha de nacimiento aproximada
        today = datetime.now()

        # Restar los meses
        birth_year = today.year - (age_months // 12)
        birth_month = today.month - (age_months % 12)

        # Ajustar si el mes es negativo
        if birth_month <= 0:
            birth_month += 12
            birth_year -= 1

        # Usar día 15 como aproximación (mitad del mes)
        birth_day = 15

        # Formatear como DD/MM/YYYY
        birthdate_str = f"{birth_day:02d}/{birth_month:02d}/{birth_year}"

        debug_print(f"✅ Fecha de nacimiento calculada: {birthdate_str} (aprox. desde {age_months} meses)")
        return birthdate_str

    except Exception as e:
        debug_print(f"⚠️ Error calculando fecha de nacimiento: {e}")
        return ""


def validate_and_fill_expected_fields(
    state: State,
    extracted_fields: dict,
    expected_fields: list[str],
    fallback_values: dict
) -> dict:
    """
    Valida que los campos esperados se llenaron.
    Si no, aplica fallback (usualmente "no").
    
    Args:
        state: Estado actual
        extracted_fields: Campos extraídos por el LLM
        expected_fields: Lista de campos que DEBÍAN extraerse
        fallback_values: Diccionario con valores por defecto para campos faltantes
    
    Returns:
        dict: Campos validados y completados con fallbacks si es necesario
    """
    filled_fields = extracted_fields.copy()
    
    debug_print("\n🔍 VALIDACIÓN POST-EXTRACCIÓN:")
    debug_print(f"  Expected fields: {expected_fields}")
    debug_print(f"  Extracted fields: {list(extracted_fields.keys())}")
    
    for field in expected_fields:
        if field not in extracted_fields or not extracted_fields[field]:
            # Campo esperado no se llenó → aplicar fallback
            fallback_val = fallback_values.get(field, "no")
            filled_fields[field] = fallback_val
            debug_print(f"  ⚠️ Campo esperado '{field}' no extraído")
            debug_print(f"  ✅ Aplicando fallback: {field}: {fallback_val}")
        else:
            debug_print(f"  ✅ Campo '{field}' extraído correctamente: {extracted_fields[field]}")
    
    return filled_fields


def calculate_duration_from_datetime(fever_start_str: str) -> str:
    """
    Calcula las horas de duración desde una fecha/hora ISO hasta ahora.
    
    Args:
        fever_start_str: Fecha/hora en formato ISO "YYYY-MM-DD HH:MM"
        
    Returns:
        str: Horas de duración (ej: "48", "72")
    """
    from datetime import datetime
    
    if not fever_start_str or fever_start_str in ["desconocido", ""]:
        return ""
    
    try:
        # Parsear fecha ISO
        fever_start = datetime.strptime(fever_start_str, "%Y-%m-%d %H:%M")
        now = datetime.now()
        
        # Calcular diferencia
        duration = now - fever_start
        hours = int(duration.total_seconds() / 3600)
        
        # Validar que sea razonable (0-336 horas = 0-14 días)
        if 0 <= hours <= 336:
            debug_print(f"✅ Cálculo de duración desde fecha:")
            debug_print(f"   Inicio: {fever_start.strftime('%Y-%m-%d %H:%M (%A)')}")
            debug_print(f"   Ahora:  {now.strftime('%Y-%m-%d %H:%M (%A)')}")
            debug_print(f"   Duración: {hours} horas")
            return str(hours)
        else:
            debug_print(f"⚠️ Duración fuera de rango razonable: {hours}h")
            return ""
            
    except ValueError as e:
        debug_print(f"⚠️ Error parseando fecha '{fever_start_str}': {e}")
        debug_print(f"   Formato esperado: YYYY-MM-DD HH:MM")
        return ""
    except Exception as e:
        debug_print(f"❌ Error calculando duración: {e}")
        return ""


def parse_llm_response(response_text: str) -> dict:
    """
    Parsea la respuesta del LLM en formato 'campo: valor' y retorna un diccionario.
    
    Ejemplo de input:
        patient_name: Juan
        temperature: 38.5
        general_symptoms: rechaza_alimento:si, vomitos:no
    
    Retorna:
        {"patient_name": "Juan", "temperature": "38.5", "general_symptoms": "rechaza_alimento:si, vomitos:no"}
    """
    extracted_fields = {}
    
    # Buscar líneas con el formato "campo: valor"
    # Usamos regex para ser más robusto
    pattern = r'^(\w+):\s*(.+)$'
    
    for line in response_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
            
        match = re.match(pattern, line)
        if match:
            field_name = match.group(1).strip()
            field_value = match.group(2).strip()
            
            # Solo agregar si el valor no está vacío
            if field_value:
                extracted_fields[field_name] = field_value
    
    return extracted_fields


def receptor_node(state: State):
    """
    Nodo receptor: extrae información del mensaje del usuario y actualiza el estado.
    NO genera mensajes de conversación, solo extrae datos.

    IMPORTANTE: Solo retorna campos que tienen información nueva/actualizada.
    El LLM recibe el estado completo y toda la conversación para contexto.
    """
    messages = state["messages"]
    new_state: State = {}

    debug_print("\n" + "📥" * 80)
    debug_print("📥 RECEPTOR NODE - INICIO")
    debug_print("=" * 80)
    debug_print(f"📨 Total mensajes en conversación: {len(messages)}")
    debug_print(f"📨 Último mensaje: {messages[-1].content[:100]}...")
    
    debug_print("\n🗄️ ESTADO ACTUAL (antes de extracción):")
    state_fields = ["patient_name", "patient_age_months", "patient_weight_kg", "temperature",
                    "fever_duration_hours", "general_symptoms", "respiratory_symptoms", "medication_given"]
    for field in state_fields:
        value = state.get(field, "NO EXISTE EN STATE")
        if value and value not in ["desconocido", "", "NO EXISTE EN STATE"]:
            debug_print(f"  ✓ {field}: {value}")
        else:
            debug_print(f"  ✗ {field}: {value}")
    debug_print("=" * 80)

    # ========== LEER CONTEXTO DE LA PREGUNTA ACTIVA (FASE 2) ==========
    expected_fields = json.loads(state.get("expected_fields", "[]"))
    fallback_values = json.loads(state.get("fallback_values", "{}"))
    last_inquiry_question = state.get("last_inquiry_question", "")
    
    # Obtener extraction_hint desde get_next_question (no está en el state pero lo reconstruimos del contexto)
    extraction_hint = ""
    if expected_fields:
        debug_print("\n📌 CONTEXTO DE PREGUNTA ACTIVA DETECTADO:")
        debug_print(f"  Pregunta: {last_inquiry_question[:80]}...")
        debug_print(f"  Expected fields: {expected_fields}")
        debug_print(f"  Fallback values: {fallback_values}")

    # Construir el prompt con el estado actual y los campos faltantes
    debug_print("\n🔧 Construyendo prompt con estado actual, campos faltantes y contexto...")
    user_prompt = build_extraction_prompt(
        state, 
        messages,
        expected_fields=expected_fields,
        extraction_hint=extraction_hint
    )
    
    # Invocar LLM sin structured output - enviar TODA la conversación
    debug_print("\n🤖 Invocando LLM para extracción (con toda la conversación)...")
    
    # Construir los mensajes: system + toda la conversación + el prompt de extracción
    llm_messages = [("system", SYSTEM_PROMPT)]
    
    # Agregar toda la conversación
    for msg in messages:
        if hasattr(msg, 'type'):
            llm_messages.append((msg.type, msg.content))
        else:
            # Fallback si no tiene type
            llm_messages.append(("human", str(msg.content)))
    
    # Agregar el prompt de extracción al final
    llm_messages.append(("user", user_prompt))
    
    response = llm.invoke(llm_messages)
    response_text = response.content
    
    debug_print("\n📋 RESPUESTA DEL LLM:")
    debug_print(response_text)
    debug_print("=" * 80)
    
    # Parsear la respuesta del LLM
    debug_print("\n🔍 Parseando respuesta...")
    extracted_fields = parse_llm_response(response_text)
    
    debug_print("\n📋 CAMPOS EXTRAÍDOS (antes de validación):")
    if extracted_fields:
        for field, value in extracted_fields.items():
            debug_print(f"  ✅ {field}: {value}")
    else:
        debug_print("  ⚪ No se extrajo información nueva")
    
    # ========== VALIDACIÓN POST-EXTRACCIÓN (FASE 3) ==========
    validated_fields = validate_and_fill_expected_fields(
        state,
        extracted_fields,
        expected_fields,
        fallback_values
    )
    
    debug_print("\n📋 CAMPOS DESPUÉS DE VALIDACIÓN:")
    for field, value in validated_fields.items():
        debug_print(f"  ✅ {field}: {value}")
        # Agregar al new_state
        new_state[field] = value
    
    # Si se recibió fecha de nacimiento, calcular edad en meses automáticamente
    if "patient_birthdate" in validated_fields:
        debug_print("\n🎂 Fecha de nacimiento detectada, calculando edad en meses...")
        age_months = calculate_age_in_months(validated_fields["patient_birthdate"])
        if age_months:
            new_state["patient_age_months"] = age_months
            debug_print(f"  ✅ patient_age_months: {age_months}")
        else:
            debug_print("  ⚠️ No se pudo calcular la edad (formato de fecha inválido)")

    # Si se recibió edad en meses y NO hay fecha de nacimiento, calcularla automáticamente
    if "patient_age_months" in validated_fields and "patient_birthdate" not in validated_fields:
        # Solo calcular si no hay fecha de nacimiento en el estado actual
        current_birthdate = state.get("patient_birthdate", "")
        if not current_birthdate or current_birthdate in ["desconocido", ""]:
            debug_print("\n📅 Edad en meses detectada, calculando fecha de nacimiento aproximada...")
            birthdate = calculate_birthdate_from_age(validated_fields["patient_age_months"])
            if birthdate:
                new_state["patient_birthdate"] = birthdate
                debug_print(f"  ✅ patient_birthdate: {birthdate} (aproximado)")
            else:
                debug_print("  ⚠️ No se pudo calcular la fecha de nacimiento")

    # ========== CONVERSIÓN AUTOMÁTICA: fever_start_datetime → fever_duration_hours ==========
    if "fever_start_datetime" in validated_fields:
        debug_print("\n⏰ Fecha/hora de inicio de fiebre detectada...")
        fever_start = validated_fields["fever_start_datetime"]
        
        # Calcular horas automáticamente
        duration_hours = calculate_duration_from_datetime(fever_start)
        
        if duration_hours:
            new_state["fever_duration_hours"] = duration_hours
            debug_print(f"  ✅ fever_duration_hours calculado automáticamente: {duration_hours}h")
        else:
            debug_print(f"  ⚠️ No se pudo calcular duración desde: {fever_start}")
    
    # Si el usuario dio duración directa (ej: "hace 24 horas"), usar esa sin conversión
    elif "fever_duration_hours" in validated_fields:
        debug_print("\n⏰ Duración de fiebre extraída directamente (usuario dio horas/días)")
        debug_print(f"  ✅ fever_duration_hours: {validated_fields['fever_duration_hours']}h (sin conversión)")

    debug_print(f"\n📈 Total campos después de validación: {len(validated_fields)}")
    debug_print("=" * 80)

    debug_print("\n📦 ESTADO QUE SE RETORNA (solo updates):")
    if new_state:
        for field, value in new_state.items():
            display_value = f"{value[:50]}..." if len(str(value)) > 50 else value
            debug_print(f"  ✓ {field}: {display_value}")
    else:
        debug_print("  ⚪ Sin updates")
    debug_print("=" * 80 + "\n")

    return new_state
