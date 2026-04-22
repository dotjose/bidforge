from __future__ import annotations

import pytest
from bidforge_agents.requirement_agent import run_requirement_agent
from bidforge_schemas import (
    FormatterAgentOutput,
    InputClassifierOutput,
    ProposalAgentOutput,
    ProposalCritiqueOutput,
    ProposalSection,
    RequirementAgentOutput,
    RequirementRow,
    RequirementStructuringOutput,
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
        "input_classifier",
        InputClassifierOutput(
            input_type="rfp",
            recommended_pipeline="enterprise",
            rationale="edge stub",
        ),
    )
    llm.register(
        "requirement_agent",
        RequirementAgentOutput(
            requirements=["Deliver widget"],
            constraints=[],
            risks=[],
            compliance_items=["FedRAMP High"],
        ),
    )
    llm.register(
        "requirement_structuring",
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
        "strategy_agent",
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
        "proposal_agent",
        ProposalAgentOutput(
            sections=[
                ProposalSection(
                    title="Executive summary",
                    content="We ship fast.",
                    covers_requirements=["REQ_1"],
                    based_on_memory=[],
                ),
                ProposalSection(title="Technical approach", content="", covers_requirements=[], based_on_memory=[]),
                ProposalSection(title="Delivery plan", content="", covers_requirements=[], based_on_memory=[]),
                ProposalSection(title="Risk management", content="", covers_requirements=[], based_on_memory=[]),
            ],
        ),
    )
    llm.register(
        "formatter_agent",
        FormatterAgentOutput(
            executive_summary="We ship fast.",
            technical_approach="",
            delivery_plan="",
            risk_management="",
            format_notes=[],
        ),
    )
    llm.register(
        "verifier_agent",
        VerifierAgentOutput(
            score=28,
            issues=["Thin technical detail"],
            missing_requirements=["Deliver widget"],
            compliance_risks=["FedRAMP High not evidenced"],
            weak_claims=[],
        ),
    )
    llm.register(
        "critique_agent",
        ProposalCritiqueOutput(
            improvements=[],
            reply_probability_delta="",
            enterprise_gap_summary="",
            top1_style_rewrite="",
        ),
    )
    result = execute_proposal_pipeline("RFP: need widget.", "u3", llm=llm)
    assert result["score"] < 40
    assert any("compliance_risk:" in i for i in result["issues"])


def test_pricing_mismatch_surfaces_as_issue_or_compliance() -> None:
    llm = stub_llm_happy_path()
    llm.register(
        "verifier_agent",
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


def test_strategy_step_missing_stub_raises_failed_pipeline() -> None:
    llm = StubLLM()
    llm.register(
        "input_classifier",
        InputClassifierOutput(
            input_type="rfp",
            recommended_pipeline="enterprise",
            rationale="edge stub",
        ),
    )
    llm.register("requirement_agent", RequirementAgentOutput())
    llm.register("requirement_structuring", RequirementStructuringOutput())
    with pytest.raises(FailedPipeline) as exc:
        execute_proposal_pipeline("Some RFP text here.", "u5", llm=llm)
    assert exc.value.failed_step == "strategy_agent"


def test_requirement_raises_pipeline_step_error() -> None:
    with pytest.raises(PipelineStepError):
        run_requirement_agent("", stub_llm_happy_path())
