"""Normalize proposal run payloads for SaaS API (run id, insights, execution status)."""

from __future__ import annotations

from typing import Any


def build_insights(
    *,
    warnings: list[str] | None = None,
    missing_context: bool = False,
    rag_fallback_mode: bool = False,
    degraded: bool = False,
) -> dict[str, Any]:
    return {
        "warnings": list(warnings or []),
        "missing_context": missing_context,
        "rag_fallback_mode": rag_fallback_mode,
        "degraded": degraded,
    }


def attach_run_envelope(
    payload: dict[str, Any],
    *,
    execution_status: str,
    insights: dict[str, Any],
) -> dict[str, Any]:
    """Mutates and returns payload with run_id, execution_status, insights (idempotent)."""
    tid = str(payload.get("trace_id") or "")
    out = dict(payload)
    out["run_id"] = tid
    out["trace_id"] = tid
    out["execution_status"] = execution_status
    out["insights"] = insights
    return out


def minimal_degraded_proposal(*, headline: str, body: str) -> dict[str, Any]:
    return {
        "sections": {
            "executive_summary": headline,
            "technical_approach": body,
            "delivery_plan": "",
            "risk_management": "",
        },
        "format_notes": [],
        "strategy": {
            "strategy": "",
            "based_on": [],
            "positioning": "",
            "win_themes": [],
            "differentiators": [],
            "response_tone": "",
            "freelance_hook_strategy": "",
        },
        "memory_summary": {
            "similar_proposals": [],
            "win_patterns": [],
            "methodology_blocks": [],
            "freelance_win_patterns": [],
        },
        "memory_grounded": False,
        "grounding_warning": None,
        "section_attributions": [],
        "pipeline_mode": "enterprise",
    }
