"""Trazas: desactivadas sin claves y enmascarado de datos sensibles."""

from ..config import AgentConfig
from ..observability import callbacks, mask_text, tracing_enabled


def test_sin_claves_no_hay_trazas():
    assert not tracing_enabled()
    assert callbacks(AgentConfig()) == []


def test_enmascara_datos_sensibles():
    texto = "correo ana@example.com, clave sk-ant-abcdefghijklmnop, tarjeta 4111 1111 1111 1111"
    enmascarado = mask_text(texto)
    assert "ana@example.com" not in enmascarado
    assert "sk-ant-abcdefghijklmnop" not in enmascarado
    assert "4111 1111 1111 1111" not in enmascarado
    assert "2026-11-17T10:00" == mask_text("2026-11-17T10:00")
