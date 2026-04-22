# bidforge-prompts

Versioned system/user prompt pairs for each agent. **Python is the source of truth** (OpenAI calls run from the `api/` FastAPI app).

TypeScript mirrors are not duplicated here to avoid drift; import versions via API metadata if the web app needs them.
