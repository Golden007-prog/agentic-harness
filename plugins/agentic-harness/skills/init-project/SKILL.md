---
name: init-project
description: Prepara el proyecto actual para crear agentes con el harness (CLAUDE.md, reglas en .claude/rules, permisos, ruff, pytest, Dockerfile, CI, .env.example y .gitignore). Usar cuando el usuario pida inicializar, preparar o configurar un proyecto o repositorio para crear agentes, o cuando /new-agent detecte que faltan las reglas.
argument-hint: [--force]
---
# Inicializar un proyecto de agentes

1. Ejecuta `bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-project.sh" "$CLAUDE_PROJECT_DIR" $ARGUMENTS`. Sin `--force` no sobrescribe archivos existentes.
2. Si algún archivo quedó "omitido", compáralo con su plantilla en `${CLAUDE_PLUGIN_ROOT}/templates/project/` y propón al usuario cómo combinarlos; no lo sobrescribas sin permiso.
3. Si no existe `pyproject.toml`, ejecuta `uv init --bare`. Las dependencias de los agentes las añade `/agentic-harness:new-agent`.
4. Indica al usuario que copie `.env.example` a `.env` y complete las claves (tú no lees ni editas `.env`), y que las reglas de `.claude/rules/` se cargan al reiniciar la sesión.
5. Informa qué se instaló, qué se omitió y qué falta.
