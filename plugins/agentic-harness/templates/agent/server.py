"""Servidor HTTP del agente.

    uv run python -m agents.__agent_name__.server

Endpoints:
    GET    /health
    POST   /chat                              {"session_id", "message", "user_id"?}
    GET    /sessions/{session_id}/approvals
    POST   /sessions/{session_id}/decisions
           {"decisions": {"<id>": {"type": "approve" | "reject", "message"?}}}
    DELETE /sessions/{session_id}

Si AGENT_API_TOKEN está definida, todas las rutas salvo /health exigen
`Authorization: Bearer <token>`.
"""

import hmac
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .agent import AgentRunner, Decision, PendingApproval, TurnResult, open_runner
from .config import AGENT_NAME, get_config, load_config_or_exit


class ChatRequest(BaseModel):
    session_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    message: str = Field(min_length=1, max_length=20_000)
    user_id: str | None = Field(None, max_length=128)


class DecisionsRequest(BaseModel):
    decisions: dict[str, Decision] = Field(min_length=1)
    user_id: str | None = Field(None, max_length=128)


def create_app(
    runner_factory: Callable[[], AbstractAsyncContextManager[AgentRunner]] = open_runner,
    api_token: str | None = None,
) -> FastAPI:
    token = get_config().api_token if api_token is None else api_token

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with runner_factory() as runner:
            app.state.runner = runner
            yield

    app = FastAPI(title=AGENT_NAME, lifespan=lifespan)

    def require_token(authorization: str | None = Header(None)) -> None:
        if not token:
            return
        expected = f"Bearer {token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="No autorizado")

    def runner_of(request: Request) -> AgentRunner:
        return request.app.state.runner

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "agent": AGENT_NAME}

    @app.post("/chat", dependencies=[Depends(require_token)])
    async def chat(body: ChatRequest, request: Request) -> TurnResult:
        return await runner_of(request).chat(body.session_id, body.message, body.user_id)

    @app.get("/sessions/{session_id}/approvals", dependencies=[Depends(require_token)])
    async def approvals(session_id: str, request: Request) -> list[PendingApproval]:
        try:
            return await runner_of(request).pending(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/sessions/{session_id}/decisions", dependencies=[Depends(require_token)])
    async def decide(session_id: str, body: DecisionsRequest, request: Request) -> TurnResult:
        try:
            return await runner_of(request).decide(session_id, body.decisions, body.user_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/sessions/{session_id}", status_code=204, dependencies=[Depends(require_token)])
    async def clear(session_id: str, request: Request) -> None:
        try:
            await runner_of(request).clear(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def main() -> None:
    import uvicorn

    cfg = load_config_or_exit()  # carga .env y valida antes de arrancar
    uvicorn.run(create_app(), host="0.0.0.0", port=cfg.port)  # noqa: S104


if __name__ == "__main__":
    main()
