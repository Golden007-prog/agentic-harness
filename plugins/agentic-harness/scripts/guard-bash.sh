#!/usr/bin/env bash
# PreToolUse(Bash): impide volcar archivos de secretos por la terminal.
# Es una barrera contra errores, no un límite de seguridad: un comando ofuscado puede saltársela.
# Si no puede leer la entrada, bloquea (falla cerrado).
set -u
. "$(dirname "$0")/lib.sh"
hook_input
cmd=$(json_field tool_input.command) || deny_tool "$PARSER_MISSING"

readers='cat|less|more|head|tail|bat|strings|grep|rg|awk|sed'
if grep -Eq "(^|[;&|[:space:]])(${readers})[[:space:]][^;&|]*\.env([[:space:]]|\$|\.local|\.prod|\.dev)" <<<"$cmd"; then
  deny_tool "No se imprimen archivos .env. Usa .env.example para conocer los nombres de las variables."
fi
exit 0
