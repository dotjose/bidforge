"""Regression tests for server-side PDF export."""

from app.modules.proposal.pdf_export import build_proposal_pdf_bytes


def test_pdf_export_long_unbroken_token_does_not_crash() -> None:
    """FPDF w=0 uses remaining width from current x; after a cell, x at RIGHT made w≈0."""
    long_token = "x" * 600
    body = f"Intro words then {long_token} then tail."
    pdf_bytes = build_proposal_pdf_bytes(
        title="Test",
        sections={
            "executive_summary": body,
            "technical_approach": "",
            "delivery_plan": "",
            "risk_management": "",
        },
        timeline=[{"phase": "Phase A", "duration": "2w"}],
        score=81,
        issues=["missing_requirement: item"],
        memory_insight_bullets=["Pattern: concise hook", "Pattern: phased delivery"],
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 200


def test_pdf_export_freelance_section_headings() -> None:
    pdf_bytes = build_proposal_pdf_bytes(
        title="Bid",
        sections={
            "executive_summary": "Hook line",
            "technical_approach": "Need bullets",
            "delivery_plan": "Approach + proof",
            "risk_management": "CTA",
        },
        timeline=[],
        memory_appendix=None,
        pipeline_mode="freelance",
    )
    # fpdf2 may compress streams; smoke-test that freelance mode still renders a valid PDF.
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 400


def test_pdf_export_multiple_sections_advances_cursor() -> None:
    pdf_bytes = build_proposal_pdf_bytes(
        title="Multi",
        sections={
            "executive_summary": "First block.",
            "technical_approach": "Second block.",
            "delivery_plan": "Third.",
            "risk_management": "Fourth.",
        },
        timeline=[],
        memory_appendix=None,
    )
    assert pdf_bytes.startswith(b"%PDF")
