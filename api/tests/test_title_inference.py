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


def test_skips_capability_filler_for_headline_picks_next_line() -> None:
    rfp = (
        "Comprehensive plan to manage and optimize e-commerce operations.\n\n"
        "Acme Marketplace Seller Ops — Q2 vendor onboarding\n"
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
        requirements=None,
    )
    assert "Acme" in title
    assert "comprehensive" not in title.lower()


def test_proposal_executive_summary_when_rfp_line_is_only_filler() -> None:
    rfp = "Well-equipped to enhance listing performance across all major marketplaces."
    prop = {
        "sections": {
            "executive_summary": (
                "Acme will consolidate seller workflows in 10 weeks, "
                "cutting support tickets by 35% while preserving SLAs."
            ),
        },
    }
    title = infer_proposal_title(
        rfp,
        pipeline_mode="enterprise",
        proposal_payload=prop,
    )
    assert "acme" in title.lower()
    assert "well-equipped" not in title.lower()


def test_source_document_title_from_upload_filename() -> None:
    body = "We deliver excellence. " * 15
    title = infer_proposal_title(
        body,
        pipeline_mode="enterprise",
        source_document_title="Acme_Marketplace_2026.pdf",
    )
    assert "acme" in title.lower() or "marketplace" in title.lower()
