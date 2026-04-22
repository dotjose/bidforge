"""Strict JSON contracts between pipeline stages — no free-form LLM surfaces."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class StructuredRequirementItem(BaseModel):
    """Indexed requirement line for traceability into proposal sections."""

    ref: str = Field(..., description="Stable id, e.g. REQ_1")
    text: str = Field(..., description="Single requirement statement")


class RequirementRow(BaseModel):
    """Requirement matrix row from structuring (maps to proposal coverage)."""

    id: str = Field(..., description="REQ_* stable id")
    type: Literal["deliverable", "compliance", "timeline"] = "deliverable"
    description: str = ""
    mandatory: bool = True
    source: str = "RFP"


class RagContext(BaseModel):
    """Grounding from proposal memory (pgvector). Empty means no indexed memory for this tenant."""

    similar_proposals: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Past proposal chunks: id, title, excerpt, outcome, section_type, similarity",
    )
    win_patterns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Reusable patterns: id, label, excerpt, tags, outcome",
    )
    methodology_blocks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Firm methodology excerpts: id, title, content, tags",
    )
    company_templates: list[str] = Field(
        default_factory=list,
        description="Legacy flat snippets mirrored from methodology for backward compatibility.",
    )
    freelance_win_patterns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="High-reply freelance hooks/snippets: type freelance_win_pattern, outcome, job_type, metrics",
    )

    def has_usable_memory(self) -> bool:
        """True when any non-empty enterprise grounding exists (excludes freelance win-only rows)."""
        for sp in self.similar_proposals:
            if isinstance(sp, dict) and (sp.get("excerpt") or "").strip():
                return True
        for wp in self.win_patterns:
            if isinstance(wp, dict) and (wp.get("excerpt") or wp.get("label") or "").strip():
                return True
        for mb in self.methodology_blocks:
            if isinstance(mb, dict) and (mb.get("content") or mb.get("title") or "").strip():
                return True
        for t in self.company_templates:
            if str(t).strip():
                return True
        return False

    def has_usable_freelance_memory(self) -> bool:
        """True when indexed freelance_win_pattern chunks exist for Win Engine retrieval."""
        for fp in self.freelance_win_patterns:
            if not isinstance(fp, dict):
                continue
            if str(fp.get("outcome") or "").lower() == "synthetic_seed":
                continue
            rid = str(fp.get("id") or "")
            if rid.startswith("_bidforge_synthetic"):
                continue
            if (fp.get("excerpt") or fp.get("label") or "").strip():
                return True
        return False


class RequirementAgentOutput(BaseModel):
    """Structured extraction from RFP / brief text."""

    requirements: list[str] = Field(default_factory=list, description="Must-have deliverables")
    constraints: list[str] = Field(default_factory=list, description="Hard limits (dates, pages, etc.)")
    risks: list[str] = Field(default_factory=list, description="Identified tender risks")
    compliance_items: list[str] = Field(
        default_factory=list,
        description="Named compliance / certification asks (e.g. SOC 2, ISO 27001)",
    )
    structured_requirements: list[StructuredRequirementItem] = Field(
        default_factory=list,
        description="REQ matrix refs — populated after structuring (from requirement_matrix).",
    )
    requirement_matrix: list[RequirementRow] = Field(
        default_factory=list,
        description="Typed requirement rows from structuring agent.",
    )


class RequirementStructuringOutput(BaseModel):
    """Requirement matrix from RFP extraction (merged into RequirementAgentOutput)."""

    requirements: list[RequirementRow] = Field(default_factory=list)


class StrategyAgentOutput(BaseModel):
    """Positioning plus narrative explicitly tied to memory patterns."""

    strategy: str = Field(
        default="",
        description="Coherent strategy narrative; MUST reference win patterns / methodology when RAG is non-empty.",
    )
    based_on: list[str] = Field(
        default_factory=list,
        description="Memory ids or labels the strategy explicitly builds on.",
    )
    positioning: str = ""
    win_themes: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    response_tone: str = Field(default="confident, precise, buyer-aligned")
    freelance_hook_strategy: str = Field(
        default="",
        description="Freelance Win Engine: how to open in 2–3 lines (empty in enterprise-only runs).",
    )


InputType = Literal["rfp", "job_post", "upwork", "freelancer", "manual"]
PipelineBrain = Literal["enterprise", "freelance"]


class InputClassifierOutput(BaseModel):
    """Stage-0 router: classify raw text and recommend which brain to run."""

    input_type: InputType = "job_post"
    recommended_pipeline: PipelineBrain = "enterprise"
    rationale: str = Field(default="", description="Short reason for routing decision")


class JobUnderstandingOutput(BaseModel):
    """Buyer psychology + implicit asks from messy job posts (freelance path only)."""

    explicit_requirements: list[str] = Field(default_factory=list)
    implicit_requirements: list[str] = Field(default_factory=list)
    buyer_intent: str = ""
    decision_triggers: list[str] = Field(default_factory=list)
    recommended_tone: str = ""
    urgency: str = Field(default="", description="e.g. hire_this_week / exploring / backlog")
    buyer_sophistication: str = Field(default="", description="junior / practitioner / expert buyer")
    budget_sensitivity: str = Field(default="", description="fixed_low / flexible / premium_ok")
    conversion_triggers: list[str] = Field(
        default_factory=list,
        description="Signals that increase reply probability (proof, speed, low risk).",
    )
    risk_concerns: list[str] = Field(
        default_factory=list,
        description="What would make them skip or ghost (scope creep, trust, timezone, etc.).",
    )


class FreelanceHookOutput(BaseModel):
    """First lines optimized for reply rate."""

    hook: str = ""
    trust_signal: str = ""
    relevance_match: str = Field(default="Medium", description="High | Medium | Low")
    alternative_hooks: list[str] = Field(
        default_factory=list,
        description="Up to two A/B variants for the opening (same job, different angle).",
    )

    @field_validator("alternative_hooks")
    @classmethod
    def _cap_alternatives(cls, v: list[str]) -> list[str]:
        return [str(x).strip() for x in v if str(x).strip()][:2]


class FreelanceProposalOutput(BaseModel):
    """Short conversion-first proposal (Upwork-style; never RFP section titles)."""

    hook: str = Field(default="", description="1–3 lines; must echo or lightly polish HOOK_TEXT")
    understanding_need: str = Field(
        default="",
        description="3–5 bullets max (plain lines); paraphrase job intent, not a wall of text",
    )
    approach: str = Field(default="", description="Very short execution plan; no theory")
    relevant_experience: str = Field(
        default="",
        description="Only relevant proof; cite memory patterns when present",
    )
    call_to_action: str = Field(default="", description="One line, low-friction CTA")

    @model_validator(mode="before")
    @classmethod
    def _legacy_opening_body_fields(cls, data: Any) -> Any:
        """Accept older {opening, body, proof, closing} JSON from models or caches."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if not str(out.get("hook", "")).strip() and str(out.get("opening", "")).strip():
            out["hook"] = str(out["opening"]).strip()
        if not str(out.get("call_to_action", "")).strip() and str(out.get("closing", "")).strip():
            out["call_to_action"] = str(out["closing"]).strip()
        if not str(out.get("relevant_experience", "")).strip() and str(out.get("proof", "")).strip():
            out["relevant_experience"] = str(out["proof"]).strip()
        # Legacy shape used `body` for execution copy (maps to approach), not buyer-need bullets.
        if not str(out.get("approach", "")).strip() and str(out.get("body", "")).strip():
            out["approach"] = str(out["body"]).strip()
        return out

    def to_formatter_slots(self) -> tuple[str, str, str, str]:
        """Map into legacy four slots for verifier shim / PDF keys."""
        proof_block = "\n\n".join(
            p for p in (self.approach.strip(), self.relevant_experience.strip()) if p
        )
        return (self.hook, self.understanding_need, proof_block, self.call_to_action)


