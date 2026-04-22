from __future__ import annotations

from bidforge_schemas import InputClassifierOutput, RequirementAgentOutput, RequirementRow

from app.pipeline.title_inference import infer_proposal_title


def test_enterprise_prefers_headline_over_long_requirement() -> None:
    rfp = (
        "AI-Powered Public Private Dialogue Platform Development\n\n"
        "The vendor shall deliver SOC 2 compliant hosting and multi-region failover "
        "with documented acceptance tests for every milestone.\n"
    )
    req = RequirementAgentOutput(
        requirement_matrix=[
            RequirementRow(
                id="REQ_1",
                type="deliverable",
                description="The vendor shall deliver SOC 2 compliant hosting and multi-region failover with documented acceptance tests for every milestone.",
                mandatory=True,
                source="RFP",
            ),
        ],
    )
    title = infer_proposal_title(
        rfp,
        pipeline_mode="enterprise",
        job_understanding=None,
        input_classification=InputClassifierOutput(
            input_type="rfp",
            recommended_pipeline="enterprise",
            rationale="",
        ),
        requirements=req,
    )
    assert "AI-Powered" in title or "Dialogue" in title
    assert "SOC 2 compliant hosting" not in title
