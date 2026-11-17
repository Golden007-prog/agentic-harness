"""Conversación por terminal.

    uv run python -m agents.__agent_name__.cli [--session ID] [--user ID]

Carga `.env` y valida la configuración al arrancar.

Comandos: /borrar (borra el histórico de la sesión), /salir.
"""

import argparse
import asyncio
import uuid

from .agent import AgentRunner, Decision, TurnResult, open_runner
from .config import load_config_or_exit


async def _ask(prompt: str) -> str:
    """input() en un hilo, para no bloquear el bucle de eventos."""
    return (await asyncio.to_thread(input, prompt)).strip()


async def _ask_decisions(result: TurnResult) -> dict[str, Decision]:
    decisions: dict[str, Decision] = {}
    for item in result.pending:
        print(f"\n[aprobación] {item.tool} {item.args}")
        answer = (await _ask("¿Aprobar? [s/N]: ")).lower()
        if answer in {"s", "si", "sí", "y", "yes"}:
            decisions[item.id] = Decision(type="approve")
        else:
            reason = await _ask("Motivo (opcional): ") or "El usuario rechazó la acción."
            decisions[item.id] = Decision(type="reject", message=reason)
    return decisions


async def _turn(runner: AgentRunner, session_id: str, text: str, user_id: str | None) -> None:
    result = await runner.chat(session_id, text, user_id)
    while result.status == "needs_approval":
        result = await runner.decide(session_id, await _ask_decisions(result), user_id)
    print(f"\n{result.reply}\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Conversa con el agente __agent_name__.")
    parser.add_argument("--session", default=f"cli-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--user", default=None)
    args = parser.parse_args()
    cfg = load_config_or_exit()  # carga .env y valida antes de arrancar

    async with open_runner(cfg) as runner:
        print(f"Sesión {args.session}. Escribe /borrar o /salir.")
        while True:
            try:
                text = await _ask("> ")
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            if text == "/salir":
                break
            if text == "/borrar":
                await runner.clear(args.session)
                print("Histórico borrado.")
                continue
            await _turn(runner, args.session, text, args.user)


if __name__ == "__main__":
    asyncio.run(main())
