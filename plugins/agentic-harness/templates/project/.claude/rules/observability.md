# Observabilidad con Langfuse

- Todo agente envía trazas a Langfuse desde el primer commit, no como paso posterior.
- La integración (callback handler, decoradores, variables de entorno) se toma de `langfuse-docs`; confirma ahí los nombres actuales antes de escribirla.
- Cada traza lleva como mínimo: nombre del agente, entorno (`dev`/`staging`/`prod`), versión o commit, y un identificador de sesión cuando hay conversación.
- No envíes a las trazas secretos ni datos personales sin enmascarar. El esqueleto los enmascara al exportar (`mask_otel_spans` en `observability.py`); amplía los patrones con los datos sensibles de tu dominio.
- Sin `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` las trazas se desactivan, para que pruebas y desarrollo funcionen sin claves.
- Las evaluaciones se registran como experimentos de Langfuse con `PROMPT_VERSION` y modelo en el nombre, para comparar versiones.
- Los procesos de vida corta (scripts, jobs, funciones) vacían el buffer de Langfuse antes de terminar.
- Las credenciales se leen de `LANGFUSE_PUBLIC_KEY` y `LANGFUSE_SECRET_KEY`; nunca se escriben en el código.
