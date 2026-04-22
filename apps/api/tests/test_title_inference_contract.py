"""Contract tests for customer-visible proposal titles (no branding, no raw echo)."""

from app.pipeline.title_inference import infer_proposal_title


def test_react_fastapi_job_title_is_compressed_not_raw_echo() -> None:
    rfp = "React + FastAPI Developer Needed for SaaS Dashboard with Auth and AI features"
    t = infer_proposal_title(rfp, pipeline_mode="freelance")
    assert "bidforge" not in t.lower()
    assert "react" in t.lower()
    assert len(t) >= 8


def test_empty_brief_falls_back_to_untitled() -> None:
    assert infer_proposal_title("", pipeline_mode="enterprise") == "Untitled proposal"
