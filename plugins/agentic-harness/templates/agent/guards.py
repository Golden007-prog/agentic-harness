"""Límites y protecciones del bucle del agente.

- Llamadas al modelo y a tools por turno (middleware integrado de LangChain).
- Presupuesto de tokens por sesión (SessionTokenBudget), que controla el coste de una conversación.
- Errores de tools convertidos en texto para el modelo, sin detalles internos.
- Aprobación humana para tools con efectos externos.
El timeout de cada turno se aplica en agent.py.
"""

import logging
from typing import Any, NotRequired

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
    hook_config,
)
from langchain.messages import AIMessage
from langgraph.runtime import Runtime

from .config import AgentConfig
from .tools import TOOLS_REQUIRING_APPROVAL

logger = logging.getLogger(__name__)

BUDGET_EXHAUSTED_REPLY = (
    "Esta conversación alcanzó su límite de uso. Empieza una sesión nueva para continuar."
)


class BudgetState(AgentState):
    tokens_used: NotRequired[int]


class SessionTokenBudget(AgentMiddleware[BudgetState]):
    """Suma los tokens de cada respuesta del modelo y corta la sesión al superar el presupuesto."""

    state_schema = BudgetState

    def __init__(self, budget: int) -> None:
        super().__init__()
        self.budget = budget  # 0 = sin límite

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: BudgetState, runtime: Runtime) -> dict[str, Any] | None:
        if self.budget and state.get("tokens_used", 0) >= self.budget:
            return {"messages": [AIMessage(BUDGET_EXHAUSTED_REPLY)], "jump_to": "end"}
        return None

    def after_model(self, state: BudgetState, runtime: Runtime) -> dict[str, Any] | None:
        last = state["messages"][-1]
        usage = getattr(last, "usage_metadata", None) or {}
        spent = usage.get("total_tokens", 0)
        if not spent:
            return None
        return {"tokens_used": state.get("tokens_used", 0) + spent}


def tool_error_to_text(exc: Exception, request: ToolCallRequest) -> str:
    """Convierte la excepción de una tool en texto útil para el modelo, sin detalles internos."""
    name = request.tool_call["name"]
    logger.exception("La tool %s falló", name, exc_info=exc)
    return (
        f"La herramienta `{name}` falló ({type(exc).__name__}). "
        "Revisa los argumentos o explica al usuario que no se pudo completar."
    )


def build_guard_middleware(cfg: AgentConfig) -> list[AgentMiddleware]:
    """Límites y protecciones. La aprobación humana va antes que el manejo de errores (docs)."""
    return [
        SessionTokenBudget(cfg.session_token_budget),
        ModelCallLimitMiddleware(run_limit=cfg.max_model_calls_per_turn, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=cfg.max_tool_calls_per_turn),
        HumanInTheLoopMiddleware(
            interrupt_on=dict(TOOLS_REQUIRING_APPROVAL),
            interrupt_mode="per_call",
            description_prefix="La herramienta necesita aprobación",
        ),
        ToolErrorMiddleware(on_error=tool_error_to_text),
    ]
