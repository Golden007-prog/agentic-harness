#!/usr/bin/env bash
# PreToolUse(Read|Edit|Write): impide leer o escribir archivos de credenciales.
# Si no puede leer la entrada, bloquea (falla cerrado).
set -u
. "$(dirname "$0")/lib.sh"
hook_input
path=$(json_field tool_input.file_path) || deny_tool "$PARSER_MISSING"
base=$(basename "$path")

case "$base" in
  .env.example|.env.sample|.env.template) exit 0 ;;
  .env|.env.*)
    deny_tool "Archivo de entorno protegido ($base). Documenta variables nuevas en .env.example; el usuario edita .env." ;;
  *.pem|*.key|*service-account*.json|*service_account*.json|*credentials*.json|application_default_credentials.json)
    deny_tool "Archivo de credenciales protegido ($base)." ;;
esac
case "$path" in
  */secrets/*) deny_tool "El directorio secrets/ está protegido." ;;
esac
exit 0
