"""Servidor HTTP con modelo falso."""

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from ..agent import AgentRunner, build_agent
from ..config import AgentConfig
from ..memory import open_checkpointer
from ..server import create_app
from .conftest import call, fake_model


def _client(*responses, token: str = "") -> TestClient:
    @asynccontextmanager
    async def factory():
        cfg = AgentConfig()
        async with open_checkpointer(cfg) as checkpointer:
            agent = build_agent(cfg=cfg, model=fake_model(*responses), checkpointer=checkpointer)
            yield AgentRunner(agent, checkpointer, cfg)

    return TestClient(create_app(factory, api_token=token))


def test_health():
    with _client() as client:
        assert client.get("/health").json()["status"] == "ok"


def test_chat_y_borrado():
    with _client("hola") as client:
        r = client.post("/chat", json={"session_id": "s1", "message": "hola"})
        assert r.status_code == 200
        assert r.json() == {
            "session_id": "s1",
            "status": "completed",
            "reply": "hola",
            "pending": [],
        }
        assert client.delete("/sessions/s1").status_code == 204


def test_aprobacion_por_http():
    with _client(call("registrar_nota", texto="x"), "hecho") as client:
        r = client.post("/chat", json={"session_id": "s1", "message": "apunta x"}).json()
        assert r["status"] == "needs_approval"
        pending_id = r["pending"][0]["id"]
        assert client.get("/sessions/s1/approvals").json()[0]["id"] == pending_id
        r = client.post(
            "/sessions/s1/decisions", json={"decisions": {pending_id: {"type": "approve"}}}
        )
        assert r.json()["reply"] == "hecho"
        r = client.post(
            "/sessions/s1/decisions", json={"decisions": {pending_id: {"type": "approve"}}}
        )
        assert r.status_code == 409


def test_validacion_de_entrada():
    with _client() as client:
        assert client.post("/chat", json={"session_id": "a b", "message": "x"}).status_code == 422
        assert client.post("/chat", json={"session_id": "s1", "message": ""}).status_code == 422


def test_token_obligatorio_si_esta_configurado():
    with _client("hola", token="secreto-de-prueba") as client:
        body = {"session_id": "s1", "message": "hola"}
        assert client.post("/chat", json=body).status_code == 401
        headers = {"Authorization": "Bearer secreto-de-prueba"}
        assert client.post("/chat", json=body, headers=headers).status_code == 200
        assert client.get("/health").status_code == 200
