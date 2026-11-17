"""Una prueba por tool: caso normal, entrada inválida y modo prueba."""

import pytest

from .. import tools
from ..config import get_config


def test_consultar_hora_zona_valida():
    result = tools.consultar_hora.invoke({"zona_horaria": "America/Lima"})
    assert result.endswith("-05:00")


def test_consultar_hora_zona_invalida_devuelve_texto():
    result = tools.consultar_hora.invoke({"zona_horaria": "Narnia/Centro"})
    assert result.startswith("Error:")


def test_registrar_nota_en_modo_prueba_no_guarda():
    tools.NOTES.clear()
    result = tools.registrar_nota.invoke({"texto": "llamar a Ana"})
    assert "[modo prueba]" in result
    assert tools.NOTES == []


def test_registrar_nota_real(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_DRY_RUN", "false")
    get_config.cache_clear()
    tools.NOTES.clear()
    assert tools.registrar_nota.invoke({"texto": "llamar a Ana"}).startswith("Nota guardada")
    assert tools.NOTES == ["llamar a Ana"]


@pytest.mark.parametrize("texto", ["", "   ", "x" * (tools.MAX_NOTE_CHARS + 1)])
def test_registrar_nota_rechaza_entradas_invalidas(texto: str):
    assert tools.registrar_nota.invoke({"texto": texto}).startswith("Error:")


def test_tools_con_efectos_requieren_aprobacion():
    nombres = {t.name for t in tools.TOOLS}
    assert set(tools.TOOLS_REQUIRING_APPROVAL) <= nombres
    assert "registrar_nota" in tools.TOOLS_REQUIRING_APPROVAL