class CrossProposalDiffOutput(BaseModel):
    """Compare current proposal against recent stored wins — all lists may be empty on degraded runs."""

    stronger_hooks: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    better_cta: list[str] = Field(default_factory=list)
    structure_optimization: list[str] = Field(default_factory=list)


class ProposalCritiqueOutput(BaseModel):
    """Mode-aware improvement hints (freelance emphasizes hook + reply delta)."""

    improvements: list[str] = Field(default_factory=list)
    reply_probability_delta: str = Field(default="", description="e.g. +12% or -5%")
    enterprise_gap_summary: str = Field(
        default="",
        description="Optional: compliance/structure gaps when in enterprise comparisons.",
    )
    top1_style_rewrite: str = Field(
        default="",
        description="Freelance: optional full bid rewritten in a top-1% reply style (empty for enterprise).",
    )


class ProposalSection(BaseModel):
    title: str = ""
    content: str = ""
    covers_requirements: list[str] = Field(default_factory=list, description="REQ_* refs covered")
    based_on_memory: list[str] = Field(
        default_factory=list,
        description="Memory ids or short labels this section grounded in",
    )


class ProposalAgentOutput(BaseModel):
    """Section-first draft; formatter normalizes to canonical four fields."""

    sections: list[ProposalSection] = Field(default_factory=list)


class TimelinePhase(BaseModel):
    phase: str = ""
    duration: str = ""


class TimelineAgentOutput(BaseModel):
    """Deterministic timeline normalization (no LLM)."""

    timeline: list[TimelinePhase] = Field(default_factory=list)


class FormatterAgentOutput(BaseModel):
    """Normalized proposal body — same section keys, cleaned copy."""

    executive_summary: str = ""
    technical_approach: str = ""
    delivery_plan: str = ""
    risk_management: str = ""
    format_notes: list[str] = Field(default_factory=list)


class VerifierAgentOutput(BaseModel):
    score: int = Field(ge=0, le=100)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(
        default_factory=list,
        description="Author-facing remediation hints; must never be copied into proposal body.",
    )
    missing_requirements: list[str] = Field(default_factory=list)
    compliance_risks: list[str] = Field(default_factory=list)
    weak_claims: list[str] = Field(default_factory=list)
    compliance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    completeness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reply_probability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    hook_strength: float | None = Field(default=None, ge=0.0, le=1.0)
    trust_signals_score: float | None = Field(default=None, ge=0.0, le=1.0)
    conciseness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    freelance_fail_flags: list[str] = Field(default_factory=list)


class ProposalRunResult(BaseModel):
    """API-facing payload after a successful pipeline run."""

    proposal: dict[str, Any]
    score: int
    issues: list[str]
    trace_id: str


class ProposalPipelineError(BaseModel):
    """Returned on controlled failure (partial state + reason)."""

    error: str
    trace_id: str
    failed_step: str
    partial: dict[str, Any] = Field(default_factory=dict)
