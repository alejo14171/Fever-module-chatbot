"""
Utilidad de logging para el sistema de triaje de fiebre.
Los logs se pueden habilitar/deshabilitar con la variable de entorno FEVER_DEBUG.
"""
import os


def is_debug_enabled() -> bool:
    """
    Verifica si el modo debug está habilitado.
    
    Returns:
        bool: True si FEVER_DEBUG está configurado como "1", "true", "True", "yes", "Yes"
    """
    debug_value = os.getenv("FEVER_DEBUG", "0").lower()
    return debug_value in ("1", "true", "yes")


def debug_print(*args, **kwargs):
    """
    Imprime un mensaje solo si el modo debug está habilitado.
    
    Uso:
        debug_print("Mensaje de debug")
        debug_print(f"Variable: {value}")
        debug_print("Error:", error, sep=" - ")
    
    Para habilitar los logs, configurar la variable de entorno:
        export FEVER_DEBUG=1  # Linux/Mac
        set FEVER_DEBUG=1     # Windows
    """
    if is_debug_enabled():
        print(*args, **kwargs)

