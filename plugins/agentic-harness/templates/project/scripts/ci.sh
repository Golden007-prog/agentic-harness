#!/usr/bin/env bash
# Comprobaciones de integración continua, independientes del proveedor de CI.
# Cualquier CI (GitHub Actions, GitLab CI, Jenkins…) solo tiene que ejecutar este script.
#   scripts/ci.sh          lint, formato y pruebas unitarias
#   scripts/ci.sh --evals  además, pruebas de integración y evaluaciones (necesita claves, cuesta dinero)
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest

if [ "${1:-}" = "--evals" ]; then
  uv run pytest -m integration
  for eval in agents/*/evals/run_eval.py; do
    [ -e "$eval" ] || continue
    module=$(dirname "$eval" | tr / .).run_eval
    uv run python -m "$module" --min-score "${EVAL_MIN_SCORE:-0.8}"
  done
fi
