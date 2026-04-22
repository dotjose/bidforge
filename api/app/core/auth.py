from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import settings

security = HTTPBearer(auto_error=False)

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not settings.clerk_issuer:
            raise RuntimeError("CLERK_ISSUER is not configured")
        jwks_url = settings.clerk_issuer.rstrip("/") + "/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url,
            cache_keys=True,
            max_cached_keys=16,
            cache_jwk_set=True,
            lifespan=3600,
        )
    return _jwks_client


class CurrentUser:
    def __init__(self, user_id: str, email: str | None) -> None:
        self.user_id = user_id
        self.email = email


def verify_clerk_bearer_token(authorization_header: str) -> CurrentUser:
    """Validate `Authorization: Bearer <jwt>` and return the Clerk subject (`sub`)."""
    parts = authorization_header.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise ValueError("missing bearer")
    token = parts[1].strip()
    if not token:
        raise ValueError("empty token")
    if not settings.clerk_issuer:
        raise ValueError("issuer not configured")

    try:
        jwks = _get_jwks_client()
        signing_key = jwks.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer.rstrip("/"),
            options={"require": ["exp", "sub"]},
            leeway=60,
        )
    except Exception as e:
        raise ValueError("invalid jwt") from e

    user_id = str(payload.get("sub", ""))
    email = payload.get("email")
    if isinstance(email, list):
        email = email[0] if email else None
    if not user_id:
        raise ValueError("missing sub")

    return CurrentUser(user_id=user_id, email=str(email) if email else None)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> CurrentUser:
    """Identity from Clerk JWT — prefer `request.state` from middleware; never from request body."""
    if settings.skip_auth:
        return CurrentUser(user_id="dev_user", email="dev@example.com")

    cu = getattr(request.state, "clerk_user", None)
    if isinstance(cu, CurrentUser):
        return cu

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        return verify_clerk_bearer_token(f"{credentials.scheme} {credentials.credentials}")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
