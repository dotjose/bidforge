"""Strict JSON contracts between pipeline stages — no free-form LLM surfaces."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
        description="Job-post path: short positioning for the proposal writer (not opening copy). Empty for enterprise.",
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


class CrossProposalDiffOutput(BaseModel):
    """Compare current proposal against recent stored wins — all lists may be empty on degraded runs."""

    stronger_hooks: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    better_cta: list[str] = Field(default_factory=list)
    structure_optimization: list[str] = Field(default_factory=list)


class SolutionBlueprintOutput(BaseModel):
    """Structured execution plan — ONLY the solution node's blueprint step may author these lists."""

    tasks: list[str] = Field(default_factory=list, description="Concrete execution steps")
    timeline: list[str] = Field(
        default_factory=list,
        description="Phases with timeboxes, e.g. Week 1 → discovery",
    )
    deliverables: list[str] = Field(default_factory=list, description="Named artifacts the client receives")


PROPOSAL_WRITER_SECTION_ORDER: tuple[str, ...] = (
    "Overview",
    "Solution",
    "Execution Plan",
    "Timeline",
    "Deliverables",
    "Risk Management",
    "Next Steps",
)


class ProposalWriterSection(BaseModel):
    title: str = ""
    content: str = ""


class ProposalWriterOutput(BaseModel):
    """Single-writer final proposal contract (DAG phase 4)."""

    title: str = Field(default="", description="Derived from blueprint + strategy, not generic product title.")
    sections: list[ProposalWriterSection] = Field(default_factory=list)


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
