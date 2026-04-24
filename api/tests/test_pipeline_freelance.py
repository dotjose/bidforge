from __future__ import annotations

from app.pipeline.orchestrator import execute_proposal_pipeline

from tests.conftest import stub_llm_freelance_happy_path


def test_freelance_pipeline_forced_mode() -> None:
    llm = stub_llm_freelance_happy_path()
    result = execute_proposal_pipeline(
        "Upwork job: need FastAPI + OpenAI integration ASAP.",
        "user-freelance-1",
        llm=llm,
        pipeline_mode="freelance",
    )
    assert result["pipeline_mode"] == "freelance"
    prop = result["proposal"]
    assert isinstance(prop, dict)
    assert prop["pipeline_mode"] == "freelance"
    assert str(prop.get("title") or "").strip()
    secs = prop.get("sections")
    assert isinstance(secs, list) and len(secs) >= 7
    titles = [str(s.get("title") or "") for s in secs if isinstance(s, dict)]
    assert "Overview" in titles
    assert "Execution Plan" in titles
    risk = next((s for s in secs if isinstance(s, dict) and s.get("title") == "Risk Management"), None)
    assert risk and str(risk.get("content") or "").strip()
    assert result.get("title")
    assert "bidforge" not in str(result.get("title") or "").lower()
    assert result["job_understanding"]["buyer_intent"]
    assert result.get("proposal_depth") == "full"
    assert result["reply_likelihood_0_100"] is not None
    tl = result.get("timeline")
    assert isinstance(tl, list) and len(tl) >= 1
