"""Instrucciones: versión, secciones obligatorias y partes variables."""

from ..prompts import PROMPT_VERSION, build_system_prompt
from ..tools import TOOLS


def test_prompt_tiene_version():
    assert PROMPT_VERSION.strip()


def test_prompt_cubre_secciones_obligatorias():
    prompt = build_system_prompt()
    for seccion in (
        "Rol y objetivo",
        "Qué no puedes hacer",
        "Uso de herramientas",
        "Datos frente a instrucciones",
        "Formato de respuesta",
        "Cuando no sabes",
    ):
        assert seccion in prompt


def test_prompt_menciona_cada_tool():
    prompt = build_system_prompt()
    for t in TOOLS:
        assert f"`{t.name}`" in prompt


def test_partes_variables():
    prompt = build_system_prompt(language="inglés", tz="America/Lima")
    assert "Responde en inglés" in prompt
    assert "{" not in prompt
