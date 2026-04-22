"""Deterministic timeline extraction — no LLM."""

from __future__ import annotations

import re

from bidforge_schemas import RequirementAgentOutput, TimelineAgentOutput, TimelinePhase


def _norm_key(phase: str, duration: str) -> tuple[str, str]:
    return (re.sub(r"\s+", " ", phase.strip().lower()), re.sub(r"\s+", " ", duration.strip().lower()))


def run_timeline_agent(rfp_text: str, requirements: RequirementAgentOutput) -> TimelineAgentOutput:
    phases: list[TimelinePhase] = []
    seen: set[tuple[str, str]] = set()

    def add(phase: str, duration: str = "") -> None:
        p = phase.strip()
        if not p:
            return
        p = p[:220]
        d = (duration or "").strip()[:120]
        key = _norm_key(p, d)
        if key in seen:
            return
        seen.add(key)
        phases.append(TimelinePhase(phase=p, duration=d))

    for row in requirements.requirement_matrix:
        if row.type == "timeline" and row.description.strip():
            add(row.description.strip()[:200], "")

    for row in requirements.requirement_matrix:
        if row.type == "deliverable" and any(
            k in row.description.lower() for k in ("milestone", "phase", "week", "month", "deadline", "due")
        ):
            if len(phases) < 20:
                add(row.description.strip()[:180], "")

    text = rfp_text or ""
    for m in re.finditer(
        r"\b(\d{1,3})\s*(?:business\s+)?(day|days|week|weeks|month|months)\b",
        text,
        re.IGNORECASE,
    ):
        window = m.group(0)
        add(f"Milestone window noted in the opportunity brief: {window}", "")
        if len(phases) >= 20:
            break

    for c in requirements.constraints:
        cl = c.lower()
        if any(k in cl for k in ("due", "deadline", "noon", "pm", "am", "week of", "by ")):
            add(f"Schedule constraint: {c.strip()[:160]}", "")
            if len(phases) >= 20:
                break

    if not phases:
        phases = [
            TimelinePhase(
                phase="Mobilization, discovery, and blueprint sign-off with stakeholders",
                duration="",
            ),
            TimelinePhase(
                phase="Iterative build, integration, and test against agreed acceptance criteria",
                duration="",
            ),
            TimelinePhase(
                phase="Pilot, hardening, training, acceptance, and operational handover",
                duration="",
            ),
        ]

    return TimelineAgentOutput(timeline=phases[:16])
