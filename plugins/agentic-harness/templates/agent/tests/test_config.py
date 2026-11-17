"""Carga de `.env` y validación de la configuración."""

import os

import pytest
from pydantic import ValidationError

from ..config import (
    AgentConfig,
    describe,
    format_validation_error,
    load_config_or_exit,
    load_env_file,
)


@pytest.fixture
def in_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    for var in ("AGENT_MODEL", "AGENT_MAX_TOKENS", "ANTHROPIC_API_KEY", "APP_ENV"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def test_valores_por_defecto():
    cfg = AgentConfig()
    assert cfg.model_id == "claude-opus-5-5"
    assert cfg.history_backend == "memory"


def test_carga_env_sin_pisar_el_entorno(in_tmp, monkeypatch: pytest.MonkeyPatch):
    (in_tmp / ".env").write_text("AGENT_MODEL=desde-archivo\nAGENT_MAX_TOKENS=1000\n")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "2000")
    assert load_env_file()
    cfg = AgentConfig()
    assert cfg.model_id == "desde-archivo"
    assert cfg.max_tokens == 2000  # el entorno real tiene prioridad sobre .env


def test_sin_env_no_falla(in_tmp):
    assert not load_env_file()


def test_variables_vacias_usan_el_valor_por_defecto(in_tmp):
    # Copiar .env.example tal cual deja muchas variables vacías: no debe romper el arranque.
    (in_tmp / ".env").write_text("AGENT_MAX_TOKENS=\nHISTORY_BACKEND=\nPORT=\n")
    load_env_file()
    cfg = AgentConfig()
    assert cfg.max_tokens == 4096
    assert cfg.port == 8000


def test_valores_invalidos_se_listan_todos(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_MAX_TOKENS", "-5")
    monkeypatch.setenv("HISTORY_BACKEND", "redis")
    monkeypatch.setenv("APP_ENV", "Prod")
    with pytest.raises(ValidationError) as error:
        AgentConfig()
    lines = format_validation_error(error.value)
    assert len(lines) == 3
    assert any(line.startswith("AGENT_MAX_TOKENS:") for line in lines)
    assert any(line.startswith("HISTORY_BACKEND:") for line in lines)
    assert any(line.startswith("APP_ENV:") for line in lines)


def test_postgres_sin_url_es_invalido(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HISTORY_BACKEND", "postgres")
    monkeypatch.setenv("AGENT_API_TOKEN", "token-que-no-debe-aparecer")
    with pytest.raises(ValidationError) as error:
        AgentConfig()
    lines = format_validation_error(error.value)
    assert lines == ["HISTORY_BACKEND=postgres requiere HISTORY_URL (cadena de conexión)"]


def test_problemas_de_ejecucion(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-solo-una")
    monkeypatch.setenv("APP_ENV", "prod")
    problems = AgentConfig().runtime_problems()
    assert any(p.startswith("ANTHROPIC_API_KEY") for p in problems)
    assert any(p.startswith("LANGFUSE_PUBLIC_KEY") for p in problems)
    assert any(p.startswith("AGENT_DRY_RUN") for p in problems)


def test_load_config_or_exit_termina_con_mensaje_claro(in_tmp, capsys):
    (in_tmp / ".env").write_text("AGENT_MAX_TOKENS=muchos\n")
    with pytest.raises(SystemExit) as salida:
        load_config_or_exit()
    assert salida.value.code == 2
    err = capsys.readouterr().err
    assert "AGENT_MAX_TOKENS" in err
    assert ".env.example" in err


def test_load_config_or_exit_valida_secretos(in_tmp, capsys):
    with pytest.raises(SystemExit):
        load_config_or_exit()
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_load_config_or_exit_correcto(in_tmp):
    (in_tmp / ".env").write_text("ANTHROPIC_API_KEY=clave-de-prueba\nAGENT_MODEL=otro\n")
    cfg = load_config_or_exit()
    assert cfg.model_id == "otro"
    assert os.environ["ANTHROPIC_API_KEY"] == "clave-de-prueba"  # visible para el SDK


def test_describe_no_revela_secretos(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-secreta")
    monkeypatch.setenv("AGENT_API_TOKEN", "token-secreto")
    monkeypatch.setenv("HISTORY_URL", "postgresql://u:clave@host/db")
    shown = describe(AgentConfig())
    texto = str(shown)
    assert "clave-secreta" not in texto
    assert "token-secreto" not in texto
    assert "u:clave" not in texto
    assert shown["ANTHROPIC_API_KEY"] == "definida"
