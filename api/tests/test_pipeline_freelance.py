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
    assert result["proposal"]["pipeline_mode"] == "freelance"
    assert result["proposal"]["freelance"]["hook"]
    assert result["proposal"]["freelance"]["understanding_need"]
    assert result.get("title")
    assert "bidforge" not in str(result.get("title") or "").lower()
    assert result["hook"] and result["hook"]["hook"]
    assert result["job_understanding"]["buyer_intent"]
    assert result["critique"]["improvements"]
    assert result["reply_likelihood_0_100"] is not None
    assert result["timeline"] == []
