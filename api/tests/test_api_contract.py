from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_api_version_contract() -> None:
    client = TestClient(app)
    r = client.get("/api/version")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "1.0.0"
    assert data["pipeline"] == "5-node-dag-v1"
    assert "rfp_max_chars" in data
    assert "supabase_env_loaded" in data
    assert "langfuse_credentials_loaded" in data
    assert "langfuse_tracing_enabled" in data
    assert "supabase_project_ref" in data
    assert "supabase_proposals_readable" in data


def test_openapi_includes_proposal_and_error_schemas() -> None:
    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "/api/proposal/run" in spec["paths"]
    assert "/api/proposals" in spec["paths"]
    assert "/api/settings" in spec["paths"]
    assert "/api/proposal/pattern" in spec["paths"]
    post = spec["paths"]["/api/proposal/run"]["post"]
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert "HTTPBearer" in schemes
    sec = post.get("security") or []
    assert any(isinstance(s, dict) and "HTTPBearer" in s for s in sec)
