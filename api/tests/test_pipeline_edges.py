from __future__ import annotations

import pytest
from bidforge_agents import run_job_intel_extract
from bidforge_schemas import (
    InputClassifierOutput,
    ProposalWriterOutput,
    ProposalWriterSection,
    RequirementAgentOutput,
    RequirementRow,
    RequirementStructuringOutput,
    SolutionBlueprintOutput,
    StrategyAgentOutput,
    VerifierAgentOutput,
)
from bidforge_shared import PipelineStepError, StubLLM

from app.pipeline.errors import FailedPipeline
from app.pipeline.orchestrator import execute_proposal_pipeline

from tests.conftest import stub_llm_happy_path


def test_malformed_rfp_still_runs_with_stub(sample_rfp: str) -> None:
    """Very short / odd unicode should not crash the stubbed pipeline."""
    llm = stub_llm_happy_path()
    weird = "@@@\n\u0000" + sample_rfp
    result = execute_proposal_pipeline(weird, "user-1", llm=llm, rfp_id="rfp-malformed")
    assert result["trace_id"]
    assert "proposal" in result


def test_large_rfp_padding_accepted(sample_rfp: str) -> None:
    llm = stub_llm_happy_path()
    big = sample_rfp + ("x" * 15_000)
    result = execute_proposal_pipeline(big, "user-1", llm=llm)
    assert result["score"] >= 0


def test_explicit_rfp_id_in_metadata_stable(sample_rfp: str) -> None:
    llm = stub_llm_happy_path()
    result = execute_proposal_pipeline(sample_rfp, "user-2", rfp_id="RFP-UNIT-001", llm=llm)
    assert result["proposal"]


def test_missing_compliance_sections_verifier_scores_low() -> None:
    llm = StubLLM()
    llm.register(
        "router",
        InputClassifierOutput(
            input_type="rfp",
            recommended_pipeline="enterprise",
            rationale="edge stub",
        ),
    )
    llm.register(
        "job_intel__extract",
        RequirementAgentOutput(
            requirements=["Deliver widget"],
            constraints=[],
            risks=[],
            compliance_items=["FedRAMP High"],
        ),
    )
    llm.register(
        "job_intel__matrix",
        RequirementStructuringOutput(
            requirements=[
                RequirementRow(
                    id="REQ_1",
                    type="deliverable",
                    description="Deliver widget",
                    mandatory=True,
                    source="Scope of Work",
                ),
            ],
        ),
    )
    llm.register(
        "solution__blueprint",
        SolutionBlueprintOutput(
            tasks=["Map widget scope", "Ship MVP", "Document acceptance", "Train handoff"],
            timeline=["Week 1 — discovery", "Week 2 — build", "Week 3 — release"],
            deliverables=["Widget build", "Test pack", "Runbook"],
        ),
    )
    llm.register(
        "solution__strategy",
        StrategyAgentOutput(
            strategy="x",
            based_on=[],
            positioning="x",
            win_themes=[],
            differentiators=[],
            response_tone="neutral",
            freelance_hook_strategy="",
        ),
    )
    llm.register(
        "proposal",
        ProposalWriterOutput(
            title="Widget delivery with Postgres-backed API tests",
            sections=[
                ProposalWriterSection(title="Overview", content="We ship fast with Postgres migrations and a clear MVP path."),
                ProposalWriterSection(title="Solution", content="Widget scope mapped to API tests and OpenAPI contract."),
                ProposalWriterSection(
                    title="Execution Plan",
                    content=(
                        "- Map widget scope into Postgres schema migrations\n"
                        "- Ship MVP with FastAPI routes covered by pytest\n"
                        "- Document acceptance criteria in git with CI/CD on each merge\n"
                        "- Train handoff using runbook in Jira"
                    ),
                ),
                ProposalWriterSection(title="Timeline", content="Week 1 — discovery\nWeek 2 — build\nWeek 3 — release"),
                ProposalWriterSection(
                    title="Deliverables",
                    content="Binary artifact, pytest pack, docs pack for operators with rollback notes.",
                ),
                ProposalWriterSection(title="Risk Management", content="Weekly scope gates with Slack updates."),
                ProposalWriterSection(title="Next Steps", content="Pick a slot this week."),
            ],
        ),
    )
    llm.register(
        "verifier",
        VerifierAgentOutput(
            score=28,
            issues=["Thin technical detail"],
            missing_requirements=["Deliver widget"],
            compliance_risks=["FedRAMP High not evidenced"],
            weak_claims=[],
        ),
    )
    result = execute_proposal_pipeline("RFP: need widget.", "u3", llm=llm)
    assert result["score"] < 40
    assert any("compliance_risk:" in i for i in result["issues"])


def test_pricing_mismatch_surfaces_as_issue_or_compliance() -> None:
    llm = stub_llm_happy_path()
    llm.register(
        "verifier",
        VerifierAgentOutput(
            score=45,
            issues=["Pricing table contradicts narrative totals"],
            missing_requirements=[],
            compliance_risks=["Commercial terms ambiguity"],
            weak_claims=[],
        ),
    )
    result = execute_proposal_pipeline("RFP: fixed price $1M cap.", "u4", llm=llm)
    assert any("Pricing" in i or "Commercial" in i for i in result["issues"])


def test_solution_blueprint_step_missing_stub_raises_failed_pipeline() -> None:
    llm = StubLLM()
    llm.register(
        "router",
        InputClassifierOutput(
            input_type="rfp",
            recommended_pipeline="enterprise",
            rationale="edge stub",
        ),
    )
    llm.register("job_intel__extract", RequirementAgentOutput())
    llm.register("job_intel__matrix", RequirementStructuringOutput())
    with pytest.raises(FailedPipeline) as exc:
        execute_proposal_pipeline("Some RFP text here.", "u5", llm=llm)
    assert exc.value.failed_step == "solution__blueprint"


def test_job_intel_extract_raises_pipeline_step_error() -> None:
    with pytest.raises(PipelineStepError):
        run_job_intel_extract("", stub_llm_happy_path())
