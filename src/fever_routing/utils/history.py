"""
Utilidades para formatear el historial de mensajes de forma limpia.
"""

def format_history(messages) -> str:
    """
    Formatea el historial de mensajes de forma limpia sin metadata.

    Args:
        messages: Lista de objetos HumanMessage/AIMessage de LangChain

    Returns:
        str: Historial formateado como texto limpio

    Example:
        Input: [HumanMessage(content='hola'), AIMessage(content='¿cómo estás?')]
        Output:
            "Usuario: hola
             Asistente: ¿cómo estás?"
    """
    if not messages:
        return "(sin mensajes previos)"

    formatted = []
    for msg in messages:
        # Determinar el rol según el tipo de mensaje
        role = "Usuario" if msg.__class__.__name__ == "HumanMessage" else "Asistente"
        formatted.append(f"{role}: {msg.content}")

    return "\n".join(formatted)
