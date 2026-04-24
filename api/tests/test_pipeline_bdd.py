"""BDD-style pipeline tests — deterministic stubs by default; optional live OpenAI."""

from __future__ import annotations

import os

import pytest
from bidforge_agents import run_job_intel_extract
from bidforge_shared import OpenRouterLLM, PipelineStepError

from app.pipeline.errors import FailedPipeline
from app.pipeline.orchestrator import execute_proposal_pipeline

from tests.conftest import stub_llm_compliance_fail, stub_llm_happy_path


def test_proposal_pipeline_happy_path(sample_rfp: str) -> None:
    """given a valid RFP when the pipeline runs then score > 70 and proposal exists."""
    llm = stub_llm_happy_path()
    result = execute_proposal_pipeline(sample_rfp, "test-user", llm=llm)
    assert result["score"] > 70
    assert "proposal" in result
    assert "sections" in result["proposal"]
    sp = result["proposal"]["sections"]
    if isinstance(sp, list):
        assert any(str(s.get("content") or "").strip() for s in sp if isinstance(s, dict))
    else:
        assert isinstance(sp, dict)
    assert "timeline" in result and isinstance(result["timeline"], list)
    assert "memory_used" in result and isinstance(result["memory_used"], dict)
    assert result["trace_id"]
    assert result.get("run_id")
    assert isinstance(result.get("insights"), dict)
    assert isinstance(result["issues"], list)
    assert result.get("title")
    assert "bidforge" not in str(result.get("title") or "").lower()
    assert result.get("cross_proposal_diff")


def test_proposal_pipeline_compliance_failure_lowers_score(sample_rfp: str) -> None:
    """given strict compliance when verifier flags gaps then score < 70."""
    llm = stub_llm_compliance_fail()
    result = execute_proposal_pipeline(sample_rfp, "test-user", llm=llm)
    assert result["score"] < 70
    assert any("compliance_risk:" in i for i in result["issues"])


def test_broken_rfp_empty_after_strip_raises() -> None:
    """given whitespace-only input when requirement runs then pipeline fails fast."""
    llm = stub_llm_happy_path()
    with pytest.raises(FailedPipeline) as exc:
        execute_proposal_pipeline("   \n\t  ", "test-user", llm=llm)
    assert exc.value.failed_step == "job_intel__extract"


def test_job_intel_extract_rejects_empty() -> None:
    with pytest.raises(PipelineStepError):
        run_job_intel_extract("", stub_llm_happy_path())


@pytest.mark.integration
def test_live_openrouter_pipeline_when_configured(sample_rfp: str) -> None:
    """given OPENROUTER_API_KEY when pipeline runs then real model returns structured JSON."""
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    primary = os.getenv("OPENROUTER_MODEL_PRIMARY", "anthropic/claude-3.5-sonnet")
    fallback = os.getenv("OPENROUTER_MODEL_FALLBACK", "openai/gpt-4o-mini")
    llm = OpenRouterLLM(api_key=key, primary_model=primary, fallback_model=fallback)
    result = execute_proposal_pipeline(sample_rfp, "integration-user", llm=llm)
    assert result["score"] >= 0
    sp = result["proposal"]["sections"]
    if isinstance(sp, list):
        assert any(str(s.get("content") or "").strip() for s in sp if isinstance(s, dict))
    else:
        assert sp.get("executive_summary") or sp.get("opening")
