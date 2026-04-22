from __future__ import annotations

import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("SKIP_AUTH", "1")
os.environ.setdefault("REQUIRE_RAG_MEMORY", "false")

import pytest
from bidforge_schemas import (
    CrossProposalDiffOutput,
    FormatterAgentOutput,
    FreelanceHookOutput,
    FreelanceProposalOutput,
    InputClassifierOutput,
    JobUnderstandingOutput,
    ProposalAgentOutput,
    ProposalCritiqueOutput,
    ProposalSection,
    RequirementAgentOutput,
    RequirementRow,
    RequirementStructuringOutput,
    StrategyAgentOutput,
    VerifierAgentOutput,
)
from bidforge_shared import StubLLM


@pytest.fixture()
def sample_rfp() -> str:
    return (
        "CONFIDENTIAL RFP-2026-100 — responses due March 1.\n"
        "Vendor must address security, SOC 2 Type II, data residency in EU.\n"
        "Section 4.2: methodology, milestones, rollback. Map to acceptance tests.\n"
    )


def stub_llm_happy_path() -> StubLLM:
    llm = StubLLM()
    llm.register(
        "input_classifier",
        InputClassifierOutput(
            input_type="rfp",
            recommended_pipeline="enterprise",
            rationale="stub: formal RFP",
        ),
    )
    llm.register(
        "requirement_agent",
        RequirementAgentOutput(
            requirements=["Meet Section 4.2 with mapped acceptance tests", "EU data residency"],
            constraints=["Response due March 1", "Max 40 pages"],
            risks=["Tight evaluation window"],
            compliance_items=["SOC 2 Type II attestation", "EU data residency"],
        ),
    )
    llm.register(
        "requirement_structuring",
        RequirementStructuringOutput(
            requirements=[
                RequirementRow(
                    id="REQ_1",
                    type="deliverable",
                    description="Meet Section 4.2 with mapped acceptance tests",
                    mandatory=True,
                    source="Scope of Work",
                ),
                RequirementRow(
                    id="REQ_2",
                    type="compliance",
                    description="EU data residency",
                    mandatory=True,
                    source="Compliance",
                ),
            ],
        ),
    )
    llm.register(
        "strategy_agent",
        StrategyAgentOutput(
            strategy="Grounded in past EU SOC 2 wins and delivery cadence patterns.",
            based_on=["mem-gov-001", "pattern-delivery-2"],
            positioning="Trusted operator for regulated EU workloads",
            win_themes=["Proven delivery cadence", "Security-first architecture"],
            differentiators=["EU-native operations", "Embedded compliance reviews"],
            response_tone="precise and confident",
            freelance_hook_strategy="",
        ),
    )
    llm.register(
        "proposal_agent",
        ProposalAgentOutput(
            sections=[
                ProposalSection(
                    title="Executive summary",
                    content="We meet EU residency and SOC 2 expectations while delivering Section 4.2 milestones.",
                    covers_requirements=["REQ_1", "REQ_2"],
                    based_on_memory=["mem-gov-001"],
                ),
                ProposalSection(
                    title="Technical approach",
                    content="Phased rollout with rollback gates per acceptance mapping.",
                    covers_requirements=["REQ_1"],
                    based_on_memory=["pattern-delivery-2"],
                ),
                ProposalSection(
                    title="Delivery plan",
                    content="Weekly checkpoints, steering forum, transparent RAID log.",
                    covers_requirements=["REQ_1"],
                    based_on_memory=["pattern-delivery-2"],
                ),
                ProposalSection(
                    title="Risk management",
                    content="Residual regulatory change managed via change control and legal review.",
                    covers_requirements=["REQ_2"],
                    based_on_memory=["mem-gov-001"],
                ),
            ],
        ),
    )
    llm.register(
        "formatter_agent",
        FormatterAgentOutput(
            executive_summary="We meet EU residency and SOC 2 expectations while delivering Section 4.2 milestones.",
            technical_approach="Phased rollout with rollback gates per acceptance mapping.",
            delivery_plan="Weekly checkpoints, steering forum, transparent RAID log.",
            risk_management="Residual regulatory change managed via change control and legal review.",
            format_notes=["Normalized tone", "Tightened section balance"],
        ),
    )
    llm.register(
        "verifier_agent",
        VerifierAgentOutput(
            score=82,
            issues=[],
            missing_requirements=[],
            compliance_risks=[],
            weak_claims=[],
        ),
    )
    llm.register(
        "critique_agent",
        ProposalCritiqueOutput(
            improvements=["Tighten executive summary proof points"],
            reply_probability_delta="",
            enterprise_gap_summary="Minor compliance mapping gaps in delivery section.",
            top1_style_rewrite="",
        ),
    )
    llm.register(
        "cross_proposal_diff_agent",
        CrossProposalDiffOutput(
            stronger_hooks=["Lead with EU + SOC 2 proof in one line"],
            missing_signals=["Explicit acceptance-test mapping for REQ_1"],
            better_cta=["Offer a 30-minute compliance alignment call"],
            structure_optimization=["Keep risk section tied to named controls"],
        ),
    )
    return llm


