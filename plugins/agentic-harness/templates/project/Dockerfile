# Imagen estándar para cualquier agente del proyecto. Sin dependencias de un proveedor de nube.
#   docker build --build-arg AGENT=<nombre> -t <nombre> .
#   docker run --env-file .env -p 8000:8000 <nombre>
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY agents ./agents

ARG AGENT
RUN test -n "$AGENT" || (echo "Falta --build-arg AGENT=<nombre>" && exit 1)
ENV AGENT=${AGENT} PORT=8000

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=3)"
CMD ["sh", "-c", "exec /app/.venv/bin/python -m agents.${AGENT}.server"]
