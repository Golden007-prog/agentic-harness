"""Trazas en Langfuse.

Se activan solo si LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY están definidas; así las pruebas y el
desarrollo sin claves funcionan igual. Cada traza lleva nombre del agente, entorno, versión,
session_id y PROMPT_VERSION. Los datos sensibles se enmascaran antes de exportarse.
"""

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from langchain_core.callbacks import BaseCallbackHandler

from .config import AGENT_NAME, AgentConfig
from .prompts import PROMPT_VERSION

_SENSITIVE = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"), "[API_KEY]"),
    (re.compile(r"sk-lf-[A-Za-z0-9-]{10,}"), "[API_KEY]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[NUMERO_TARJETA]"),
]


def mask_text(value: str) -> str:
    """Enmascara claves, correos y números de tarjeta."""
    for pattern, replacement in _SENSITIVE:
        value = pattern.sub(replacement, value)
    return value


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


@lru_cache
def _client(environment: str, release: str):
    from langfuse import Langfuse
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    def mask_otel_spans(*, params) -> MaskOtelSpansResult | None:
        patches = {}
        for identifier, span in params.spans.items():
            changes = {
                key: masked
                for key, value in span.attributes.items()
                if isinstance(value, str) and (masked := mask_text(value)) != value
            }
            if changes:
                patches[identifier] = OtelSpanPatch(set_attributes=changes)
        return MaskOtelSpansResult(span_patches=patches) if patches else None

    return Langfuse(
        environment=environment, release=release or None, mask_otel_spans=mask_otel_spans
    )


def callbacks(cfg: AgentConfig) -> list[BaseCallbackHandler]:
    """Handlers de LangChain para la invocación; vacío si las trazas están desactivadas."""
    if not tracing_enabled():
        return []
    from langfuse.langchain import CallbackHandler

    _client(cfg.app_env, cfg.release)
    return [CallbackHandler()]


@contextmanager
def trace_scope(cfg: AgentConfig, *, session_id: str, user_id: str | None = None) -> Iterator[None]:
    """Propaga los atributos de la traza a todo lo que ocurra dentro del bloque."""
    if not tracing_enabled():
        yield
        return
    from langfuse import propagate_attributes

    _client(cfg.app_env, cfg.release)
    with propagate_attributes(
        trace_name=AGENT_NAME,
        session_id=session_id,
        user_id=user_id,
        version=cfg.release or None,
        tags=[AGENT_NAME, cfg.app_env],
        metadata={"prompt_version": PROMPT_VERSION, "model": cfg.model_id},
    ):
        yield


def flush() -> None:
    """Vacía el buffer de Langfuse. Llamar antes de terminar procesos de vida corta."""
    if tracing_enabled():
        from langfuse import get_client

        get_client().flush()