def stub_llm_freelance_happy_path() -> StubLLM:
    llm = StubLLM()
    llm.register(
        "input_classifier",
        InputClassifierOutput(
            input_type="upwork",
            recommended_pipeline="freelance",
            rationale="stub: platform job",
        ),
    )
    llm.register(
        "job_understanding_agent",
        JobUnderstandingOutput(
            explicit_requirements=["Python", "FastAPI"],
            implicit_requirements=["wants low risk", "wants senior engineer"],
            buyer_intent="hire fast / shortlist candidates",
            decision_triggers=["proof of similar work", "clear timeline"],
            recommended_tone="concise, confident, direct",
            urgency="this_week",
            buyer_sophistication="mixed",
            budget_sensitivity="normal",
            conversion_triggers=["similar build proof", "fast first milestone"],
            risk_concerns=["scope creep", "unclear acceptance"],
        ),
    )
    llm.register(
        "strategy_agent_freelance",
        StrategyAgentOutput(
            strategy="Lead with shipped AI automation; anchor to win memory.",
            based_on=["win-1"],
            positioning="Senior builder who de-risks delivery",
            win_themes=["Speed", "Proof"],
            differentiators=["Similar builds", "Clear comms"],
            response_tone="direct, warm, expert",
            freelance_hook_strategy="Open with one-line outcome, then stack proof tease.",
        ),
    )
    llm.register(
        "freelance_hook_agent",
        FreelanceHookOutput(
            hook="I've shipped similar AI pipelines that cut manual ops ~60% in two weeks.",
            trust_signal="SaaS + LLM integrations (FastAPI, OpenAI, vector RAG)",
            relevance_match="High",
            alternative_hooks=[
                "If speed matters most: I can deliver a working FastAPI + RAG slice in 48h with logged evals.",
            ],
        ),
    )
    llm.register(
        "freelance_proposal_agent",
        FreelanceProposalOutput(
            hook="I've shipped similar AI pipelines that cut manual ops ~60% in two weeks.",
            understanding_need="• You need FastAPI + LLM glue with low rework risk\n• You want proof before scaling spend",
            approach="Discovery → thin vertical slice → daily async updates; eval harness from day one.",
            relevant_experience="Similar wins used short demos + logged evals to de-risk delivery (pattern win-1).",
            call_to_action="Reply with your preferred stack for embeddings and I’ll propose a 48h slice with acceptance checks.",
        ),
    )
    llm.register(
        "freelance_verifier_agent",
        VerifierAgentOutput(
            score=84,
            issues=[],
            missing_requirements=[],
            compliance_risks=[],
            weak_claims=[],
            reply_probability_score=0.84,
            hook_strength=0.9,
            trust_signals_score=0.78,
            conciseness_score=0.88,
            freelance_fail_flags=[],
        ),
    )
    llm.register(
        "critique_agent",
        ProposalCritiqueOutput(
            improvements=["Keep hook to two lines", "Name one metric from memory"],
            reply_probability_delta="+10%",
            enterprise_gap_summary="",
            top1_style_rewrite="",
        ),
    )
    llm.register(
        "cross_proposal_diff_agent",
        CrossProposalDiffOutput(
            stronger_hooks=["Name the buyer’s stack explicitly in the hook"],
            missing_signals=["One line on communication cadence"],
            better_cta=["Ask one scoping question instead of a generic ‘happy to chat’"],
            structure_optimization=["Merge proof into two scannable lines"],
        ),
    )
    return llm


def stub_llm_compliance_fail() -> StubLLM:
    llm = stub_llm_happy_path()
    llm.register(
        "verifier_agent",
        VerifierAgentOutput(
            score=52,
            issues=["Executive summary lacks measurable proof points"],
            missing_requirements=["EU data residency operational detail"],
            compliance_risks=["SOC 2 Type II evidence not explicit in proposal body"],
            weak_claims=[],
        ),
    )
    return llm
