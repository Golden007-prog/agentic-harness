"""Histórico de conversación por sesión.

- Persistencia: checkpointers de LangGraph. Cada `session_id` es un `thread_id`.
- Backends (HISTORY_BACKEND): `memory` (desarrollo y pruebas), `sqlite` (local, un solo proceso)
  y `postgres` (producción; requiere `uv add langgraph-checkpoint-postgres "psycopg[binary]"`).
- Límite: antes de cada llamada al modelo se recorta (`trim`) o se resume (`summarize`). El system
  prompt no forma parte del histórico, así que nunca se recorta. El recorte empieza siempre en un
  mensaje humano, de modo que no separa una llamada a tool de su resultado.
"""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, SummarizationMiddleware
from langchain.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from .config import AgentConfig, build_model

CANCELLED_TOOL_RESULT = (
    "Llamada cancelada: el turno se interrumpió antes de obtener el resultado. "
    "No asumas que la acción se ejecutó."
)


@asynccontextmanager
async def open_checkpointer(cfg: AgentConfig) -> AsyncIterator[BaseCheckpointSaver]:
    """Abre el backend de histórico configurado. La lógica del agente no conoce cuál es."""
    if cfg.history_backend == "memory":
        yield InMemorySaver()
    elif cfg.history_backend == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(cfg.history_url or "history.sqlite") as saver:
            await saver.setup()
            yield saver
    elif cfg.history_backend == "postgres":
        if not cfg.history_url:
            raise ValueError("HISTORY_BACKEND=postgres requiere HISTORY_URL (cadena de conexión).")
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError as exc:  # dependencia opcional
            raise RuntimeError(
                'Instala el backend: uv add langgraph-checkpoint-postgres "psycopg[binary]"'
            ) from exc
        async with AsyncPostgresSaver.from_conn_string(cfg.history_url) as saver:
            await saver.setup()
            yield saver
    else:  # pragma: no cover - Literal en config lo impide
        raise ValueError(f"HISTORY_BACKEND desconocido: {cfg.history_backend}")


async def delete_session(checkpointer: BaseCheckpointSaver, session_id: str) -> None:
    """Borra todo el histórico de una sesión."""
    await checkpointer.adelete_thread(session_id)


def repair_tool_pairs(messages: Sequence[BaseMessage]) -> tuple[list[BaseMessage], bool]:
    """Añade un resultado de cancelación a cada llamada a tool que se quedó sin respuesta.

    Ocurre si un turno se corta (timeout, error) entre la llamada y el resultado. Sin esto, el
    siguiente turno enviaría al modelo un histórico inválido.
    """
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    repaired: list[BaseMessage] = []
    changed = False
    for message in messages:
        repaired.append(message)
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call["id"] not in answered:
                    repaired.append(
                        ToolMessage(
                            content=CANCELLED_TOOL_RESULT,
                            tool_call_id=call["id"],
                            name=call["name"],
                            status="error",
                        )
                    )
                    changed = True
    return repaired, changed


def trim_history(messages: Sequence[BaseMessage], max_tokens: int) -> list[BaseMessage]:
    """Conserva los mensajes más recientes que caben en `max_tokens`, empezando en un humano."""
    messages = list(messages)
    if count_tokens_approximately(messages) <= max_tokens:
        return messages
    trimmed = trim_messages(
        messages,
        max_tokens=max_tokens,
        token_counter=count_tokens_approximately,
        strategy="last",
        start_on="human",
        end_on=("human", "tool"),
        include_system=False,
    )
    if trimmed:
        return trimmed
    # El turno actual ya no cabe entero: se conserva desde el último mensaje humano.
    human_positions = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    return messages[human_positions[-1] :] if human_positions else messages[-1:]


class HistoryMiddleware(AgentMiddleware):
    """Repara llamadas a tool huérfanas y, si `trim=True`, recorta el histórico."""

    def __init__(self, *, max_tokens: int, trim: bool = True) -> None:
        super().__init__()
        self.max_tokens = max_tokens
        self.trim = trim

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state["messages"]
        repaired, changed = repair_tool_pairs(messages)
        result = trim_history(repaired, self.max_tokens) if self.trim else repaired
        if not changed and len(result) == len(messages):
            return None
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *result]}


def build_history_middleware(cfg: AgentConfig) -> list[AgentMiddleware]:
    """Middleware que mantiene el histórico dentro del límite según HISTORY_STRATEGY."""
    if cfg.history_strategy == "summarize":
        return [
            HistoryMiddleware(max_tokens=cfg.history_max_tokens, trim=False),
            SummarizationMiddleware(
                model=build_model(cfg),
                trigger=("tokens", cfg.history_max_tokens),
                keep=("tokens", cfg.history_max_tokens // 2),
            ),
        ]
    return [HistoryMiddleware(max_tokens=cfg.history_max_tokens)]
