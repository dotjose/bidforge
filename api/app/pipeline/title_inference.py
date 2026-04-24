"""Derive a customer-visible proposal title from RFP / job text or structured understanding — never product placeholders."""

from __future__ import annotations

import re
from typing import Any

from bidforge_schemas import InputClassifierOutput, JobUnderstandingOutput, RequirementAgentOutput  # pyright: ignore[reportMissingImports]

_TITLE_BAD_TOKENS = re.compile(
    r"\b(rfp|summary|response|posted|hourly|fixed\s*price|job\s*post)\b",
    re.IGNORECASE,
)

_FORBIDDEN = frozenset(
    {
        "",
        "bidforge proposal",
        "proposal",
        "proposal output",
        "untitled",
        "untitled proposal",
        "new proposal",
        "rfp response",
        "rfp response:",
        "strong experience",
        "opportunity",
    }
)


def _clean_line(s: str) -> str:
    t = re.sub(r"^[\s#>*-]+", "", s).strip()
    t = re.sub(r"\s+", " ", t)
    low = t.lower()
    for prefix in (
        "rfp response:",
        "rfp response",
        "bidforge proposal:",
        "bidforge proposal",
        "proposal:",
    ):
        if low.startswith(prefix):
            t = t[len(prefix) :].lstrip(" :—-\t")
            low = t.lower()
            break
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


def _looks_like_capability_filler(text: str) -> bool:
    """Marketing / capability blurbs (often mirror weak_claims) — poor as document titles."""
    low = (text or "").lower().strip()
    if len(low) < 16:
        return False
    starters = (
        "comprehensive ",
        "we are ",
        "we deliver ",
        "our team ",
        "our company ",
        "proven track",
        "well-equipped",
        "well equipped",
        "deep expertise",
        "end-to-end ",
        "full-service ",
        "trusted partner",
        "tailored solution",
    )
    if any(low.startswith(s) for s in starters):
        return True
    if "well-equipped" in low or "well equipped" in low:
        return True
    return False


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
        if _looks_like_capability_filler(t):
            continue
        # Long single-sentence blurbs read as body copy, not a headline
        if t.endswith(".") and len(t) > 72:
            continue
        if t.count(".") > 1 or t.count(";") > 1:
            continue
        if t.count(",") > 3:
            continue
        return t[:160]
    return None


