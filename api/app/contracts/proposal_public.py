"""Strict client-facing proposal run contract — no evaluation internals, no RAG dumps."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProposalSectionPublic(BaseModel):
    title: str
    content: str


class CrossProposalDiffPublic(BaseModel):
    delta_score: int = Field(default=0, description="Score change vs prior saved run when chained; else 0.")
    improvements: list[str] = Field(default_factory=list)


class ProposalPublicRunResponse(BaseModel):
    """POST /api/proposal/run — only fields safe for UI."""

    proposal_id: str = Field(description="UUID of persisted run when saved; else same as internal trace id.")
    title: str
    executive_summary: str
    sections: list[ProposalSectionPublic]
    score: int = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    memory_used: bool
    cross_proposal_diff: CrossProposalDiffPublic


class ProposalSavedRunPublic(ProposalPublicRunResponse):
    """GET /api/proposal/runs/{id} — public proposal + RFP echo + workspace mode (not evaluation data)."""

    rfp_input: str = Field(default="", description="Original brief text for the left panel (persisted source input).")
    input_type: str = Field(
        default="",
        description="Classifier input_type for this run (e.g. rfp, job_post) when stored.",
    )
    pipeline_mode: Literal["enterprise", "freelance"] = Field(
        default="enterprise",
        description="Which brain path produced the stored run (for UI defaults only).",
    )


_SLUG_ONLY = re.compile(r"^[a-z0-9_\-]+$", re.I)
_PREFIXED = re.compile(r"^([a-z0-9_]+)\s*:\s*(.+)$", re.I)


def _strip_markdown_noise(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    return t.strip()


def sanitize_issues_for_public(raw: list[Any], *, limit: int = 8) -> list[str]:
    """Drop verifier slugs and internal codes; keep short human-facing lines."""
    out: list[str] = []
    for x in raw or []:
        s = str(x).strip()
        if not s or len(s) > 400:
            continue
        if _SLUG_ONLY.match(s) and "_" in s:
            continue
        m = _PREFIXED.match(s)
        if m:
            code, rest = m.group(1), m.group(2).strip()
            if code in {"generic_tone", "unclear_value", "weak_claim", "missing_requirement", "missing_memory_usage"}:
                if rest:
                    out.append(rest[:320])
                continue
        out.append(s[:320])
        if len(out) >= limit:
            break
    return out


def _bool_memory_used(
    *,
    memory_grounded: bool | None,
    memory_status: str | None,
    memory_used: dict[str, Any] | None,
) -> bool:
    if memory_grounded is True:
        return True
    if str(memory_status or "").lower() == "grounded":
        return True
    if isinstance(memory_used, dict):
        for key in ("similar_proposals", "win_patterns", "methodology_blocks", "freelance_win_patterns"):
            v = memory_used.get(key)
            if isinstance(v, list) and len(v) > 0:
                return True
    return False


def _last_paragraph(text: str, max_len: int = 900) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", t) if b.strip()]
    if len(blocks) >= 2:
        return blocks[-1][:max_len]
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    return lines[-1][:max_len] if lines else ""


def _enterprise_sections(sec: dict[str, Any]) -> tuple[str, list[ProposalSectionPublic]]:
    opening = _strip_markdown_noise(
        str(sec.get("opening") or sec.get("hook") or sec.get("executive_summary") or ""),
    )
    understanding = _strip_markdown_noise(str(sec.get("understanding") or sec.get("what_ill_deliver") or ""))
    solution = _strip_markdown_noise(str(sec.get("solution") or ""))
    execp = _strip_markdown_noise(str(sec.get("execution_plan") or sec.get("technical_approach") or ""))
    tl = _strip_markdown_noise(str(sec.get("timeline") or sec.get("timeline_block") or ""))
    deliv = _strip_markdown_noise(str(sec.get("deliverables") or sec.get("deliverables_block") or ""))
    experience = _strip_markdown_noise(str(sec.get("experience") or sec.get("relevant_experience") or ""))
    risks = _strip_markdown_noise(
        str(sec.get("risks") or sec.get("risk_reduction") or sec.get("risk_management") or ""),
    )
    nxt = _strip_markdown_noise(str(sec.get("next_step") or sec.get("call_to_action") or ""))
    cta = nxt or _last_paragraph(opening, max_len=700)
    if understanding or solution or execp or tl or deliv:
        sections: list[ProposalSectionPublic] = []
        if opening:
            sections.append(ProposalSectionPublic(title="Opening", content=opening))
        sections.extend(
            [
            ProposalSectionPublic(title="Understanding", content=understanding),
            ProposalSectionPublic(title="Solution", content=solution),
            ProposalSectionPublic(title="Execution Plan", content=execp),
            ProposalSectionPublic(title="Timeline", content=tl),
            ProposalSectionPublic(title="Deliverables", content=deliv),
            ProposalSectionPublic(title="Risk Management", content=risks),
            ProposalSectionPublic(title="Relevant Experience", content=experience),
            ProposalSectionPublic(title="Next Step", content=cta),
            ]
        )
        return opening, [s for s in sections if s.content.strip() or s.title == "Next Step"]
    ex = _strip_markdown_noise(str(sec.get("executive_summary") or opening or ""))
    tech = _strip_markdown_noise(str(sec.get("technical_approach") or execp or ""))
    delivery = _strip_markdown_noise(str(sec.get("delivery_plan") or ""))
    risk2 = _strip_markdown_noise(str(sec.get("risk_management") or risks or ""))
    cta2 = nxt or _last_paragraph(ex, max_len=700)
    rel2 = risk2 if len(risk2) > 48 else (tech[800:2400] if len(tech) > 800 else risk2)
    sections = [
        ProposalSectionPublic(title="Execution Plan", content=tech),
        ProposalSectionPublic(title="Timeline & deliverables", content=delivery),
        ProposalSectionPublic(title="Relevant Experience", content=rel2),
        ProposalSectionPublic(title="Next Step", content=cta2),
    ]
    return ex, sections


def _freelance_sections(prop: dict[str, Any]) -> tuple[str, list[ProposalSectionPublic]]:
    fl = prop.get("freelance") if isinstance(prop.get("freelance"), dict) else {}
    op = _strip_markdown_noise(str(fl.get("opening") or fl.get("hook") or ""))
    und = _strip_markdown_noise(str(fl.get("understanding") or fl.get("understanding_need") or ""))
    sol = _strip_markdown_noise(str(fl.get("solution") or fl.get("approach") or ""))
    rel = _strip_markdown_noise(str(fl.get("experience") or fl.get("relevant_experience") or ""))
    nxt = _strip_markdown_noise(str(fl.get("next_step") or fl.get("call_to_action") or ""))
    tasks = "\n".join(f"- {str(t).strip()}" for t in (fl.get("execution_tasks") or []) if str(t).strip())
    tw = "\n".join(
        str(x).strip() for x in (fl.get("timeline") or fl.get("timeline_weeks") or []) if str(x).strip()
    )
    dl = "\n".join(
        f"- {str(d).strip()}" for d in (fl.get("deliverables") or fl.get("deliverables_list") or []) if str(d).strip()
    )
    rm = _strip_markdown_noise(str(fl.get("risks") or fl.get("risks_mitigation") or ""))
    exec_summary = op or und or (sol[:900] if sol else "")
    sections: list[ProposalSectionPublic] = []
    if op:
        sections.append(ProposalSectionPublic(title="Opening", content=op))
    sections.extend(
        [
        ProposalSectionPublic(title="Understanding", content=und),
        ProposalSectionPublic(title="Solution", content=sol),
        ProposalSectionPublic(title="Execution Plan", content=tasks),
        ProposalSectionPublic(title="Timeline", content=tw),
        ProposalSectionPublic(title="Deliverables", content=dl),
        ProposalSectionPublic(title="Risk Management", content=rm),
        ProposalSectionPublic(title="Relevant Experience", content=rel),
        ProposalSectionPublic(title="Next Step", content=nxt),
        ]
    )
    return exec_summary, [s for s in sections if s.content.strip() or s.title == "Next Step"]


def _writer_shape_sections(proposal: dict[str, Any]) -> tuple[str, list[ProposalSectionPublic]] | None:
    raw = proposal.get("sections")
    if not isinstance(raw, list) or not raw:
        return None
    first = raw[0]
    if not isinstance(first, dict) or "content" not in first or "title" not in first:
        return None
    sections: list[ProposalSectionPublic] = []
    overview_ex = ""
    for item in raw:
        if not isinstance(item, dict):
            continue
        t = str(item.get("title") or "").strip()
        c = _strip_markdown_noise(str(item.get("content") or ""))
        if not t:
            continue
        sections.append(ProposalSectionPublic(title=t, content=c))
        if t.lower() == "overview" and c and not overview_ex:
            overview_ex = c.split("\n\n")[0].split("\n")[0].strip()[:900]
    if not sections:
        return None
    exec_summary = overview_ex or (sections[0].content[:900] if sections[0].content else "")
    kept = [s for s in sections if s.content.strip() or s.title.strip().lower() == "next steps"]
    return exec_summary, kept


def build_sections_and_executive_summary(
    proposal: dict[str, Any] | None,
    *,
    pipeline_mode: Literal["enterprise", "freelance"],
) -> tuple[str, list[ProposalSectionPublic]]:
    if not isinstance(proposal, dict):
        return "", []
    wr = _writer_shape_sections(proposal)
    if wr is not None:
        return wr
    sec = proposal.get("sections")
    if pipeline_mode == "freelance" and isinstance(proposal.get("freelance"), dict):
        ex, parts = _freelance_sections(proposal)
        if ex or any(p.content.strip() for p in parts):
            return ex, parts
    if isinstance(sec, dict):
        return _enterprise_sections(sec)
    return "", []


def build_cross_proposal_diff_public(
    diff: dict[str, Any] | None,
    *,
    delta_score: int = 0,
    max_items: int = 12,
) -> CrossProposalDiffPublic:
    improvements: list[str] = []
    if isinstance(diff, dict):
        for key in ("stronger_hooks", "missing_signals", "better_cta", "structure_optimization"):
            v = diff.get(key)
            if isinstance(v, list):
                for item in v:
                    t = str(item).strip()
                    if t and t not in improvements:
                        improvements.append(t[:400])
                    if len(improvements) >= max_items:
                        break
            if len(improvements) >= max_items:
                break
    return CrossProposalDiffPublic(delta_score=int(delta_score), improvements=improvements[:max_items])


def build_public_run_response(
    *,
    proposal: dict[str, Any] | None,
    score: int,
    issues: list[Any],
    title: str,
    pipeline_mode: str,
    memory_grounded: bool | None,
    memory_status: str | None,
    memory_used: dict[str, Any] | None,
    cross_proposal_diff: dict[str, Any] | None,
    persisted_run_id: str | None,
    run_id: str,
    cross_diff_delta_score: int = 0,
) -> ProposalPublicRunResponse:
    pm: Literal["enterprise", "freelance"] = "freelance" if pipeline_mode == "freelance" else "enterprise"
    ex, sections = build_sections_and_executive_summary(proposal, pipeline_mode=pm)
    pid = (persisted_run_id or "").strip() or (run_id or "").strip()
    return ProposalPublicRunResponse(
        proposal_id=pid,
        title=(title or "").strip()[:512],
        executive_summary=ex,
        sections=sections,
        score=max(0, min(100, int(score))),
        issues=sanitize_issues_for_public(list(issues or [])),
        memory_used=_bool_memory_used(
            memory_grounded=memory_grounded,
            memory_status=memory_status,
            memory_used=memory_used,
        ),
        cross_proposal_diff=build_cross_proposal_diff_public(
            cross_proposal_diff,
            delta_score=cross_diff_delta_score,
        ),
    )


def build_public_from_stored_proposal_output(
    po: dict[str, Any],
    *,
    row_title: str,
    row_score: int,
    row_issues: list[Any],
    row_id: str,
    rfp_input: str,
    input_type: str = "",
    row_pipeline_mode: str | None = None,
) -> ProposalSavedRunPublic:
    """Rebuild public contract from DB `proposal_content` blob (may contain internal pipeline fields)."""
    proposal = po.get("proposal") if isinstance(po.get("proposal"), dict) else None
    pm = str(po.get("pipeline_mode") or row_pipeline_mode or "enterprise")
    pm_lit: Literal["enterprise", "freelance"] = "freelance" if pm == "freelance" else "enterprise"
    mem_used = po.get("memory_used") if isinstance(po.get("memory_used"), dict) else {}
    diff = po.get("cross_proposal_diff") if isinstance(po.get("cross_proposal_diff"), dict) else None
    ps = po.get("pipeline_state") if isinstance(po.get("pipeline_state"), dict) else {}
    delta = int(ps.get("cross_diff_delta_score") or 0)
    pub = build_public_run_response(
        proposal=proposal,
        score=int(row_score),
        issues=list(row_issues or []),
        title=str(row_title or ""),
        pipeline_mode=pm_lit,
        memory_grounded=bool(po.get("memory_grounded")),
        memory_status=str(po.get("memory_status") or ""),
        memory_used=mem_used,
        cross_proposal_diff=diff,
        persisted_run_id=str(row_id),
        run_id=str(po.get("trace_id") or row_id),
        cross_diff_delta_score=delta,
    )
    return ProposalSavedRunPublic(
        **pub.model_dump(),
        rfp_input=(rfp_input or "").strip(),
        input_type=(input_type or "").strip()[:128],
        pipeline_mode=pm_lit,
    )


def minimal_failed_public(*, title: str, run_id: str) -> ProposalPublicRunResponse:
    body = (
        "We could not finish this draft automatically. Try again with a shorter brief, "
        "or check your connection."
    )
    return ProposalPublicRunResponse(
        proposal_id=run_id,
        title=(title or "Proposal")[:512],
        executive_summary=body,
        sections=[
            ProposalSectionPublic(title="Execution Plan", content=""),
            ProposalSectionPublic(title="Timeline", content=""),
            ProposalSectionPublic(title="Deliverables", content=""),
            ProposalSectionPublic(title="Call to Action", content=""),
        ],
        score=0,
        issues=[],
        memory_used=False,
        cross_proposal_diff=CrossProposalDiffPublic(delta_score=0, improvements=[]),
    )
