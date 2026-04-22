from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_api_version_contract() -> None:
    client = TestClient(app)
    r = client.get("/api/version")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "1.0.0"
    assert data["pipeline"] == "deterministic-v1"
    assert "rfp_max_chars" in data


def test_openapi_includes_proposal_and_error_schemas() -> None:
    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "/api/proposal/run" in spec["paths"]
    post = spec["paths"]["/api/proposal/run"]["post"]
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert "HTTPBearer" in schemes
    sec = post.get("security") or []
    assert any(isinstance(s, dict) and "HTTPBearer" in s for s in sec)
