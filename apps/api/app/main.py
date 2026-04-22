from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings, validate_production_settings
from app.core.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.middleware.clerk_auth import ClerkAuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.modules.documents.router import router as documents_router
from app.modules.memory.router import router as memory_router
from app.modules.meta.router import router as meta_router
from app.modules.profile.router import router as profile_router
from app.modules.proposal.router import router as proposal_router
from app.modules.workspace.router import router as workspace_router
from app.openapi import attach_custom_openapi


def _cors_origins() -> list[str]:
    base = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    extra = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
    return base + extra


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_settings()
    configure_logging()
    yield


_docs_enabled = settings.env != "production"

app = FastAPI(
    title="BidForge API",
    description=(
        "Proposal intelligence HTTP layer — deterministic multi-agent pipeline, "
        "Langfuse tracing, Clerk JWT auth, Supabase-backed RAG. "
        "Interactive **Swagger** and **ReDoc** are enabled outside `ENV=production`."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(ClerkAuthMiddleware)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

attach_custom_openapi(app)

app.include_router(meta_router, prefix="/api")
app.include_router(proposal_router, prefix="/v1/proposal")
app.include_router(proposal_router, prefix="/api/proposal")
app.include_router(profile_router, prefix="/v1")
app.include_router(documents_router, prefix="/v1")
app.include_router(documents_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(workspace_router, prefix="/api/workspace")


@app.get(
    "/health",
    tags=["health"],
    openapi_extra={"security": []},
    summary="Health check",
)
async def health() -> dict:
    return {
        "status": "ok",
        "skip_auth": settings.skip_auth,
        "env": settings.env,
        "langfuse": bool(settings.langfuse_public_key and settings.langfuse_secret_key),
        "langfuse_environment": settings.langfuse_tracing_environment,
        "openrouter": bool(settings.openrouter_api_key),
    }
