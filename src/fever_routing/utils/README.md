# Utilidades - Sistema de Logging

Este módulo proporciona un sistema de logging configurable para el sistema de triaje de fiebre pediátrica.

## 🔧 Configuración

Los logs del sistema se pueden habilitar/deshabilitar usando la variable de entorno `FEVER_DEBUG`.

### Habilitar logs (modo debug)

**Linux / MacOS:**
```bash
export FEVER_DEBUG=1
```

**Windows (CMD):**
```cmd
set FEVER_DEBUG=1
```

**Windows (PowerShell):**
```powershell
$env:FEVER_DEBUG="1"
```

**Docker / Docker Compose:**
```yaml
environment:
  - FEVER_DEBUG=1
```

### Deshabilitar logs (producción)

**Linux / MacOS:**
```bash
unset FEVER_DEBUG
# o
export FEVER_DEBUG=0
```

**Windows (CMD):**
```cmd
set FEVER_DEBUG=0
```

**Windows (PowerShell):**
```powershell
$env:FEVER_DEBUG="0"
```

### Valores aceptados para habilitar

La variable `FEVER_DEBUG` acepta cualquiera de estos valores (no distingue mayúsculas/minúsculas):
- `1`
- `true`
- `True`
- `yes`
- `Yes`

Cualquier otro valor (incluyendo vacío o no definido) deshabilitará los logs.

## 📝 Uso en el código

```python
from fever_routing.utils.logging import debug_print

# Funciona igual que print(), pero solo muestra output si FEVER_DEBUG=1
debug_print("Mensaje de debug")
debug_print(f"Variable: {valor}")
debug_print("Error:", error, sep=" - ")
```

## 📊 Módulos con logging

Los siguientes módulos utilizan `debug_print` para logging:

- **`receptor/node.py`**: Extracción de información del paciente
- **`inquiry/node.py`**: Generación de preguntas
- **`recommendation/node.py`**: Generación de recomendaciones
- **`routes/triage/route.py`**: Decisiones de routing del grafo

## 💡 Casos de uso

### Desarrollo local
```bash
# Habilitar logs para debugging
export FEVER_DEBUG=1
python main.py
```

### Producción
```bash
# No configurar la variable o establecerla en 0
python main.py
```

### Testing
```python
import os

# En tests, puedes controlar logs programáticamente
os.environ["FEVER_DEBUG"] = "1"  # Habilitar
from fever_routing.utils.logging import debug_print

debug_print("Test log")  # Se verá

os.environ["FEVER_DEBUG"] = "0"  # Deshabilitar
debug_print("Otro log")  # No se verá
```

## 🚀 Beneficios

✅ **Sin overhead en producción**: Los logs no afectan performance cuando están deshabilitados  
✅ **Fácil debugging**: Habilita logs instantáneamente sin cambiar código  
✅ **Granular**: Solo logs del módulo `fever_routing`, no afecta otras partes  
✅ **Configurable por entorno**: Diferente configuración para dev/staging/prod  

---

**Nota**: Los logs incluyen información detallada del estado del sistema, respuestas del LLM, y decisiones de routing. En producción es recomendable mantenerlos deshabilitados para evitar logs excesivos.

