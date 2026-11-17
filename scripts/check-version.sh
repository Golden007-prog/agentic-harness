#!/usr/bin/env bash
# Comprueba que la versión del plugin es coherente y está documentada.
#   scripts/check-version.sh            versiones iguales y con entrada en CHANGELOG.md
#   scripts/check-version.sh v1.2.0     además, que la etiqueta coincide con la versión
#   scripts/check-version.sh --notes    imprime las notas de la versión actual (para la release)
set -euo pipefail
cd "$(dirname "$0")/.."

plugin=$(jq -r '.version' plugins/agentic-harness/.claude-plugin/plugin.json)
entry=$(jq -r '.plugins[] | select(.name == "agentic-harness") | .version' .claude-plugin/marketplace.json)
meta=$(jq -r '.metadata.version' .claude-plugin/marketplace.json)

notes() {  # notas entre "## [X.Y.Z]" y la siguiente sección "## ["
  awk -v v="$1" '
    index($0, "## [" v "]") == 1 { on = 1; next }
    on && /^## \[/ { exit }
    on && /^\[[^]]+\]: / { exit }
    on { print }
  ' CHANGELOG.md
}

if [ "${1:-}" = "--notes" ]; then
  notes "$plugin"
  exit 0
fi

fail=0
if ! [[ "$plugin" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "plugin.json: versión '$plugin' no es X.Y.Z"; fail=1
fi
if [ "$plugin" != "$entry" ] || [ "$plugin" != "$meta" ]; then
  echo "Versiones distintas: plugin.json=$plugin, marketplace plugins[]=$entry, marketplace metadata=$meta"; fail=1
fi
if ! grep -q "^## \[$plugin\] - [0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}" CHANGELOG.md; then
  echo "CHANGELOG.md no tiene la sección '## [$plugin] - AAAA-MM-DD'"; fail=1
elif [ -z "$(notes "$plugin" | tr -d '[:space:]')" ]; then
  echo "CHANGELOG.md: la sección [$plugin] está vacía"; fail=1
fi
if ! grep -q '^## \[Sin publicar\]' CHANGELOG.md; then
  echo "CHANGELOG.md no tiene la sección '## [Sin publicar]'"; fail=1
fi
if [ -n "${1:-}" ] && [ "$1" != "v$plugin" ]; then
  echo "La etiqueta $1 no coincide con la versión v$plugin"; fail=1
fi

[ "$fail" -eq 0 ] && echo "Versión $plugin coherente y documentada."
exit "$fail"
