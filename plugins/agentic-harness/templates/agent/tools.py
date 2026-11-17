"""Herramientas del agente.

Reglas: una responsabilidad por tool, argumentos tipados, docstring para el modelo y errores
devueltos como texto. Las tools con efectos externos van en TOOLS_REQUIRING_APPROVAL (aprobación
humana) y respetan `dry_run` (modo prueba).

Las dos tools de este archivo son ejemplos: sustitúyelas por las del agente.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain.agents.middleware import InterruptOnConfig
from langchain.tools import tool

from .config import get_config

MAX_NOTE_CHARS = 2000

# Almacén de ejemplo. Sustitúyelo por el sistema real (API, base de datos…) detrás de una interfaz.
NOTES: list[str] = []


@tool(parse_docstring=True)
def consultar_hora(zona_horaria: str) -> str:
    """Devuelve la fecha y hora actuales en una zona horaria.

    Úsala cuando el usuario pregunte qué hora o qué día es en un lugar. Devuelve la fecha en
    formato ISO 8601 o un mensaje de error si la zona no existe.

    Args:
        zona_horaria: Nombre IANA de la zona, por ejemplo "Europe/Madrid" o "America/Lima".
    """
    try:
        zone = ZoneInfo(zona_horaria.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return (
            f"Error: '{zona_horaria}' no es una zona horaria IANA válida. "
            "Usa un nombre como 'Europe/Madrid' o 'America/Lima'."
        )
    return datetime.now(zone).isoformat(timespec="minutes")


@tool(parse_docstring=True)
def registrar_nota(texto: str) -> str:
    """Guarda una nota del usuario. Tiene efectos externos y requiere aprobación humana.

    Úsala solo cuando el usuario pida guardar o apuntar algo de forma explícita. Devuelve una
    confirmación o un mensaje de error.

    Args:
        texto: Contenido de la nota, en texto plano y como máximo 2000 caracteres.
    """
    texto = texto.strip()
    if not texto:
        return "Error: la nota está vacía. Pide al usuario el contenido."
    if len(texto) > MAX_NOTE_CHARS:
        return f"Error: la nota supera {MAX_NOTE_CHARS} caracteres. Pide una versión más corta."
    if get_config().dry_run:
        return f"[modo prueba] La nota no se guardó de verdad ({len(texto)} caracteres)."
    NOTES.append(texto)
    return f"Nota guardada ({len(texto)} caracteres)."


TOOLS = [consultar_hora, registrar_nota]

# Tools con efectos externos: el agente se pausa y espera una decisión humana antes de ejecutarlas.
TOOLS_REQUIRING_APPROVAL: dict[str, InterruptOnConfig] = {
    "registrar_nota": {"allowed_decisions": ["approve", "reject"]},
}
