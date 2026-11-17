"""Configuración del agente: un único objeto tipado, sobrescribible por variables de entorno.

Carga y validación:
- Los puntos de entrada (CLI, servidor, evaluación) llaman a `load_config_or_exit()`, que carga
  `.env` en el entorno del proceso sin pisar las variables ya definidas y valida todo al arrancar.
- Una variable vacía (`AGENT_MAX_TOKENS=`) equivale a no definida: se usa el valor por defecto.
- Si algo es inválido o falta un secreto obligatorio, el proceso no arranca y lista cada problema.
- Comprobar la configuración sin arrancar el agente: `uv run python -m agents.__agent_name__.config`

El modelo se construye solo aquí (`build_model`). Cambiar de modelo es cambiar configuración.
"""

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from pydantic import AliasChoices, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_NAME = "__agent_name__"

# Secretos que leen directamente las librerías (Anthropic SDK, Langfuse) desde el entorno.
SECRET_VARS = ("ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "AGENT_API_TOKEN")
# Variables de AgentConfig cuyo valor nunca se muestra en mensajes de error.
SENSITIVE_FIELDS = {"AGENT_API_TOKEN", "HISTORY_URL"}


def _env(name: str) -> AliasChoices:
    return AliasChoices(name)


class AgentConfig(BaseSettings):
    """Lee la configuración del entorno. Los nombres de variable están en `.env.example`."""

    model_config = SettingsConfigDict(
        extra="ignore", protected_namespaces=(), populate_by_name=True, env_ignore_empty=True
    )

    # Modelo
    provider: Literal["anthropic"] = Field("anthropic", validation_alias=_env("AGENT_PROVIDER"))
    model_id: str = Field("claude-opus-5-5", min_length=1, validation_alias=_env("AGENT_MODEL"))
    max_tokens: int = Field(4096, gt=0, validation_alias=_env("AGENT_MAX_TOKENS"))
    request_timeout_s: float = Field(60.0, gt=0, validation_alias=_env("AGENT_TIMEOUT_S"))
    max_retries: int = Field(2, ge=0, validation_alias=_env("AGENT_MAX_RETRIES"))

    # Límites del bucle del agente
    run_timeout_s: float = Field(180.0, gt=0, validation_alias=_env("AGENT_RUN_TIMEOUT_S"))
    max_model_calls_per_turn: int = Field(10, gt=0, validation_alias=_env("AGENT_MAX_MODEL_CALLS"))
    max_tool_calls_per_turn: int = Field(20, gt=0, validation_alias=_env("AGENT_MAX_TOOL_CALLS"))
    session_token_budget: int = Field(
        500_000, ge=0, validation_alias=_env("AGENT_SESSION_TOKEN_BUDGET")
    )  # 0 = sin límite

    # Tools con efectos externos: en modo prueba simulan la acción en vez de ejecutarla
    dry_run: bool = Field(True, validation_alias=_env("AGENT_DRY_RUN"))

    # Histórico de conversación
    history_backend: Literal["memory", "sqlite", "postgres"] = Field(
        "memory", validation_alias=_env("HISTORY_BACKEND")
    )
    history_url: str = Field("", repr=False, validation_alias=_env("HISTORY_URL"))
    history_strategy: Literal["trim", "summarize"] = Field(
        "trim", validation_alias=_env("HISTORY_STRATEGY")
    )
    history_max_tokens: int = Field(12_000, gt=0, validation_alias=_env("HISTORY_MAX_TOKENS"))

    # Entorno y trazas
    app_env: str = Field("dev", pattern=r"^[a-z0-9_-]{1,40}$", validation_alias=_env("APP_ENV"))
    release: str = Field("", validation_alias=_env("APP_RELEASE"))  # versión o commit

    # Servidor HTTP
    api_token: str = Field("", repr=False, validation_alias=_env("AGENT_API_TOKEN"))
    port: int = Field(8000, ge=1, le=65535, validation_alias=_env("PORT"))

    @model_validator(mode="after")
    def _check_combinations(self) -> Self:
        if self.history_backend == "postgres" and not self.history_url:
            raise ValueError("HISTORY_BACKEND=postgres requiere HISTORY_URL (cadena de conexión)")
        return self

    def runtime_problems(self) -> list[str]:
        """Secretos y combinaciones que solo se exigen al ejecutar con el modelo real."""
        problems = []
        if self.provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            problems.append("ANTHROPIC_API_KEY: falta (necesaria para llamar al modelo)")
        langfuse = [bool(os.getenv(v)) for v in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")]
        if any(langfuse) and not all(langfuse):
            problems.append(
                "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY: define las dos o ninguna "
                "(sin ninguna, las trazas se desactivan)"
            )
        if self.app_env == "prod" and self.dry_run:
            problems.append("AGENT_DRY_RUN=true en prod: las tools con efectos no actuarían")
        return problems


@lru_cache
def get_config() -> AgentConfig:
    """Configuración del proceso.

    En pruebas, llama a `get_config.cache_clear()` después de cambiar el entorno.
    """
    return AgentConfig()


def load_env_file(path: str | Path = ".env") -> bool:
    """Carga un archivo .env en el entorno del proceso. Las variables ya definidas tienen prioridad.

    Devuelve False si el archivo no existe (lo normal en contenedores y en CI).
    """
    path = Path(path)
    if not path.is_file():
        return False
    load_dotenv(path, override=False)
    return True


def format_validation_error(error: ValidationError) -> list[str]:
    """Convierte los errores de Pydantic en líneas `VARIABLE: problema`."""
    lines = []
    for item in error.errors():
        variable = ".".join(str(part) for part in item["loc"])
        message = item["msg"].removeprefix("Value error, ")
        if not variable:  # error de combinación: `input` contiene toda la config, con secretos
            lines.append(message)
        elif variable in SENSITIVE_FIELDS:
            lines.append(f"{variable}: {message}")
        else:
            lines.append(f"{variable}: {message} (valor recibido: {item.get('input')!r})")
    return lines


def load_config_or_exit(
    env_file: str | Path = ".env", *, require_runtime: bool = True
) -> AgentConfig:
    """Carga `.env`, valida la configuración y termina el proceso con un mensaje claro si falla."""
    load_env_file(env_file)
    get_config.cache_clear()
    try:
        cfg = get_config()
    except ValidationError as error:
        problems = format_validation_error(error)
    else:
        problems = cfg.runtime_problems() if require_runtime else []
        if not problems:
            return cfg
    print(f"Configuración inválida de {AGENT_NAME}:", file=sys.stderr)
    for line in problems:
        print(f"  - {line}", file=sys.stderr)
    print(
        "Revisa tu .env (plantilla en .env.example) o las variables del entorno.", file=sys.stderr
    )
    raise SystemExit(2)


def describe(cfg: AgentConfig) -> dict[str, str]:
    """Configuración efectiva para mostrar, sin revelar secretos."""
    shown = {
        name: str(getattr(cfg, name))
        for name in AgentConfig.model_fields
        if name not in {"api_token", "history_url"}
    }
    shown["history_url"] = "definida" if cfg.history_url else "vacía"
    for var in SECRET_VARS:
        shown[var] = "definida" if os.getenv(var) else "no definida"
    return shown


def build_model(cfg: AgentConfig) -> BaseChatModel:
    """Único punto donde se instancia el modelo."""
    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=cfg.model_id,
            max_tokens=cfg.max_tokens,
            timeout=cfg.request_timeout_s,
            max_retries=cfg.max_retries,
        )
    raise ValueError(f"Proveedor de modelo no soportado: {cfg.provider}")


def main() -> None:
    """Valida la configuración y la muestra: `python -m agents.__agent_name__.config`."""
    cfg = load_config_or_exit()
    print(f"Configuración válida de {AGENT_NAME}:")
    for key, value in describe(cfg).items():
        print(f"  {key} = {value}")


if __name__ == "__main__":
    main()
