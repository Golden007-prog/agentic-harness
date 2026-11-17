---
name: instrument-langfuse
description: Añade o corrige la observabilidad de un agente con Langfuse (trazas, sesiones, metadatos, flush) y comprueba que las trazas llegan. Usar cuando el usuario pida trazas, observabilidad, monitorizar, depurar ejecuciones o conectar Langfuse a un agente.
argument-hint: <agente>
---
# Instrumentar un agente con Langfuse

Agente: $ARGUMENTS

1. Consulta `langfuse-docs` (`searchLangfuseDocs`, `getLangfuseDocsPage`) para la integración vigente con LangChain/LangGraph: paquete, imports, variables de entorno y cómo se pasan sesión, usuario y metadatos. No lo escribas de memoria.
2. Lee el agente. Si se creó con el esqueleto, la integración ya está en `observability.py` (handler, `propagate_attributes`, enmascarado y flush) y se usa en `AgentRunner._run`: compárala con la documentación y corrige lo que haya cambiado. Si no, localiza el único punto donde se invoca el agente: ahí se conecta la traza.
3. Implementa:
   - Cliente o handler de Langfuse creado una vez y reutilizado.
   - En cada ejecución: nombre del agente, entorno, versión o commit, e identificador de sesión si hay conversación.
   - Flush al terminar en scripts, jobs y funciones de vida corta.
   - Sin secretos ni datos personales sin enmascarar en entradas y salidas trazadas.
4. Añade a `.env.example` las variables que indique la documentación.
5. Comprueba: ejecuta el agente una vez y confirma que no hay errores de Langfuse en la salida. Pide al usuario que confirme que la traza aparece en su proyecto de Langfuse; tú no tienes acceso a la interfaz.
6. Informa qué quedó trazado y qué no pudiste comprobar.
