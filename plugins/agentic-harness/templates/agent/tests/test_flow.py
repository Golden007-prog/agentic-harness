"""Flujo completo con modelo falso: tools, aprobación humana, límites y timeout."""

import asyncio

import pytest
from langchain.messages import AIMessage, ToolMessage
from langchain.tools import tool

from .. import tools
from ..agent import Decision
from ..guards import BUDGET_EXHAUSTED_REPLY
from .conftest import FakeToolCallingModel, call, fake_model, history


async def test_llama_tool_y_responde(make_runner):
    model = fake_model(call("consultar_hora", zona_horaria="UTC"), "Son las 10:00 en UTC.")
    async with make_runner(model) as runner:
        result = await runner.chat("s1", "¿hora en UTC?")
        mensajes = await history(runner, "s1")
    assert result.status == "completed"
    assert result.reply == "Son las 10:00 en UTC."
    assert any(isinstance(m, ToolMessage) and m.name == "consultar_hora" for m in mensajes)


async def test_tool_con_efectos_espera_aprobacion_y_se_ejecuta_al_aprobar(make_runner):
    tools.NOTES.clear()
    model = fake_model(call("registrar_nota", texto="comprar pan"), "Nota guardada.")
    async with make_runner(model) as runner:
        result = await runner.chat("s1", "apunta comprar pan")
        assert result.status == "needs_approval"
        assert result.pending[0].tool == "registrar_nota"
        assert result.pending[0].args == {"texto": "comprar pan"}

        final = await runner.decide("s1", {result.pending[0].id: Decision(type="approve")})
        mensajes = await history(runner, "s1")
    assert final.status == "completed"
    resultado_tool = next(m for m in mensajes if isinstance(m, ToolMessage))
    assert "[modo prueba]" in resultado_tool.text


async def test_rechazo_no_ejecuta_la_tool(make_runner):
    model = fake_model(call("registrar_nota", texto="x"), "Entendido, no la guardo.")
    async with make_runner(model) as runner:
        result = await runner.chat("s1", "apunta x")
        decision = Decision(type="reject", message="No quiero guardarla.")
        final = await runner.decide("s1", {result.pending[0].id: decision})
        mensajes = await history(runner, "s1")
    resultado_tool = next(m for m in mensajes if isinstance(m, ToolMessage))
    assert resultado_tool.status == "error"
    assert "No quiero guardarla." in resultado_tool.text
    assert final.reply == "Entendido, no la guardo."


async def test_mensaje_nuevo_con_aprobacion_abierta_no_avanza(make_runner):
    model = fake_model(call("registrar_nota", texto="x"))
    async with make_runner(model) as runner:
        primera = await runner.chat("s1", "apunta x")
        segunda = await runner.chat("s1", "¿y bien?")
        with pytest.raises(ValueError):
            await runner.decide("s1", {"id-inventado": Decision(type="approve")})
    assert segunda.status == "needs_approval"
    assert segunda.pending[0].id == primera.pending[0].id


async def test_error_de_tool_vuelve_al_modelo_como_texto(make_runner):
    @tool
    def rota(dato: str) -> str:
        """Tool de prueba que siempre falla."""
        raise ValueError("detalle interno secreto")

    model = fake_model(call("rota", dato="a"), "No pude completarlo.")
    async with make_runner(model, tools=[rota]) as runner:
        result = await runner.chat("s1", "usa rota")
        mensajes = await history(runner, "s1")
    error = next(m for m in mensajes if isinstance(m, ToolMessage))
    assert "ValueError" in error.text
    assert "secreto" not in error.text
    assert result.reply == "No pude completarlo."


async def test_limite_de_llamadas_al_modelo_corta_el_bucle(make_runner):
    model = fake_model(*[call("consultar_hora", f"c{i}", zona_horaria="UTC") for i in range(10)])
    async with make_runner(model, max_model_calls_per_turn=3) as runner:
        result = await runner.chat("s1", "bucle")
        mensajes = await history(runner, "s1")
    llamadas = [m for m in mensajes if isinstance(m, AIMessage) and m.tool_calls]
    assert result.status == "completed"
    assert len(llamadas) == 3


async def test_presupuesto_de_tokens_por_sesion(make_runner):
    usage = {"input_tokens": 80, "output_tokens": 40, "total_tokens": 120}
    model = fake_model(AIMessage("primera", usage_metadata=usage), "no debería llegar")
    async with make_runner(model, session_token_budget=100) as runner:
        primera = await runner.chat("s1", "hola")
        segunda = await runner.chat("s1", "otra")
    assert primera.reply == "primera"
    assert segunda.reply == BUDGET_EXHAUSTED_REPLY


class SlowModel(FakeToolCallingModel):
    async def _agenerate(self, *args, **kwargs):
        await asyncio.sleep(1)
        return await super()._agenerate(*args, **kwargs)


async def test_timeout_del_turno(make_runner):
    model = SlowModel(messages=iter(["tarde"]))
    async with make_runner(model, run_timeout_s=0.1) as runner:
        result = await runner.chat("s1", "hola")
    assert result.status == "timeout"


async def test_session_id_invalido(make_runner):
    async with make_runner(fake_model("x")) as runner:
        with pytest.raises(ValueError):
            await runner.chat("../otra sesión", "hola")
