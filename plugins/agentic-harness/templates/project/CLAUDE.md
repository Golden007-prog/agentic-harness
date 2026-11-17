# Harness para crear agentes de IA

Este proyecto usa el plugin `agentic-harness` de Claude Code para construir agentes con LangChain/LangGraph, modelos de Anthropic (`claude-opus-5-5` por defecto) y trazas en Langfuse. Es agnóstico al proveedor de nube.

## Cómo trabajar aquí
- Las reglas de `.claude/rules/` se aplican siempre. La principal: consulta la documentación por MCP antes de escribir código de LangChain, LangGraph o Langfuse.
- Servidores MCP (los aporta el plugin): `docs-langchain` (guías), `reference-langchain` (referencia de API), `langfuse-docs` (Langfuse).
- Skills: `/agentic-harness:new-agent`, `/agentic-harness:add-tool`, `/agentic-harness:add-eval`, `/agentic-harness:instrument-langfuse`, `/agentic-harness:init-project`.
- Subagentes: `agentic-harness:langchain-researcher` (documentación), `agentic-harness:agent-architect` (diseño), `agentic-harness:agent-reviewer` (revisión).
- Hooks (del plugin): bloquean el acceso a `.env` y credenciales (y bloquean todo si no pueden leer la llamada), detectan secretos incrustados y pasan `ruff` a cada archivo Python editado.

## Todo agente incluye
Instrucciones (`prompts.py`), configuración del modelo (`config.py`), histórico por sesión (`memory.py`), límites y aprobación humana (`guards.py`), trazas (`observability.py`), CLI, servidor HTTP, evaluaciones y pruebas. Se crea desde el esqueleto del plugin. Detalle en `.claude/rules/agent-design.md`.

## Comandos
- `uv sync` — instalar dependencias
- `uv run pytest` — pruebas
- `uv run pytest -m integration` — pruebas con el modelo real (cuestan dinero)
- `uv run ruff check .` — lint
- `scripts/ci.sh` — lo que ejecuta la CI (`.github/workflows/ci.yml`); `--evals` añade integración y evaluaciones
- `uv run python -m agents.<nombre>.config` — validar la configuración (`.env` y entorno) sin arrancar el agente
- `uv run python -m agents.<nombre>.cli` — conversar por terminal
- `uv run python -m agents.<nombre>.server` — API HTTP
- `uv run python -m agents.<nombre>.evals.run_eval` — evaluación
- `docker build --build-arg AGENT=<nombre> -t <nombre> .` — imagen
