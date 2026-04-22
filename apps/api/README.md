# BidForge API (`apps/api`)

FastAPI orchestration layer: **stateless** proposal pipeline, Langfuse tracing, Clerk JWT, Supabase.

## Layout

- `app/pipeline/` — Langfuse trace + sequential agent execution (no business logic in routers).
- `app/modules/` — HTTP routers only.
- Python packages live under repo root `packages/` (`bidforge-schemas`, `bidforge-prompts`, `bidforge-shared`, `bidforge-agents`).

## Run locally

```bash
cp .env.example .env
# Set CLERK_ISSUER, CLERK_SECRET_KEY (production), OPENROUTER_API_KEY, optional LANGFUSE_* and Supabase

uv sync --all-groups
uv run uvicorn app.main:app --reload --port 8000
```

## Endpoints

- `POST /api/proposal/run` — primary contract (also `POST /v1/proposal/run`).
- `GET /api/version` — public contract metadata.
- `GET /health` — liveness.

## Tests

```bash
uv sync --all-groups
uv run pytest tests/ -v
# Live OpenRouter (optional):
OPENROUTER_API_KEY=... uv run pytest tests/ -v -m integration
```
