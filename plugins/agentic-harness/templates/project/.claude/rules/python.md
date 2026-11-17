---
paths:
  - "**/*.py"
  - "pyproject.toml"
---
# Python

- Dependencias con `uv` (`uv add`, `uv sync`); no uses `pip install` directo ni edites `uv.lock` a mano.
- Type hints en todas las funciones públicas; Pydantic para esquemas de entrada y salida.
- `ruff` formatea y revisa cada archivo al guardarlo (hook `post-edit.sh`) con la configuración de `ruff.toml`. Si el hook devuelve errores, corrígelos antes de seguir.
- Código asíncrono para llamadas de red cuando el agente se sirve por HTTP.
- La configuración se lee del entorno en un único módulo `config.py`; el resto del código la importa de ahí.
- Pruebas con `pytest` (`uv run pytest`, configurado en `pytest.ini`). Las pruebas no llaman al modelo real salvo las marcadas como `integration` (`uv run pytest -m integration`).
- `scripts/ci.sh` es la única definición de CI: lint, formato y pruebas. `.github/workflows/ci.yml` solo lo ejecuta; no dupliques pasos en el workflow.
- La prueba del backend de Postgres se ejecuta con `HISTORY_TEST_POSTGRES_URL` definida y `uv run pytest -m integration -k postgres`.
