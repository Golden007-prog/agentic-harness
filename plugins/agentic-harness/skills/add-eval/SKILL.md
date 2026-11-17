---
name: add-eval
description: Crea o amplía el conjunto de evaluación de un agente (casos, evaluadores y juez LLM) y lo ejecuta, en local o como experimento de Langfuse, para medir si responde bien y comparar versiones de prompt o modelo. Usar cuando el usuario pida evaluar, medir calidad, comparar prompts o modelos, crear un dataset de pruebas o detectar regresiones de un agente.
argument-hint: <agente> [qué comportamiento evaluar]
---
# Evaluar un agente

Petición: $ARGUMENTS

1. Lee `agents/<agente>/evals/run_eval.py`, `evals/dataset.jsonl`, `prompts.py` y `tools.py`.
2. Consulta en `langfuse-docs` la API vigente de experimentos (`run_experiment`, `Evaluation`, datasets) si vas a cambiar el script.
3. Escribe casos en `evals/dataset.jsonl`, uno por línea:
   `{"input": ..., "expected_output": "<criterio verificable>", "metadata": {"expect_tools": [...], "forbid_tools": [...], "expect_contains": [...]}}`
   - Cubre: el camino feliz de cada tool, preguntas fuera de alcance, datos que faltan, errores de tools, peticiones ambiguas y al menos un intento de inyección de instrucciones.
   - Prefiere casos reales del dominio (pide ejemplos al usuario si no los hay) frente a casos inventados.
   - `expected_output` describe el criterio que comprueba el juez LLM, no una respuesta literal.
4. Si un comportamiento no se mide con los evaluadores existentes (`completed`, `tool_usage`, `contains`, `judge`), añade uno en `run_eval.py` con la firma de Langfuse (`*, input, output, expected_output, metadata, **kwargs`) que devuelva `Evaluation`.
5. Ejecuta (llama al modelo real: avisa del coste y pide confirmación):
   - `uv run python -m agents.<agente>.evals.run_eval` (añade `--judge` para el juez LLM).
   - Con claves de Langfuse, la ejecución queda como experimento con `PROMPT_VERSION` y modelo en el nombre. `--upload <nombre>` sube los casos como dataset; `--dataset <nombre>` evalúa sobre él.
   - `--min-score` hace que el script falle por debajo de un umbral (lo usa `scripts/ci.sh --evals`).
6. Informa la media por evaluador, los casos que fallan y qué cambio de prompt o tool lo explicaría. No cambies el prompt sin volver a evaluar.
