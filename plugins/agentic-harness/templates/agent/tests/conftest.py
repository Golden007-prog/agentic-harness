"""Utilidades de prueba: modelo falso con tools, configuración aislada y runner en memoria."""

import os
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values
from langchain.messages import AIMessage, ToolCall
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from ..agent import AgentRunner, build_agent
from ..config import AgentConfig, get_config
from ..memory import open_checkpointer

# Entorno del proceso antes de que ninguna prueba lo toque (para las pruebas de integración).
ORIGINAL_ENV = dict(os.environ)


class FakeToolCallingModel(GenericFakeChatModel):
    """GenericFakeChatModel no implementa bind_tools; create_agent lo necesita."""

    def bind_tools(self, tools, **kwargs):
        return self


def fake_model(*responses: AIMessage | str) -> FakeToolCallingModel:
    return FakeToolCallingModel(messages=iter(responses))


def call(name: str, call_id: str = "call_1", **args: Any) -> AIMessage:
    """Respuesta del modelo que llama a una tool."""
    return AIMessage(content="", tool_calls=[ToolCall(name=name, args=args, id=call_id)])


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    """Sin trazas, histórico en memoria y tools en modo prueba, sea cual sea el entorno local.

    Las pruebas no leen `.env`. Al terminar, el entorno vuelve a su estado anterior aunque una
    prueba lo haya modificado directamente (por ejemplo, con load_env_file).
    """
    snapshot = dict(os.environ)
    for var in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "AGENT_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HISTORY_BACKEND", "memory")
    monkeypatch.setenv("AGENT_DRY_RUN", "true")
    get_config.cache_clear()
    yield
    os.environ.clear()
    os.environ.update(snapshot)
    get_config.cache_clear()


@pytest.fixture
def real_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Para pruebas `integration`: entorno real del proceso más `.env` (el entorno tiene prioridad).

    Se salta la prueba si no hay ANTHROPIC_API_KEY. Mantiene histórico en memoria y modo prueba.
    """
    from_file = dotenv_values(Path.cwd() / ".env") if (Path.cwd() / ".env").is_file() else {}
    merged = {k: v for k, v in from_file.items() if v} | {
        k: v for k, v in ORIGINAL_ENV.items() if v
    }
    if not merged.get("ANTHROPIC_API_KEY"):
        pytest.skip("requiere ANTHROPIC_API_KEY (en el entorno o en .env)")
    for key, value in merged.items():
        if key not in {"HISTORY_BACKEND", "AGENT_DRY_RUN"}:
            monkeypatch.setenv(key, value)
    get_config.cache_clear()


RunnerFactory = Callable[..., AbstractAsyncContextManager[AgentRunner]]


@pytest.fixture
def make_runner() -> RunnerFactory:
    """`async with make_runner(model, **overrides) as runner:` crea un runner con modelo falso."""

    @asynccontextmanager
    async def factory(model, tools=None, **overrides: Any) -> AsyncIterator[AgentRunner]:
        cfg = AgentConfig().model_copy(update=overrides)
        async with open_checkpointer(cfg) as checkpointer:
            agent = build_agent(cfg=cfg, model=model, tools=tools, checkpointer=checkpointer)
            yield AgentRunner(agent, checkpointer, cfg)

    return factory


async def history(runner: AgentRunner, session_id: str) -> list[Any]:
    state = await runner.agent.aget_state({"configurable": {"thread_id": session_id}})
    return state.values.get("messages", [])
