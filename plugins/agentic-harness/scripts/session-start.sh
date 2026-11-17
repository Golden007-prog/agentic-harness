#!/usr/bin/env bash
# SessionStart: inyecta en el contexto el estado del entorno (stdout -> contexto del modelo).
# Solo informa si las variables existen; nunca imprime sus valores.
set -u
. "$(dirname "$0")/lib.sh"
# Aviso en cualquier proyecto: sin jq ni python3 los hooks de seguridad bloquean las tools.
if ! command -v jq >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    echo "- agentic-harness: jq no está instalado; los hooks usan python3 como respaldo."
  else
    echo "- agentic-harness: faltan jq y python3; los hooks de seguridad bloquearán Read, Edit, Write y Bash hasta instalar jq."
  fi
fi
# Fuera de un proyecto inicializado no añade nada más al contexto.
is_harness_project || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

echo "## Estado del entorno (hook session-start)"

if [ -f .env ]; then
  echo "- .env: presente (no lo leas; consulta .env.example para los nombres de variables)"
else
  echo "- .env: ausente (crear a partir de .env.example)"
fi

for v in ANTHROPIC_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY; do
  if [ -n "${!v:-}" ] || { [ -f .env ] && grep -q "^${v}=." .env; }; then
    echo "- ${v}: definida"
  else
    echo "- ${v}: NO definida"
  fi
done

command -v uv >/dev/null 2>&1 || echo "- uv: NO instalado (el harness asume uv para Python)"
exit 0
