# Docokids Fever Chatbot — Landing

Landing local con documentación de arquitectura, vista detallada de los 25 tests y chat en vivo.

## Archivos

- `index.html` — landing completa (Tailwind CDN + Mermaid + vanilla JS)
- `tests_data.json` — transcripts y verdicts de los 25 tests (generado por `build_tests_data.py`)
- `build_tests_data.py` — parser de logs de pytest → JSON consumido por la landing

## Correr localmente

```bash
cd landing
python3 -m http.server 8080
# abrí http://localhost:8080
```

Si el chat no conecta, verificá que `langgraph dev --tunnel` esté corriendo y pegá la URL del túnel arriba a la derecha en la sección **Probar**.

## Regenerar `tests_data.json`

Después de correr una nueva suite agéntica:

```bash
cd landing
python3 build_tests_data.py
```

Lee de `/tmp/fever-runs/full_v7.log` y `/tmp/fever-runs/v8_retry.log` por defecto. Editá el script para apuntar a otros logs.

## Secciones de la landing

1. **Hero + métricas** — resumen visual.
2. **Arquitectura** — diagrama Mermaid del grafo + capas Python/LLM + 7 ramas conversacionales.
3. **Tests** — 25 cards filtrables por categoría, click para abrir modal con transcript completo + verdict del juez.
4. **Estado del arte** — 6 decisiones arquitecturales con citas (Nature, Mount Sinai, Anthropic, Hartford, LangGraph docs).
5. **Código** — file tree + stack técnico.
6. **Probar** — chat embed con avatares, typing indicator, sugerencias clicables, switch entre grafos.
