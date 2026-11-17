#!/usr/bin/env bash
# Prueba el esqueleto de agente de punta a punta en un proyecto temporal:
# init-project -> scaffold-agent -> uv add -> scripts/ci.sh (ruff + pytest).
# Necesita red la primera vez (descarga dependencias). Uso: scripts/test-skeleton.sh [--keep]
# Con HISTORY_TEST_POSTGRES_URL definida, prueba también el backend de Postgres.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
p="$root/plugins/agentic-harness/scripts"
proj=$(mktemp -d)
[ "${1:-}" = "--keep" ] && echo "Proyecto: $proj" || trap 'rm -rf "$proj"' EXIT

bash "$p/init-project.sh" "$proj" >/dev/null
deps=$(bash "$p/scaffold-agent.sh" demo_agent "$proj" | sed -n 's/^Dependencias: uv add //p')
cd "$proj"
uv init --bare --name demo -q
eval "uv add -q $deps"
uv add -q --dev pytest pytest-asyncio httpx ruff
grep -rq '__agent_name__' agents && { echo "Quedan marcadores sin sustituir"; exit 1; }
env -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY bash scripts/ci.sh
if [ -n "${HISTORY_TEST_POSTGRES_URL:-}" ]; then
  uv add -q --optional postgres langgraph-checkpoint-postgres "psycopg[binary]"
  uv run --extra postgres pytest -q -m integration -k postgres agents/demo_agent/tests/test_memory.py
fi
echo "Esqueleto OK."
