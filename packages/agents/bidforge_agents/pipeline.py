"""Sequential pipeline — deterministic ordering, no side effects beyond LLM I/O."""

from __future__ import annotations

from dataclasses import dataclass

from bidforge_schemas import (
    FormatterAgentOutput,
    ProposalAgentOutput,
    RagContext,
    RequirementAgentOutput,
    StrategyAgentOutput,
    TimelineAgentOutput,
    VerifierAgentOutput,
)
from bidforge_shared import LLMClient

from bidforge_agents.formatter_agent import run_formatter_agent
from bidforge_agents.proposal_agent import run_proposal_agent
from bidforge_agents.proposal_sanitize import sanitize_formatter_output
from bidforge_agents.requirement_agent import run_requirement_agent
from bidforge_agents.strategy_agent import run_strategy_agent
from bidforge_agents.timeline_agent import run_timeline_agent
from bidforge_agents.verifier_agent import run_verifier_agent


@dataclass(frozen=True)
class PipelineStages:
    rag: RagContext
    requirements: RequirementAgentOutput
    strategy: StrategyAgentOutput
    proposal: ProposalAgentOutput
    timeline: TimelineAgentOutput
    formatted: FormatterAgentOutput
    verification: VerifierAgentOutput


def run_stages_after_requirements(
    requirements: RequirementAgentOutput,
    llm: LLMClient,
    *,
    rag_context: RagContext,
    rfp_text: str = "",
    workspace_preferences: str = "",
) -> tuple[StrategyAgentOutput, ProposalAgentOutput, TimelineAgentOutput, FormatterAgentOutput, VerifierAgentOutput]:
    strat = run_strategy_agent(
        requirements,
        llm,
        rag_context=rag_context,
        workspace_preferences=workspace_preferences,
    )
    prop = run_proposal_agent(
        strat,
        llm,
        rag_context=rag_context,
        workspace_preferences=workspace_preferences,
        requirements=requirements,
    )
    timeline = run_timeline_agent(rfp_text, requirements)
    fmt = sanitize_formatter_output(run_formatter_agent(prop, llm))
    ver = run_verifier_agent(
        fmt,
        requirements,
        llm,
        strategy=strat,
        rag_context=rag_context,
    )
    return strat, prop, timeline, fmt, ver


def run_pipeline_stages(
    rfp_text: str,
    llm: LLMClient,
    *,
    rag_context: RagContext | None = None,
) -> PipelineStages:
    req = run_requirement_agent(rfp_text, llm)
    rag = rag_context or RagContext()
    strat, prop, timeline, fmt, ver = run_stages_after_requirements(
        req,
        llm,
        rag_context=rag,
        rfp_text=rfp_text,
        workspace_preferences="",
    )
    return PipelineStages(
        rag=rag,
        requirements=req,
        strategy=strat,
        proposal=prop,
        timeline=timeline,
        formatted=fmt,
        verification=ver,
    )
