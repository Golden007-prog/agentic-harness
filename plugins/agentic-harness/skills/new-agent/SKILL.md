---
name: new-agent
description: Crea un agente de IA nuevo de principio a fin con LangChain/LangGraph, Claude, trazas en Langfuse, evaluaciones y pruebas, a partir del esqueleto probado del plugin. Usar cuando el usuario pida crear, montar o empezar un agente, asistente o flujo agéntico nuevo.
argument-hint: <nombre_en_snake_case> <qué debe hacer>
---
# Crear un agente nuevo

Petición: $ARGUMENTS

## 0. Preparar el proyecto
Si no existe `.claude/rules/agent-design.md` en el proyecto, sigue antes la skill `/agentic-harness:init-project`. En esta sesión las reglas aún no estarán cargadas: léelas desde `${CLAUDE_PLUGIN_ROOT}/templates/project/.claude/rules/`.

## 1. Entender el caso
Si faltan, pregunta en un solo mensaje: qué entra y qué sale, qué sistemas externos toca, qué acciones tienen efectos, y cómo se va a usar (CLI, HTTP, job). Si la petición ya lo aclara, no preguntes.

## 2. Diseñar
Lanza el subagente `agentic-harness:agent-architect` con el caso de uso completo; parte del esqueleto descrito en `agent-design.md`. Muestra el diseño al usuario y espera su visto bueno antes de escribir código cuando el agente tenga tools con efectos externos o más de un agente; en el resto de casos, continúa.

## 3. Crear desde el esqueleto
1. `bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold-agent.sh" <nombre> "$CLAUDE_PROJECT_DIR"`. El nombre va en snake_case.
2. Si no existe `pyproject.toml`: `uv init --bare`. Instala las dependencias que imprime el script con `uv add` y `uv add --dev` (`uv add` ignora las que ya estén).
3. `uv run pytest agents/<nombre>` debe pasar antes de tocar nada: así sabes que el esqueleto funciona con las versiones instaladas. Si falla, consulta la documentación por MCP (o `agentic-harness:langchain-researcher`) antes de corregir, y dilo al usuario.

## 4. Adaptar
- `prompts.py`: rol, límites, uso de cada tool y formato de respuesta del caso real. Conserva las secciones (las comprueba `test_prompts.py`) y sube `PROMPT_VERSION`.
- `tools.py`: sustituye las tools de ejemplo siguiendo `/agentic-harness:add-tool`. Las que tienen efectos van en `TOOLS_REQUIRING_APPROVAL` y respetan `dry_run`.
- `config.py`: solo cambia valores por defecto si el diseño lo justifica.
- Adapta las pruebas de ejemplo a las tools reales; no borres las de histórico, límites ni aprobación.
- Si una API del esqueleto ya no coincide con la documentación vigente, dilo y corrígela consultando el MCP.
- Añade a `.env.example` cada variable nueva.

## 5. Evaluar
Sigue `/agentic-harness:add-eval` para escribir casos reales en `evals/dataset.jsonl`.

## 6. Probar
- `scripts/ci.sh` (lint, formato y pruebas unitarias) y lee el resultado.
- `uv run python -m agents.<nombre>.config` para comprobar que la configuración del usuario es válida (no muestra secretos).
- Si hay `ANTHROPIC_API_KEY` y el usuario lo acepta (cuesta dinero): `uv run pytest -m integration` y `uv run python -m agents.<nombre>.evals.run_eval`.

## 7. Revisar
Lanza `agentic-harness:agent-reviewer` sobre `agents/<nombre>/` y corrige los hallazgos graves.

## 8. Entregar
Informa: qué hace el agente, cómo ejecutarlo (CLI, servidor, imagen), resultado real de pruebas y evaluaciones, y qué quedó sin verificar (por ejemplo, trazas en Langfuse si no hay claves).
