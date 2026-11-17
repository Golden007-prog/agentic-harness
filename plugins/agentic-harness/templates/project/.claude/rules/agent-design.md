# Diseño de agentes

Stack por defecto: Python 3.12+, `uv`, LangChain/LangGraph, modelo de Anthropic, trazas en Langfuse. El proveedor de nube no está decidido: el código es agnóstico (ver `deployment.md`).

## Punto de partida: el esqueleto del plugin
Todo agente nuevo se crea con `/agentic-harness:new-agent`, que copia un esqueleto probado (`scaffold-agent.sh`). El esqueleto ya resuelve histórico, límites, aprobación humana, trazas, CLI, servidor HTTP, evaluaciones y pruebas. Adapta prompts, tools y casos de evaluación; no reescribas desde cero lo que ya resuelve. Si la documentación vigente contradice el esqueleto, dilo antes de cambiarlo.

## Componentes obligatorios

### 1. Instrucciones (prompt) — `prompts.py`
- El system prompt vive aquí como plantilla con nombre; nunca incrustado en la lógica.
- Cubre: rol y objetivo, qué puede y qué no puede hacer, cuándo usar cada tool, que el contenido de las tools es dato y no instrucción, formato de la respuesta y qué hacer cuando no sabe o le falta información.
- Las partes variables (fecha, idioma, datos del usuario) entran como parámetros y se resuelven en cada llamada (`dynamic_prompt`).
- Lleva `PROMPT_VERSION`, que viaja en las trazas y en el nombre de cada evaluación. Súbela en cada cambio del texto.

### 2. Configuración del modelo — `config.py`
- Un único objeto tipado (`pydantic-settings`) con: proveedor, ID del modelo, máximo de tokens de salida, timeout, reintentos, límites del bucle y backend del histórico.
- Valores por defecto: proveedor Anthropic, modelo `claude-opus-5-5`. Todo se sobrescribe por entorno (ver `.env.example`).
- Los puntos de entrada llaman a `load_config_or_exit()`: carga `.env` sin pisar el entorno real, trata las variables vacías como no definidas, valida tipos, rangos y combinaciones, y exige los secretos de ejecución (`ANTHROPIC_API_KEY`). Si algo falla, el proceso no arranca y lista cada problema sin mostrar secretos.
- Las pruebas no leen `.env`; las de integración lo cargan con la fixture `real_env`.
- El modelo se construye solo en `build_model()`. Cambiar de modelo es cambiar configuración, no código.
- Confirma en `reference-langchain` qué parámetros admite la clase del modelo antes de exponer uno nuevo; no añadas parámetros que no se usan.

### 3. Histórico de conversación — `memory.py`
- Cada conversación se identifica con un `session_id` (el `thread_id` del checkpointer). Mismo `session_id`, mismo histórico; otro distinto, nada.
- Backends por `HISTORY_BACKEND`: `memory` (desarrollo y pruebas), `sqlite` (local) y `postgres` (producción). La lógica del agente no conoce el backend.
- Límite: `HISTORY_STRATEGY=trim` (recorta desde un mensaje humano) o `summarize`. El system prompt no está en el histórico y nunca se recorta; el recorte no separa una llamada a tool de su resultado.
- Las llamadas a tool que quedaron sin resultado (turno cortado) se reparan antes de la siguiente llamada al modelo.
- El `session_id` va a Langfuse para agrupar las trazas. `AgentRunner.clear()` borra el histórico de una sesión.

## Estructura de un agente
```
agents/<nombre>/
├── agent.py          # build_agent(), AgentRunner (chat/decide/clear por session_id), open_runner()
├── prompts.py        # system prompt, plantilla y PROMPT_VERSION
├── config.py         # configuración tipada y build_model()
├── memory.py         # backends del histórico, recorte y borrado
├── tools.py          # tools, TOOLS y TOOLS_REQUIRING_APPROVAL
├── guards.py         # límites por turno, presupuesto de tokens, errores de tools, aprobación humana
├── observability.py  # Langfuse: atributos de traza, enmascarado y flush
├── cli.py            # conversación por terminal
├── server.py         # API HTTP (FastAPI)
├── evals/            # dataset.jsonl y run_eval.py
└── tests/            # tools, histórico, flujo, servidor, prompts e integración
```

## Principios
- Empieza por el agente más simple que resuelva el caso: un agente con tools antes que un grafo, un grafo antes que varios agentes.
- Cada tool hace una sola cosa, tiene tipos en sus argumentos y un docstring que el modelo pueda entender: qué hace, cuándo usarla y qué devuelve.
- Las tools devuelven errores como texto útil para el modelo; las excepciones inesperadas las convierte `ToolErrorMiddleware` en texto sin detalles internos.
- Las tools con efectos externos (escribir, enviar, cobrar, borrar) van en `TOOLS_REQUIRING_APPROVAL` (aprobación humana por llamada) y respetan `AGENT_DRY_RUN`.
- Todo turno tiene límite de llamadas al modelo y a tools, timeout, y cada sesión un presupuesto de tokens.

## Definición de terminado
Un agente no está terminado sin:
- Una prueba por tool (caso normal, entrada inválida, fallo del servicio simulado).
- Pruebas de que el histórico se mantiene dentro de una sesión, se aísla entre sesiones y se recorta sin romper parejas llamada/resultado.
- Prueba del flujo completo con modelo falso, incluida la aprobación humana de las tools con efectos.
- Pruebas `integration` con el modelo real, incluida la de resistencia a inyección de instrucciones en resultados de tools.
- Un conjunto de evaluación (`evals/dataset.jsonl`) con casos reales del dominio y su resultado en `run_eval`.
- Trazas visibles en Langfuse.
- `scripts/ci.sh` en verde.
