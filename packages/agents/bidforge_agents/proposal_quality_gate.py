"""Hard validation after solution blueprint and proposal node — blueprint integrity, echo, generic filler."""

from __future__ import annotations

import re

from bidforge_schemas import (
    PROPOSAL_WRITER_SECTION_ORDER,
    ProposalWriterOutput,
    SolutionBlueprintOutput,
)
from bidforge_shared import PipelineStepError

# Hard-fail only on echo / broken-RAG markers and a few trite openers. Do not substring-match
# common adjectives (e.g. "comprehensive") — RFPs and good drafts use them; prompts + verifier
# still steer tone without blocking the whole pipeline.
_BANNED_SUBSTRINGS = (
    "executive summary",
    "technical approach",
    "no memory",
    "no memory found",
    "we are excited",
    "we specialize in",
    "proven track record",
)

_TIMELINE_RE = re.compile(
    r"\b(week\s*[1-9]\d?|week\s*one|week\s*two|phase\s*[1-9]|day\s*[1-9]\d?|\d+\s*[\-–]\s*week)\b",
    re.I,
)

_TOOLISH = re.compile(
    r"\b(api|sdk|sql|postgres|git|docker|kubernetes|aws|gcp|azure|hubspot|salesforce|"
    r"slack|jira|terraform|fastapi|react|node|python|typescript|openai|llm|ci\/cd|s3)\b",
    re.I,
)


def _bulletish_lines(block: str) -> list[str]:
    out: list[str] = []
    for ln in (block or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith(("-", "•", "*")) or re.match(r"^\d+[\).\s]", s):
            out.append(s)
    return out


def validate_solution_blueprint(bp: SolutionBlueprintOutput) -> None:
    tasks = [str(t).strip() for t in bp.tasks if str(t).strip()]
    if len(tasks) < 4:
        raise PipelineStepError(
            "proposal_quality",
            "Blueprint blocked: tasks[] must contain at least four non-empty items.",
            partial={"solution_blueprint": bp.model_dump()},
        )
    tls = [str(t).strip() for t in bp.timeline if str(t).strip()]
    if not tls:
        raise PipelineStepError(
            "proposal_quality",
            "Blueprint blocked: timeline[] must be non-empty.",
            partial={"solution_blueprint": bp.model_dump()},
        )
    joined_tl = "\n".join(tls)
    if not _TIMELINE_RE.search(joined_tl):
        raise PipelineStepError(
            "proposal_quality",
            "Blueprint blocked: each timeline line should reference Week, Day, or Phase.",
            partial={"solution_blueprint": bp.model_dump()},
        )
    dels = [str(d).strip() for d in bp.deliverables if str(d).strip()]
    if len(dels) < 3:
        raise PipelineStepError(
            "proposal_quality",
            "Blueprint blocked: deliverables[] must contain at least three non-empty items.",
            partial={"solution_blueprint": bp.model_dump()},
        )


def _echoes_source(source: str, proposal_blob: str) -> bool:
    blob = re.sub(r"\s+", " ", (proposal_blob or "").lower())
    hits = 0
    for ln in (source or "").splitlines():
        s = re.sub(r"\s+", " ", ln.strip().lower())
        if len(s) < 90:
            continue
        chunk = s[:220]
        if chunk and chunk in blob:
            hits += 1
        if hits >= 2:
            return True
    return False


def _blueprint_reflected_in_execution(exec_body: str, bp: SolutionBlueprintOutput) -> bool:
    body = (exec_body or "").lower()
    tasks = [str(t).strip() for t in bp.tasks if len(str(t).strip()) > 10]
    if not tasks:
        return False
    used = 0
    for task in tasks[:10]:
        frag = task.lower()[: min(48, len(task))]
        if frag and frag in body:
            used += 1
    need = min(3, len(tasks))
    return used >= need


def validate_proposal_writer_output(
    pw: ProposalWriterOutput,
    *,
    blueprint: SolutionBlueprintOutput,
    source_brief: str = "",
) -> None:
    titles = [s.title.strip() for s in pw.sections]
    if titles != list(PROPOSAL_WRITER_SECTION_ORDER):
        raise PipelineStepError(
            "proposal_quality",
            f"Proposal blocked: sections must match {list(PROPOSAL_WRITER_SECTION_ORDER)!r} in order.",
            partial={"proposal_writer": pw.model_dump()},
        )
    blob = "\n".join(f"{s.title}\n{s.content}" for s in pw.sections).lower()
    for b in _BANNED_SUBSTRINGS:
        if b in blob:
            raise PipelineStepError(
                "proposal_quality",
                f"Proposal blocked: banned phrasing ({b!r}).",
                partial={"proposal_writer": pw.model_dump()},
            )
    title = (pw.title or "").strip()
    if len(title) < 8 or len(title) > 200:
        raise PipelineStepError(
            "proposal_quality",
            "Proposal blocked: title must be derived (8–200 chars).",
            partial={"proposal_writer": pw.model_dump()},
        )
    tl_sec = next(s for s in pw.sections if s.title == "Timeline")
    if not _TIMELINE_RE.search(tl_sec.content or ""):
        raise PipelineStepError(
            "proposal_quality",
            "Proposal blocked: Timeline section must include explicit Week/Day/Phase scheduling.",
            partial={"proposal_writer": pw.model_dump()},
        )
    exec_sec = next(s for s in pw.sections if s.title == "Execution Plan")
    bullets = _bulletish_lines(exec_sec.content or "")
    if len(bullets) < 3:
        raise PipelineStepError(
            "proposal_quality",
            "Proposal blocked: Execution Plan needs at least three concrete step lines (leading - or 1.).",
            partial={"proposal_writer": pw.model_dump()},
        )
    # Soft gate: some strong proposals are tool-agnostic (esp. when the brief is non-technical).
    # Verifier + issues list will still surface vagueness; hard-blocking here causes false negatives.
    # Keep the stricter ">= 3 step lines" and "reflect blueprint tasks" checks above/below.
    if not _TOOLISH.search(exec_sec.content or ""):
        return
    del_sec = next(s for s in pw.sections if s.title == "Deliverables")
    if len((del_sec.content or "").strip()) < 40:
        raise PipelineStepError(
            "proposal_quality",
            "Proposal blocked: Deliverables section too thin — name tangible artifacts.",
            partial={"proposal_writer": pw.model_dump()},
        )
    if not _blueprint_reflected_in_execution(exec_sec.content or "", blueprint):
        raise PipelineStepError(
            "proposal_quality",
            "Proposal blocked: Execution Plan must reflect SOLUTION_BLUEPRINT tasks.",
            partial={"proposal_writer": pw.model_dump()},
        )
    if source_brief and len(source_brief.strip()) > 400 and _echoes_source(source_brief, blob):
        raise PipelineStepError(
            "proposal_quality",
            "Proposal blocked: output appears to echo the source brief — expand the blueprint instead.",
            partial={"proposal_writer": pw.model_dump()},
        )
