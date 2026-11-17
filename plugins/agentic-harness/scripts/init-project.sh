#!/usr/bin/env bash
# Prepara un proyecto para crear agentes con el plugin agentic-harness.
#   init-project.sh [directorio] [--force]
# Copia todo templates/project/: CLAUDE.md, reglas, permisos, ruff/pytest, Dockerfile, CI…
# Sin --force no sobrescribe nada; en .gitignore y .env.example añade solo las líneas que falten.
set -euo pipefail
tpl="$(cd "$(dirname "$0")/../templates/project" && pwd)"
dest="${1:-${CLAUDE_PROJECT_DIR:-$PWD}}"
force="${2:-}"
mkdir -p "$dest"

copy() {  # copy <ruta relativa>
  local rel=$1
  if [ -e "$dest/$rel" ] && [ "$force" != "--force" ]; then
    echo "omitido (ya existe): $rel"
  else
    mkdir -p "$(dirname "$dest/$rel")"
    cp -p "$tpl/$rel" "$dest/$rel"
    echo "instalado: $rel"
  fi
}

merge_lines() {  # merge_lines <ruta relativa>: añade las líneas que falten (variables o patrones)
  local rel=$1 added=0 key
  if [ ! -e "$dest/$rel" ]; then cp "$tpl/$rel" "$dest/$rel"; echo "instalado: $rel"; return; fi
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"
    # Comparación literal: la línea entera (patrones) o la clave seguida de "=" (variables)
    if ! awk -v k="$key" '$0 == k || index($0, k "=") == 1 { f = 1 } END { exit !f }' "$dest/$rel"; then
      [ "$added" -eq 0 ] && printf '\n# Añadido por agentic-harness\n' >>"$dest/$rel"
      printf '%s\n' "$line" >>"$dest/$rel"; added=$((added + 1))
    fi
  done <"$tpl/$rel"
  echo "actualizado: $rel ($added línea(s) nuevas)"
}

while IFS= read -r rel; do
  case "$rel" in
    .gitignore|.env.example) merge_lines "$rel" ;;
    *) copy "$rel" ;;
  esac
done < <(cd "$tpl" && find . -type f | sed 's|^\./||' | sort)
echo "Listo: $dest"
