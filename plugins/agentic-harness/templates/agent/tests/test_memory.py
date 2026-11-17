"""Histórico: persistencia en la sesión, aislamiento entre sesiones, recorte y borrado."""

import os
import uuid

import pytest
from langchain.messages import AIMessage, HumanMessage, ToolMessage

from ..config import AgentConfig
from ..memory import open_checkpointer, repair_tool_pairs, trim_history
from .conftest import call, fake_model, history


async def test_misma_sesion_conserva_turnos_y_otra_sesion_no(make_runner):
    async with make_runner(fake_model("hola Ana", "te llamas Ana", "no lo sé")) as runner:
        await runner.chat("s1", "me llamo Ana")
        await runner.chat("s1", "¿cómo me llamo?")
        await runner.chat("s2", "¿cómo me llamo?")

        s1 = [m.text for m in await history(runner, "s1")]
        s2 = [m.text for m in await history(runner, "s2")]
    assert s1 == ["me llamo Ana", "hola Ana", "¿cómo me llamo?", "te llamas Ana"]
    assert s2 == ["¿cómo me llamo?", "no lo sé"]


async def test_borrar_sesion(make_runner):
    async with make_runner(fake_model("hola")) as runner:
        await runner.chat("s1", "hola")
        await runner.clear("s1")
        assert await history(runner, "s1") == []


async def test_recorte_dentro_del_agente_conserva_ultimo_turno(make_runner):
    respuestas = ["r" * 400 for _ in range(6)]
    async with make_runner(fake_model(*respuestas), history_max_tokens=300) as runner:
        for i in range(6):
            await runner.chat("s1", f"pregunta {i} " + "x" * 400)
        mensajes = await history(runner, "s1")
    assert isinstance(mensajes[0], HumanMessage)
    assert mensajes[0].text.startswith("pregunta 5")
    assert len(mensajes) == 2


def test_recorte_no_separa_llamada_y_resultado():
    mensajes = [
        HumanMessage("a" * 200, id="h1"),
        AIMessage("b" * 200, id="a1"),
        HumanMessage("¿hora?", id="h2"),
        AIMessage("", tool_calls=[{"name": "consultar_hora", "args": {}, "id": "c1"}], id="a2"),
        ToolMessage("10:00", tool_call_id="c1", id="t1"),
    ]
    recortado = trim_history(mensajes, max_tokens=60)
    assert [m.id for m in recortado] == ["h2", "a2", "t1"]


def test_repara_llamadas_sin_resultado():
    mensajes = [
        HumanMessage("guarda", id="h1"),
        AIMessage("", tool_calls=[{"name": "registrar_nota", "args": {}, "id": "c1"}], id="a1"),
        HumanMessage("¿sigues?", id="h2"),
    ]
    reparado, cambiado = repair_tool_pairs(mensajes)
    assert cambiado
    assert isinstance(reparado[2], ToolMessage) and reparado[2].tool_call_id == "c1"
    assert reparado[3].id == "h2"


async def test_turno_cortado_no_rompe_el_siguiente(make_runner):
    """Una llamada a tool sin resultado (turno interrumpido) se repara antes de llamar al modelo."""
    async with make_runner(fake_model("sigo aquí")) as runner:
        config = {"configurable": {"thread_id": "s1"}}
        await runner.agent.aupdate_state(
            config,
            {
                "messages": [
                    HumanMessage("hora"),
                    call("consultar_hora", zona_horaria="UTC"),
                ]
            },
        )
        result = await runner.chat("s1", "¿sigues?")
        mensajes = await history(runner, "s1")
    assert result.reply == "sigo aquí"
    assert any(isinstance(m, ToolMessage) and m.status == "error" for m in mensajes)


async def test_backend_sqlite_persiste_entre_procesos(tmp_path):
    from ..agent import AgentRunner, build_agent

    cfg = AgentConfig(HISTORY_BACKEND="sqlite", HISTORY_URL=str(tmp_path / "h.sqlite"))
    for respuesta in ("uno", "dos"):
        async with open_checkpointer(cfg) as checkpointer:
            agent = build_agent(cfg=cfg, model=fake_model(respuesta), checkpointer=checkpointer)
            runner = AgentRunner(agent, checkpointer, cfg)
            await runner.chat("s1", "hola")
            textos = [m.text for m in await history(runner, "s1")]
    assert textos == ["hola", "uno", "hola", "dos"]


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("HISTORY_TEST_POSTGRES_URL"), reason="requiere HISTORY_TEST_POSTGRES_URL"
)
async def test_backend_postgres_persiste_aisla_y_borra():
    pytest.importorskip("langgraph.checkpoint.postgres")
    from ..agent import AgentRunner, build_agent

    sesion = f"pg-{uuid.uuid4().hex[:8]}"
    cfg = AgentConfig(
        HISTORY_BACKEND="postgres", HISTORY_URL=os.environ["HISTORY_TEST_POSTGRES_URL"]
    )
    for respuesta in ("uno", "dos"):
        async with open_checkpointer(cfg) as checkpointer:
            agent = build_agent(cfg=cfg, model=fake_model(respuesta), checkpointer=checkpointer)
            runner = AgentRunner(agent, checkpointer, cfg)
            await runner.chat(sesion, "hola")
            textos = [m.text for m in await history(runner, sesion)]
    assert textos == ["hola", "uno", "hola", "dos"]
    async with open_checkpointer(cfg) as checkpointer:
        runner = AgentRunner(
            build_agent(cfg=cfg, model=fake_model(), checkpointer=checkpointer), checkpointer, cfg
        )
        assert await history(runner, f"{sesion}-otra") == []
        await runner.clear(sesion)
        assert await history(runner, sesion) == []
