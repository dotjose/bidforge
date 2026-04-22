"""Derive a customer-visible proposal title from RFP / job text or structured understanding — never product placeholders."""

from __future__ import annotations

import re

from bidforge_schemas import InputClassifierOutput, JobUnderstandingOutput, RequirementAgentOutput

_FORBIDDEN = frozenset(
    {
        "",
        "bidforge proposal",
        "proposal",
        "proposal output",
        "untitled",
        "new proposal",
    }
)


def _clean_line(s: str) -> str:
    t = re.sub(r"^[\s#>*-]+", "", s).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:200].strip()


def _shorten_opportunity_title(head: str, *, max_len: int = 96) -> str:
    """Compress long marketplace headlines into a readable title (no full sentence echo)."""
    h = head.strip()
    if len(h) <= max_len:
        return h
    low = h.lower()
    for sep in (" needed for ", " needed to ", " for a ", " for an ", " for "):
        idx = low.find(sep)
        if idx > 12:
            left = h[:idx].strip()
            right = h[idx + len(sep) :].strip()
            if len(left) >= 10 and len(right) >= 8:
                tail = right.split(".")[0].split("—")[0].strip()
                tail = re.sub(r"\s+", " ", tail)[:56].strip()
                cand = f"{left[:48].strip()} – {tail}".strip()
                if len(cand) <= max_len + 8:
                    return cand[:max_len]
    # Word-boundary trim
    cut = h[: max_len - 1]
    sp = cut.rfind(" ")
    if sp > 40:
        cut = cut[:sp]
    return (cut + "…").strip()


def _first_meaningful_lines(text: str, *, max_lines: int = 12) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        ln = _clean_line(raw)
        if len(ln) < 4:
            continue
        low = ln.lower()
        if low.startswith("posted ") or low.startswith("budget ") or low.startswith("hourly "):
            continue
        lines.append(ln)
        if len(lines) >= max_lines:
            break
    return lines


def _looks_like_compliance_clause(text: str) -> bool:
    low = text.lower()
    if " shall " in low or " must " in low or "comply with" in low or " in accordance with" in low:
        return True
    if "vendor" in low and ("submit" in low or "provide" in low):
        return True
    if low.startswith("section ") and ":" in text[:32]:
        return True
    return False


def _title_from_rfp_opportunity(lines: list[str]) -> str | None:
    """Prefer short headline-like lines (project name) over long requirement sentences."""
    for ln in lines[:14]:
        t = ln.strip()
        if len(t) < 10 or len(t) > 130:
            continue
        if _looks_like_compliance_clause(t):
            continue
        if t.count(".") > 1 or t.count(";") > 1:
            continue
        if t.count(",") > 3:
            continue
        return t[:160]
    return None


def _from_job_understanding(ju: JobUnderstandingOutput | None) -> str | None:
    if ju is None:
        return None
    intent = (ju.buyer_intent or "").strip()
    if len(intent) > 20 and len(intent) < 160 and not _looks_like_compliance_clause(intent):
        return intent[:160]
    if ju.explicit_requirements:
        cand = _clean_line(ju.explicit_requirements[0])
        if 12 < len(cand) < 120 and not _looks_like_compliance_clause(cand):
            return cand[:160]
    return None


def _from_requirements(req: RequirementAgentOutput | None) -> str | None:
    if req is None:
        return None
    candidates: list[str] = []
    for row in req.requirement_matrix:
        desc = (row.description or "").strip()
        if not desc or len(desc) > 100:
            continue
        if _looks_like_compliance_clause(desc):
            continue
        if row.type == "deliverable" and len(desc) >= 15:
            candidates.append(desc)
    if candidates:
        return candidates[0][:100]
    for s in req.structured_requirements[:5]:
        t = (s.text or "").strip()
        if 15 < len(t) < 100 and not _looks_like_compliance_clause(t):
            return t[:160]
    return None


def infer_proposal_title(
    rfp_text: str,
    *,
    pipeline_mode: str,
    job_understanding: JobUnderstandingOutput | None = None,
    input_classification: InputClassifierOutput | None = None,
    requirements: RequirementAgentOutput | None = None,
) -> str:
    """Return a job-specific title; callers should persist this as the canonical run title."""
    rfp = (rfp_text or "").strip()
    lines = _first_meaningful_lines(rfp)

    # Enterprise / formal: headline from early RFP lines beats first long requirement row
    if pipeline_mode == "enterprise" or (input_classification and input_classification.input_type == "rfp"):
        opp = _title_from_rfp_opportunity(lines)
        if opp and opp.lower() not in _FORBIDDEN:
            return _shorten_opportunity_title(opp, max_len=100)

    # Upwork / short job post: first line is often the headline
    if lines:
        head = lines[0]
        if pipeline_mode == "freelance" or (
            input_classification and input_classification.input_type in ("job_post", "upwork", "freelancer")
        ):
            if len(head) >= 10:
                cand = _shorten_opportunity_title(head, max_len=100) if len(head) > 100 else head[:160]
                if cand.lower() not in _FORBIDDEN:
                    return cand

    ju_title = _from_job_understanding(job_understanding)
    if ju_title and ju_title.lower() not in _FORBIDDEN:
        return ju_title

    req_title = _from_requirements(requirements)
    if req_title and req_title.lower() not in _FORBIDDEN:
        return _shorten_opportunity_title(req_title, max_len=100)

    if lines:
        snippet = lines[0][:140].strip()
        if snippet.lower() not in _FORBIDDEN:
            return _shorten_opportunity_title(snippet, max_len=100)

    return "Untitled proposal"
