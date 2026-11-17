"""Construcción e invocación del agente.

- `build_agent()` arma el agente con sus tools y middleware.
- `AgentRunner` es la única puerta de entrada: conversa por `session_id`, gestiona las aprobaciones
  humanas, aplica el timeout del turno y conecta las trazas.
- `open_runner()` abre el backend de histórico y devuelve un runner listo (lo usan CLI y servidor).
"""

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, dynamic_prompt
from langchain.messages import AIMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from . import observability
from .config import AGENT_NAME, AgentConfig, build_model, get_config
from .guards import build_guard_middleware
from .memory import build_history_middleware, delete_session, open_checkpointer
from .prompts import build_system_prompt
from .tools import TOOLS

logger = logging.getLogger(__name__)

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
TIMEOUT_REPLY = "No pude terminar a tiempo. Inténtalo de nuevo o simplifica la petición."


@dynamic_prompt
def system_prompt(request: ModelRequest) -> str:
    """System prompt con las partes variables resueltas en cada llamada (p. ej., la fecha)."""
    return build_system_prompt()


def build_agent(
    *,
    cfg: AgentConfig | None = None,
    model: BaseChatModel | None = None,
    tools: Sequence[BaseTool] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Crea el agente. `model` y `tools` se pueden sustituir en pruebas."""
    cfg = cfg or get_config()
    middleware: list[AgentMiddleware] = [
        *build_history_middleware(cfg),
        system_prompt,
        *build_guard_middleware(cfg),
    ]
    return create_agent(
        model or build_model(cfg),
        tools=list(tools if tools is not None else TOOLS),
        middleware=middleware,
        checkpointer=checkpointer,
        name=AGENT_NAME,
    )


class PendingApproval(BaseModel):
    """Una llamada a tool que espera decisión humana."""

    id: str
    tool: str
    args: dict[str, Any]
    description: str = ""


class Decision(BaseModel):
    type: Literal["approve", "reject"]
    message: str | None = Field(None, description="Motivo del rechazo, visible para el modelo.")


class TurnResult(BaseModel):
    session_id: str
    status: Literal["completed", "needs_approval", "timeout"]
    reply: str | None = None
    pending: list[PendingApproval] = []


def validate_session_id(session_id: str) -> str:
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError("session_id inválido: usa 1-128 caracteres [A-Za-z0-9_.:-].")
    return session_id


class AgentRunner:
    def __init__(self, agent, checkpointer: BaseCheckpointSaver, cfg: AgentConfig) -> None:
        self.agent = agent
        self.checkpointer = checkpointer
        self.cfg = cfg

    def _config(self, session_id: str) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": session_id},
            "callbacks": observability.callbacks(self.cfg),
            "metadata": {"agent": AGENT_NAME},
            # Red de seguridad por encima de los límites de middleware: cada vuelta del bucle
            # recorre varios nodos (un paso por hook de middleware, modelo y tools).
            "recursion_limit": 30 * (self.cfg.max_model_calls_per_turn + 2),
        }

    async def _run(self, payload: Any, session_id: str, user_id: str | None) -> TurnResult:
        validate_session_id(session_id)
        config = self._config(session_id)
        with observability.trace_scope(self.cfg, session_id=session_id, user_id=user_id):
            try:
                output = await asyncio.wait_for(
                    self.agent.ainvoke(payload, config=config, version="v2"),
                    timeout=self.cfg.run_timeout_s,
                )
            except TimeoutError:
                logger.warning("Turno cortado por timeout en la sesión %s", session_id)
                return TurnResult(session_id=session_id, status="timeout", reply=TIMEOUT_REPLY)
        if output.interrupts:
            return TurnResult(
                session_id=session_id,
                status="needs_approval",
                pending=[_to_pending(i) for i in output.interrupts],
            )
        return TurnResult(
            session_id=session_id, status="completed", reply=_last_reply(output.value["messages"])
        )

    async def pending(self, session_id: str) -> list[PendingApproval]:
        """Aprobaciones que siguen abiertas en la sesión."""
        state = await self.agent.aget_state({"configurable": {"thread_id": session_id}})
        return [_to_pending(i) for i in state.interrupts]

    async def chat(self, session_id: str, message: str, user_id: str | None = None) -> TurnResult:
        """Envía un mensaje del usuario. Si hay aprobaciones abiertas, las devuelve sin avanzar."""
        validate_session_id(session_id)
        if open_items := await self.pending(session_id):
            return TurnResult(session_id=session_id, status="needs_approval", pending=open_items)
        return await self._run({"messages": [HumanMessage(message)]}, session_id, user_id)

    async def decide(
        self, session_id: str, decisions: dict[str, Decision], user_id: str | None = None
    ) -> TurnResult:
        """Responde a las aprobaciones abiertas, una decisión por id de interrupción."""
        validate_session_id(session_id)
        open_ids = {p.id for p in await self.pending(session_id)}
        unknown = set(decisions) - open_ids
        if unknown:
            raise ValueError(f"Aprobaciones desconocidas o ya resueltas: {sorted(unknown)}")
        resume = {k: d.model_dump(exclude_none=True) for k, d in decisions.items()}
        return await self._run(Command(resume=resume), session_id, user_id)

    async def clear(self, session_id: str) -> None:
        """Borra el histórico de la sesión."""
        await delete_session(self.checkpointer, validate_session_id(session_id))


def _to_pending(interrupt) -> PendingApproval:
    value = interrupt.value
    return PendingApproval(
        id=interrupt.id,
        tool=value["name"],
        args=value.get("args", {}),
        description=value.get("description", ""),
    )


def _last_reply(messages: Sequence[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.text:
            return message.text
    return ""


@asynccontextmanager
async def open_runner(
    cfg: AgentConfig | None = None, *, model: BaseChatModel | None = None
) -> AsyncIterator[AgentRunner]:
    """Abre el histórico configurado y devuelve el runner. Vacía las trazas al cerrar."""
    cfg = cfg or get_config()
    async with open_checkpointer(cfg) as checkpointer:
        agent = build_agent(cfg=cfg, model=model, checkpointer=checkpointer)
        try:
            yield AgentRunner(agent, checkpointer, cfg)
        finally:
            observability.flush()