def _clean_source_document_title(raw: str | None) -> str | None:
    """Filename or normalizer title from PDF/DOCX upload — humanize for display."""
    if not raw or not str(raw).strip():
        return None
    t = str(raw).strip()
    t = re.sub(r"\.[a-z0-9]{2,5}$", "", t, flags=re.IGNORECASE).strip()
    t = re.sub(r"[_\-]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) < 3 or len(t) > 220:
        return None
    low = t.lower()
    if low in ("opportunity", "document", "untitled", "proposal", "rfp"):
        return None
    return t


def _title_from_proposal_excerpt(proposal: dict[str, Any] | None) -> str | None:
    """First substantive line from executive summary when RFP-derived title is weak."""
    if not isinstance(proposal, dict):
        return None
    doc_title = str(proposal.get("title") or "").strip()
    if len(doc_title) >= 8 and not _looks_like_capability_filler(doc_title):
        low = doc_title.lower()
        if low not in _FORBIDDEN and not _title_contains_rejected_tokens(doc_title):
            cap = _cap_title_words(doc_title, 12)
            if cap:
                return cap
    secs_list = proposal.get("sections")
    if isinstance(secs_list, list):
        for item in secs_list:
            if not isinstance(item, dict):
                continue
            if str(item.get("title") or "").strip().lower() != "overview":
                continue
            ex = str(item.get("content") or "").strip()
            if len(ex) < 24:
                return None
            ex = re.sub(r"\*\*([^*]+)\*\*", r"\1", ex)
            ex = re.sub(r"^#+\s*", "", ex, flags=re.MULTILINE)
            block = ex.split("\n\n")[0].split("\n")[0].strip()
            if len(block) < 24:
                return None
            if _looks_like_capability_filler(block):
                return None
            one = re.split(r"(?<=[.!?])\s+", block)[0].strip()
            use = one if 20 <= len(one) <= 140 else block[:140].strip()
            if _looks_like_capability_filler(use):
                return None
            words = use.split()
            if len(words) > 14:
                use = " ".join(words[:14]).rstrip(",;:") + "..."
            return use[:120].strip() or None
    sec = proposal.get("sections")
    if not isinstance(sec, dict):
        return None
    ex = str(sec.get("opening") or sec.get("hook") or sec.get("executive_summary") or "").strip()
    if len(ex) < 24:
        return None
    ex = re.sub(r"\*\*([^*]+)\*\*", r"\1", ex)
    ex = re.sub(r"^#+\s*", "", ex, flags=re.MULTILINE)
    block = ex.split("\n\n")[0].split("\n")[0].strip()
    if len(block) < 24:
        return None
    pleasant = (
        "thank you",
        "dear ",
        "we are pleased",
        "this proposal",
        "introduction",
        "attached please",
        "per your request",
    )
    low = block.lower()
    if any(low.startswith(p) for p in pleasant):
        return None
    if _looks_like_capability_filler(block):
        return None
    # First sentence only
    one = re.split(r"(?<=[.!?])\s+", block)[0].strip()
    use = one if 20 <= len(one) <= 140 else block[:140].strip()
    if _looks_like_capability_filler(use):
        return None
    words = use.split()
    if len(words) > 14:
        use = " ".join(words[:14]).rstrip(",;:") + "..."
    return use[:120].strip() or None


def _job_signals_from_requirements(req: RequirementAgentOutput | None) -> JobUnderstandingOutput | None:
    """Enterprise DAG has no separate job-signals LLM; synthesize buyer_intent for titling only."""
    if req is None:
        return None
    explicit: list[str] = []
    for row in req.requirement_matrix[:10]:
        d = (row.description or "").strip()
        if len(d) >= 12 and d not in explicit:
            explicit.append(d[:420])
    for s in req.requirements[:8]:
        t = str(s).strip()
        if len(t) >= 12 and t not in explicit:
            explicit.append(t[:420])
    for st in req.structured_requirements[:8]:
        t = (st.text or "").strip()
        if len(t) >= 12 and t not in explicit:
            explicit.append(t[:420])
    buyer = (explicit[0][:200] if explicit else "").strip()
    if not buyer:
        return None
    return JobUnderstandingOutput(
        explicit_requirements=explicit[:14],
        implicit_requirements=[],
        buyer_intent=buyer,
        decision_triggers=[],
        recommended_tone="",
        urgency="",
        buyer_sophistication="",
        budget_sensitivity="",
        conversion_triggers=[],
        risk_concerns=[str(x).strip() for x in req.risks[:8] if str(x).strip()],
    )


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


def _cap_title_words(title: str, max_words: int = 12) -> str:
    words = (title or "").split()
    if len(words) <= max_words:
        return (title or "").strip()
    return " ".join(words[:max_words]).strip()


def _ensure_title_word_band(title: str, ju: JobUnderstandingOutput | None) -> str:
    """Prefer 6–12 words: role + outcome, without echoing marketplace noise."""
    t = (title or "").strip()
    if not t:
        return t
    words = t.split()
    if len(words) < 6 and ju is not None:
        for x in ju.explicit_requirements[:3]:
            frag = _clean_line(str(x))
            if 10 < len(frag) < 90 and frag.lower() not in t.lower():
                merged = _shorten_opportunity_title(f"{t} — {frag}", max_len=110)
                return _cap_title_words(merged, 12)
    return _cap_title_words(t, 12)


def _title_contains_rejected_tokens(title: str) -> bool:
    """Product rule: avoid generic document labels in customer-visible titles."""
    return bool(_TITLE_BAD_TOKENS.search(title or ""))


def _pick_first_valid_title(candidates: list[str | None]) -> str | None:
    for raw in candidates:
        if not raw:
            continue
        t = _shorten_opportunity_title(str(raw).strip(), max_len=100)
        t = _cap_title_words(t, 12)
        if not t or t.lower() in _FORBIDDEN:
            continue
        if _looks_like_capability_filler(t):
            continue
        if _title_contains_rejected_tokens(t):
            continue
        return t
    return None


def infer_proposal_title(
    rfp_text: str,
    *,
    pipeline_mode: str,
    job_understanding: JobUnderstandingOutput | None = None,
    input_classification: InputClassifierOutput | None = None,
    requirements: RequirementAgentOutput | None = None,
    source_document_title: str | None = None,
    proposal_payload: dict[str, Any] | None = None,
) -> str:
    """Return a job-specific title; callers should persist this as the canonical run title."""
    rfp = (rfp_text or "").strip()
    lines = _first_meaningful_lines(rfp)
    candidates: list[str | None] = []
    ju_eff = job_understanding or _job_signals_from_requirements(requirements)

    # Job Understanding first (role + outcome beats raw post echo).
    if ju_eff is not None:
        candidates.append(_from_job_understanding(ju_eff))

    doc = _clean_source_document_title(source_document_title)
    if doc and doc.lower() not in _FORBIDDEN and not _looks_like_capability_filler(doc):
        candidates.append(doc)

    if pipeline_mode == "enterprise" or (input_classification and input_classification.input_type == "rfp"):
        opp = _title_from_rfp_opportunity(lines)
        if opp and opp.lower() not in _FORBIDDEN:
            candidates.append(opp)

    if lines:
        head = lines[0]
        if pipeline_mode == "freelance" or (
            input_classification and input_classification.input_type in ("job_post", "upwork", "freelancer")
        ):
            if len(head) >= 10 and not _looks_like_capability_filler(head):
                if not (head.endswith(".") and len(head) > 72):
                    cand = _shorten_opportunity_title(head, max_len=100) if len(head) > 100 else head[:160]
                    if cand.lower() not in _FORBIDDEN:
                        candidates.append(cand)

    req_title = _from_requirements(requirements)
    if req_title and req_title.lower() not in _FORBIDDEN and not _looks_like_capability_filler(req_title):
        candidates.append(req_title)

    if lines:
        for ln in lines[:6]:
            snippet = ln[:140].strip()
            s_low = snippet.lower()
            if len(snippet) < 12 or s_low in _FORBIDDEN:
                continue
            if _looks_like_capability_filler(snippet):
                continue
            if snippet.endswith(".") and len(snippet) > 72:
                continue
            if not _looks_like_compliance_clause(snippet):
                candidates.append(snippet)

    pe = _title_from_proposal_excerpt(proposal_payload)
    if pe and pe.lower() not in _FORBIDDEN and not _looks_like_capability_filler(pe):
        candidates.append(pe)

    if lines:
        candidates.append(_shorten_opportunity_title(lines[0], max_len=100))
    head = (rfp or "").strip().split("\n", 1)[0].strip()
    if len(head) >= 8:
        candidates.append(_clean_line(head))

    picked = _pick_first_valid_title(candidates)
    if not picked:
        return "Proposal from your brief"
    return _ensure_title_word_band(picked, ju_eff)
