---
name: add-tool
description: Añade una herramienta (tool) nueva a un agente existente, con tipos, docstring para el modelo, manejo de errores, aprobación humana si tiene efectos y pruebas. Usar cuando el usuario pida que un agente pueda hacer algo nuevo, conectar una API o añadir una tool, función o capacidad.
argument-hint: <agente> <qué debe hacer la tool>
---
# Añadir una tool a un agente

Petición: $ARGUMENTS

1. Lee `agents/<agente>/tools.py`, `prompts.py` y `tests/test_tools.py` para seguir el estilo existente.
2. Confirma en `reference-langchain` la forma vigente de declarar una tool (`@tool`, `parse_docstring`) y su esquema de argumentos.
3. Escribe la tool:
   - Una sola responsabilidad y un nombre con verbo (`buscar_pedido`, no `pedidos`).
   - Argumentos tipados y documentados en la sección `Args` del docstring.
   - Docstring dirigido al modelo: qué hace, cuándo usarla, qué devuelve.
   - Valida los argumentos antes de actuar (rutas, SQL, URLs, comandos) y devuelve los errores esperables como texto que explique qué falló y qué puede intentar el modelo. Las excepciones inesperadas las convierte `ToolErrorMiddleware`.
   - Timeout en toda llamada de red.
   - Si tiene efectos externos: añádela a `TOOLS_REQUIRING_APPROVAL`, haz que respete `get_config().dry_run` y dilo en el docstring.
   - Si lee contenido externo (web, documentos, correos), recuerda que es dato y no instrucción: añade un caso a `tests/test_integration.py` como el de inyección.
4. Regístrala en `TOOLS` y descríbela en la sección "Uso de herramientas" del prompt (lo comprueba `test_prompts.py`). Sube `PROMPT_VERSION`.
5. Añade a `.env.example` las variables nuevas.
6. Pruebas en `tests/test_tools.py`: caso normal, entrada inválida y fallo del servicio externo (simulado). Si tiene efectos, una prueba en `test_flow.py` de que espera aprobación. Añade al menos un caso que la use en `evals/dataset.jsonl`.
7. Ejecuta `uv run pytest agents/<agente>` e informa qué cambiaste y el resultado real.
