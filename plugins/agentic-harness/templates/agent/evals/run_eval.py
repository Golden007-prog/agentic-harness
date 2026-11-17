"""Evaluación del agente sobre un conjunto de casos.

    uv run python -m agents.__agent_name__.evals.run_eval [--judge] [--min-score 0.8]
    uv run python -m agents.__agent_name__.evals.run_eval --upload mi-dataset   # sube dataset.jsonl
    uv run python -m agents.__agent_name__.evals.run_eval --dataset mi-dataset  # usa el de Langfuse

Con claves de Langfuse, cada ejecución queda registrada como experimento (comparable entre versiones
de prompt o modelo). Sin claves, se ejecuta en local e imprime los resultados.
Llama al modelo real: cuesta dinero. Las tools con efectos corren en modo prueba (AGENT_DRY_RUN).

Formato de cada línea de dataset.jsonl:
    {"input": str, "expected_output": str, "metadata": {"expect_tools": [...],
     "forbid_tools": [...], "expect_contains": [...]}}
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from statistics import mean
from typing import Any

from langchain.messages import AIMessage
from pydantic import BaseModel, Field

from ..agent import Decision, open_runner
from ..config import AGENT_NAME, build_model, get_config, load_config_or_exit
from ..observability import tracing_enabled
from ..prompts import PROMPT_VERSION

DATASET = Path(__file__).with_name("dataset.jsonl")


def load_items(path: Path = DATASET) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


async def run_case(question: str) -> dict[str, Any]:
    """Ejecuta un caso en una sesión nueva; aprueba las acciones (corren en modo prueba)."""
    cfg = get_config().model_copy(update={"history_backend": "memory"})
    session_id = f"eval-{uuid.uuid4().hex[:12]}"
    async with open_runner(cfg) as runner:
        result = await runner.chat(session_id, question)
        rounds = 0
        while result.status == "needs_approval" and rounds < 5:
            decisions = {p.id: Decision(type="approve") for p in result.pending}
            result = await runner.decide(session_id, decisions)
            rounds += 1
        state = await runner.agent.aget_state({"configurable": {"thread_id": session_id}})
    tools = [
        call["name"]
        for m in state.values.get("messages", [])
        if isinstance(m, AIMessage)
        for call in m.tool_calls
    ]
    return {"reply": result.reply or "", "status": result.status, "tools": tools}


def _item_parts(item: Any) -> tuple[Any, Any, dict[str, Any]]:
    if isinstance(item, dict):
        return item["input"], item.get("expected_output"), item.get("metadata") or {}
    return item.input, item.expected_output, item.metadata or {}


# --- Evaluadores (firma del experiment runner de Langfuse) ---------------------------------
def _evaluation(name: str, value: float, comment: str = ""):
    from langfuse import Evaluation

    return Evaluation(name=name, value=value, comment=comment)


def tool_usage(*, output: dict, metadata: dict | None = None, **_: Any):
    meta = metadata or {}
    called = set(output["tools"])
    missing = set(meta.get("expect_tools", [])) - called
    forbidden = set(meta.get("forbid_tools", [])) & called
    ok = not missing and not forbidden
    return _evaluation(
        "tool_usage", float(ok), f"faltan={sorted(missing)} prohibidas={sorted(forbidden)}"
    )


def contains(*, output: dict, metadata: dict | None = None, **_: Any):
    expected = (metadata or {}).get("expect_contains", [])
    reply = output["reply"].lower()
    missing = [t for t in expected if t.lower() not in reply]
    return _evaluation("contains", float(not missing), f"faltan={missing}")


def completed(*, output: dict, **_: Any):
    return _evaluation("completed", float(output["status"] == "completed"), output["status"])


class JudgeVerdict(BaseModel):
    score: float = Field(ge=0, le=1, description="1 si la respuesta cumple el criterio, 0 si no.")
    reason: str


async def llm_judge(*, input: Any, output: dict, expected_output: Any = None, **_: Any):
    """Juez con LLM: compara la respuesta con el criterio esperado."""
    if not expected_output:
        return _evaluation("judge", 1.0, "sin criterio")
    judge = build_model(get_config()).with_structured_output(JudgeVerdict)
    verdict = await judge.ainvoke(
        "Evalúa si la RESPUESTA cumple el CRITERIO. Sé estricto.\n"
        f"PREGUNTA: {input}\nCRITERIO: {expected_output}\nRESPUESTA: {output['reply']}"
    )
    return _evaluation("judge", verdict.score, verdict.reason)


async def task(*, item: Any, **_: Any) -> dict[str, Any]:
    question, _expected, _meta = _item_parts(item)
    return await run_case(question)


# --- Ejecución ------------------------------------------------------------------------------
async def _run_local(items: list[dict[str, Any]], evaluators: list) -> list[list[Any]]:
    scores = []
    for item in items:
        question, expected, meta = _item_parts(item)
        output = await run_case(question)
        row = []
        for evaluator in evaluators:
            result = evaluator(
                input=question, output=output, expected_output=expected, metadata=meta
            )
            row.append(await result if asyncio.iscoroutine(result) else result)
        scores.append(row)
        print(f"- {question!r}: " + ", ".join(f"{e.name}={e.value:g}" for e in row))
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Evalúa el agente {AGENT_NAME}.")
    parser.add_argument("--judge", action="store_true", help="Añade un juez LLM (más coste).")
    parser.add_argument("--dataset", help="Nombre de un dataset de Langfuse en lugar del local.")
    parser.add_argument("--upload", metavar="NOMBRE", help="Sube dataset.jsonl a Langfuse y sale.")
    parser.add_argument("--min-score", type=float, default=0.0, help="Falla si la media es menor.")
    args = parser.parse_args()

    # Las tools con efectos leen AGENT_DRY_RUN: en evaluación nunca actúan de verdad.
    os.environ["AGENT_DRY_RUN"] = "true"
    load_config_or_exit()  # carga .env y valida (incluida ANTHROPIC_API_KEY)

    evaluators = [completed, tool_usage, contains] + ([llm_judge] if args.judge else [])
    run_name = f"{AGENT_NAME}-prompt-v{PROMPT_VERSION}-{get_config().model_id}"

    if not tracing_enabled():
        if args.dataset or args.upload:
            print("--dataset y --upload requieren LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY.")
            return 2
        print(f"Langfuse no configurado: evaluación local ({run_name}).")
        rows = asyncio.run(_run_local(load_items(), evaluators))
        evaluations = [e for row in rows for e in row]
    else:
        from langfuse import get_client

        langfuse = get_client()
        if args.upload:
            langfuse.create_dataset(name=args.upload, description=f"Casos de {AGENT_NAME}")
            for item in load_items():
                langfuse.create_dataset_item(dataset_name=args.upload, **item)
            langfuse.flush()
            print(f"Dataset '{args.upload}' subido.")
            return 0
        common = {
            "name": f"{AGENT_NAME}-eval",
            "run_name": run_name,
            "task": task,
            "evaluators": evaluators,
            "max_concurrency": 4,
            "metadata": {"prompt_version": PROMPT_VERSION, "model": get_config().model_id},
        }
        if args.dataset:
            result = langfuse.get_dataset(args.dataset).run_experiment(**common)
        else:
            result = langfuse.run_experiment(data=load_items(), **common)
        print(result.format())
        langfuse.flush()
        evaluations = [e for r in result.item_results for e in r.evaluations]

    numeric = [float(e.value) for e in evaluations if isinstance(e.value, int | float)]
    average = mean(numeric) if numeric else 0.0
    print(f"Media: {average:.2f} (mínimo exigido {args.min_score:.2f})")
    return 0 if average >= args.min_score else 1


if __name__ == "__main__":
    sys.exit(main())
