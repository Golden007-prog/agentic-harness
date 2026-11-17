#!/usr/bin/env bash
# Crea agents/<nombre>/ a partir del esqueleto probado del plugin.
#   scaffold-agent.sh <nombre> [directorio-del-proyecto]
# <nombre> en snake_case (es un paquete de Python). No sobrescribe un agente existente.
set -euo pipefail
name="${1:?Uso: scaffold-agent.sh <nombre> [directorio-del-proyecto]}"
dest_root="${2:-${CLAUDE_PROJECT_DIR:-$PWD}}"
tpl="$(cd "$(dirname "$0")/../templates/agent" && pwd)"

if ! [[ "$name" =~ ^[a-z][a-z0-9_]{0,40}$ ]]; then
  echo "Nombre inválido '$name': usa snake_case (letras minúsculas, números y _)." >&2
  exit 1
fi
dest="$dest_root/agents/$name"
if [ -e "$dest" ]; then
  echo "Ya existe $dest; no se sobrescribe." >&2
  exit 1
fi

mkdir -p "$dest_root/agents"
[ -e "$dest_root/agents/__init__.py" ] || : >"$dest_root/agents/__init__.py"
cp -R "$tpl" "$dest"
find "$dest" \( -name '__pycache__' -o -name '.ruff_cache' -o -name '.pytest_cache' \) -type d -prune -exec rm -rf {} +
# Sustituye el marcador por el nombre real en todos los archivos de texto.
grep -rl '__agent_name__' "$dest" | while IFS= read -r f; do
  sed -i.bak "s/__agent_name__/${name}/g" "$f" && rm -f "$f.bak"
done
echo "Creado: agents/$name"
echo "Dependencias: uv add \"langchain>=1.4.6\" langchain-anthropic langgraph langgraph-checkpoint-sqlite langfuse fastapi uvicorn pydantic-settings python-dotenv"
echo "              uv add --dev pytest pytest-asyncio httpx ruff"
