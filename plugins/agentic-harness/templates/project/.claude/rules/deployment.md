# Despliegue (proveedor de nube sin decidir)

El proveedor de nube todavía no está elegido. El código de los agentes debe poder ejecutarse en cualquiera.

- No asumas ni propongas un proveedor concreto, y no añadas SDKs, servicios gestionados ni CLIs específicos de una nube sin que el usuario lo pida.
- Toda la configuración entra por variables de entorno (ver `config.py`); nada depende de metadatos o servicios de una plataforma.
- El agente se empaqueta como contenedor estándar (`Dockerfile`, `--build-arg AGENT=<nombre>`) que arranca `agents/<nombre>/server.py`; eso es lo único que se da por supuesto del destino.
- El servidor HTTP exige `AGENT_API_TOKEN` en cualquier entorno expuesto; no lo publiques sin autenticación.
- `HISTORY_BACKEND=memory` y `sqlite` solo sirven para un único proceso; con varias réplicas usa `postgres`.
- Estado, memoria y almacenamiento se usan a través de una interfaz propia del proyecto, de modo que cambiar de backend no toque la lógica del agente.
- Los secretos se leen del entorno; cómo llegan ahí (gestor de secretos, variables del servicio) es decisión del despliegue, no del código.
- Si una tarea exige elegir proveedor, detente y pregunta.
