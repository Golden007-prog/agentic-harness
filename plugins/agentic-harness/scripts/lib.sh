# Utilidades comunes de los hooks del plugin.

# Un proyecto "harness" es el que se inicializó con /agentic-harness:init-project.
is_harness_project() {
  [ -f "${CLAUDE_PROJECT_DIR:-.}/.claude/rules/agent-design.md" ]
}

# hook_input: lee la entrada JSON del hook (stdin) una sola vez.
HOOK_INPUT=""
hook_input() { HOOK_INPUT=$(cat); }

# json_field <campo.anidado>: extrae un campo de HOOK_INPUT con jq o, si falta, con python3.
# Devuelve 1 si no hay ningún parser o el JSON no es válido: el llamador debe fallar cerrado.
json_field() {
  local field=$1
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$HOOK_INPUT" | jq -er --arg f "$field" 'getpath($f | split(".")) // "" ' 2>/dev/null
    return $?
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$HOOK_INPUT" | python3 -I -c '
import json, sys
value = json.load(sys.stdin)
for key in sys.argv[1].split("."):
    value = value.get(key) if isinstance(value, dict) else None
print("" if value is None else value)
' "$field" 2>/dev/null
    return $?
  fi
  return 1
}

# deny_tool <motivo>: respuesta de PreToolUse que bloquea la llamada. No necesita jq.
# Quita comillas, barras y controles del motivo para que el JSON sea siempre válido.
deny_tool() {
  local reason
  reason=$(printf '%s' "$1" | tr -d '"\\' | tr '[:cntrl:]' ' ')
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
  exit 0
}

PARSER_MISSING="El hook de seguridad no pudo leer la llamada (falta jq y python3, o la entrada no es JSON). Instala jq para continuar."
