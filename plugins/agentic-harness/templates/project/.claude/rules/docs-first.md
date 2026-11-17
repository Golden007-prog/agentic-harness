# Documentación primero

Las APIs de LangChain, LangGraph y Langfuse cambian con frecuencia. Lo que recuerdas de ellas puede estar obsoleto.

Antes de escribir o modificar código que use estas librerías, consulta el MCP correspondiente y básate en lo que devuelva:

| Necesitas | Servidor MCP | Herramientas |
|---|---|---|
| Guías, conceptos, tutoriales, patrones de LangChain / LangGraph / LangSmith | `docs-langchain` | `search_docs_by_lang_chain`, `query_docs_filesystem_docs_by_lang_chain` |
| Firma exacta de una clase, función o parámetro | `reference-langchain` | `search_api`, `get_symbol` |
| Trazas, prompts, evaluaciones, SDK e integraciones de Langfuse | `langfuse-docs` | `searchLangfuseDocs`, `getLangfuseDocsPage`, `getLangfuseOverview` |

- Usa primero `docs-langchain` para elegir el enfoque y después `reference-langchain` para confirmar imports y firmas.
- Si la documentación contradice el código existente del proyecto, dilo antes de cambiar nada.
- Si un MCP no responde, avisa al usuario y marca en tu respuesta qué partes del código no pudiste verificar.
- Para búsquedas largas delega en el subagente `agentic-harness:langchain-researcher`, que devuelve solo la conclusión con sus fuentes.
