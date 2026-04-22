"""Strip internal verifier / QA artifacts that must never ship in customer-facing proposal text."""

from __future__ import annotations

import re

from bidforge_schemas import FormatterAgentOutput

_PREFIXES = (
    "compliance_risk:",
    "missing_requirement:",
    "weak_claim:",
    "missing_memory_usage:",
    "generic_language:",
    "deviation_from_win_patterns:",
    "freelance_fail:",
)

_LINE_START_BANNED = re.compile(
    r"^\s*(verifier\s+score|review\s+summary|issues?)\s*:",
    re.I | re.M,
)


def _scrub_block(text: str) -> str:
    out: list[str] = []
    for line in (text or "").splitlines():
        raw = line.strip()
        low = raw.lower()
        if not raw:
            out.append(line)
            continue
        if _LINE_START_BANNED.match(line):
            continue
        if any(low.startswith(p) for p in _PREFIXES):
            continue
        if "verifier score" in low and len(raw) < 120:
            continue
        if "review summary" in low and len(raw) < 200:
            continue
        out.append(line)
    t = "\n".join(out).strip()
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def sanitize_formatter_output(fmt: FormatterAgentOutput) -> FormatterAgentOutput:
    """Defense-in-depth after LLM format; keeps schema, drops editorial / QA leakage."""
    return FormatterAgentOutput(
        executive_summary=_scrub_block(fmt.executive_summary),
        technical_approach=_scrub_block(fmt.technical_approach),
        delivery_plan=_scrub_block(fmt.delivery_plan),
        risk_management=_scrub_block(fmt.risk_management),
        format_notes=[],
    )
