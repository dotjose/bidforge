"""Core UX paths: brief upload (normalize) and proposal PDF download (export)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_workspace_document_normalize_text_upload() -> None:
    """POST /api/workspace/document with source=text — no binary file; auth bypassed in test env."""
    client = TestClient(app)
    long_text = (
        "Section: Scope\n\nThe vendor shall deliver widget integration with API tests.\n\n"
        "Section: Schedule\n\nPhase 1 in March; acceptance in April.\n"
    )
    r = client.post(
        "/api/workspace/document",
        data={"source": "text", "text": long_text},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "sections" in data
    assert isinstance(data["sections"], list)
    assert len(data["sections"]) >= 1
    plain = "\n".join(
        (s.get("content") or "") for s in data["sections"] if isinstance(s, dict)
    )
    assert "widget" in plain.lower() or "scope" in plain.lower()


def test_proposal_export_pdf_download() -> None:
    """POST /api/proposal/export/pdf returns application/pdf bytes."""
    client = TestClient(app)
    body = {
        "title": "Integration test export",
        "sections": {
            "executive_summary": "We will deliver the scoped widget with tests.",
            "technical_approach": "- Build\n- Verify\n- Ship",
            "delivery_plan": "Week 1 — build\nWeek 2 — verify",
            "risk_management": "Scope risk mitigated via weekly checkpoints.",
        },
        "timeline": [],
        "pipeline_mode": "enterprise",
        "score": 80,
        "issues": ["missing_requirement: none"],
    }
    r = client.post("/api/proposal/export/pdf", json=body)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    cd = r.headers.get("content-disposition") or ""
    assert "attachment" in cd.lower()
    assert "proposal-export.pdf" in cd
    assert r.content[:4] == b"%PDF"


def test_workspace_document_rejects_pdf_without_file() -> None:
    client = TestClient(app)
    r = client.post("/api/workspace/document", data={"source": "pdf"})
    assert r.status_code == 400
