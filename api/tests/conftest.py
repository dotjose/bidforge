from __future__ import annotations

import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("SKIP_AUTH", "1")
os.environ.setdefault("REQUIRE_RAG_MEMORY", "false")
import pytest
from bidforge_schemas import (
    InputClassifierOutput,
    JobUnderstandingOutput,
    ProposalWriterOutput,
    ProposalWriterSection,
    RequirementAgentOutput,
    RequirementRow,
    RequirementStructuringOutput,
    SolutionBlueprintOutput,
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
        "router",
        InputClassifierOutput(
            input_type="rfp",
            recommended_pipeline="enterprise",
            rationale="stub: formal RFP",
        ),
    )
    llm.register(
        "job_intel__extract",
        RequirementAgentOutput(
            requirements=["Meet Section 4.2 with mapped acceptance tests", "EU data residency"],
            constraints=["Response due March 1", "Max 40 pages"],
            risks=["Tight evaluation window"],
            compliance_items=["SOC 2 Type II attestation", "EU data residency"],
        ),
    )
    llm.register(
        "job_intel__matrix",
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
        "solution__blueprint",
        SolutionBlueprintOutput(
            tasks=[
                "Map EU data flows to REQ_1 acceptance tests",
                "Stand up SOC 2 control evidence pack",
                "Deliver phased rollout with rollback gates",
                "Run weekly steering with RAID transparency",
            ],
            timeline=[
                "Week 1 — discovery + residency mapping",
                "Week 2 — integration slice + automated tests",
                "Week 3 — pilot hardening + handover",
            ],
            deliverables=[
                "Control matrix workbook",
                "Deployed platform baseline in EU region",
                "Rollback-tested release notes",
                "Training deck + operator runbook",
            ],
        ),
    )
    llm.register(
        "solution__strategy",
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
        "proposal",
        ProposalWriterOutput(
            title="EU SOC 2 aligned delivery with Postgres-backed checkpoints",
            sections=[
                ProposalWriterSection(
                    title="Overview",
                    content=(
                        "You need EU residency plus SOC 2 evidence that buyers trust; we anchor on shipped "
                        "Postgres audit patterns and Jira-tracked RAID cadence."
                    ),
                ),
                ProposalWriterSection(
                    title="Solution",
                    content="Phased delivery ties your REQ_1 matrix to integration slices with automated verification in AWS.",
                ),
                ProposalWriterSection(
                    title="Execution Plan",
                    content=(
                        "- Map EU data flows to REQ_1 acceptance tests using Postgres-backed fixtures\n"
                        "- Stand up SOC 2 control evidence pack with git-based change history\n"
                        "- Deliver phased rollout with rollback gates monitored via FastAPI health checks\n"
                        "- Run weekly steering with RAID transparency documented in Jira"
                    ),
                ),
                ProposalWriterSection(
                    title="Timeline",
                    content=(
                        "Week 1 — discovery + residency mapping\n"
                        "Week 2 — AWS integration slice + automated tests\n"
                        "Week 3 — pilot hardening + handover"
                    ),
                ),
                ProposalWriterSection(
                    title="Deliverables",
                    content=(
                        "Control matrix workbook, PostgreSQL migration pack, rollback-tested release notes, "
                        "and operator training deck with acceptance criteria."
                    ),
                ),
                ProposalWriterSection(
                    title="Risk Management",
                    content="Residual regulatory change managed via staged rollouts and explicit legal review gates.",
                ),
                ProposalWriterSection(
                    title="Next Steps",
                    content="Book a 30-minute architecture alignment this week.",
                ),
            ],
        ),
    )
    llm.register(
        "verifier",
        VerifierAgentOutput(
            score=82,
            issues=[],
            missing_requirements=[],
            compliance_risks=[],
            weak_claims=[],
        ),
    )
    return llm


def stub_llm_freelance_happy_path() -> StubLLM:
    llm = StubLLM()
    llm.register(
        "router",
        InputClassifierOutput(
            input_type="upwork",
            recommended_pipeline="freelance",
            rationale="stub: platform job",
        ),
    )
    llm.register(
        "job_intel__signals",
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
        "solution__blueprint",
        SolutionBlueprintOutput(
            tasks=[
                "Map FastAPI routes for LLM endpoints",
                "Add structured logging + eval harness",
                "Ship RAG retrieval with pgvector",
                "Wire OpenAI JSON mode for stable outputs",
            ],
            timeline=[
                "Week 1 — repo audit + API contract",
                "Week 2 — vertical slice + tests",
                "Week 3 — hardening + handoff",
            ],
            deliverables=[
                "Working FastAPI service",
                "Eval notebook + fixtures",
                "Deployment checklist",
            ],
        ),
    )
    llm.register(
        "solution__strategy_job",
        StrategyAgentOutput(
            strategy="Lead with shipped AI automation; anchor to win memory.",
            based_on=["win-1"],
            positioning="Senior builder who de-risks delivery",
            win_themes=["Speed", "Proof"],
            differentiators=["Similar builds", "Clear comms"],
            response_tone="direct, warm, expert",
            freelance_hook_strategy="Emphasize shipped FastAPI + eval proof; concise tone.",
        ),
    )
    llm.register(
        "proposal",
        ProposalWriterOutput(
            title="FastAPI LLM integration with pgvector and eval harness",
            sections=[
                ProposalWriterSection(
                    title="Overview",
                    content=(
                        "You need FastAPI + LLM glue with low rework risk; I lead with a shipped slice, "
                        "Postgres-backed evals, and async updates that respect your timeline."
                    ),
                ),
                ProposalWriterSection(
                    title="Solution",
                    content="Discovery-first vertical slice with pgvector retrieval and OpenAI JSON-mode clients on AWS.",
                ),
                ProposalWriterSection(
                    title="Execution Plan",
                    content=(
                        "- Map FastAPI routes for LLM endpoints with pytest coverage in CI\n"
                        "- Add structured logging + Postgres-backed eval harness\n"
                        "- Ship RAG retrieval with pgvector using OpenAI embeddings API\n"
                        "- Wire OpenAI JSON mode for stable outputs with Slack alerts on regressions"
                    ),
                ),
                ProposalWriterSection(
                    title="Timeline",
                    content=(
                        "Week 1 — repo audit + API contract\n"
                        "Week 2 — RAG slice + eval harness\n"
                        "Week 3 — hardening + handoff checklist"
                    ),
                ),
                ProposalWriterSection(
                    title="Deliverables",
                    content=(
                        "Runnable FastAPI + RAG service, eval fixtures with logged scores in Postgres, "
                        "README with deploy + rollback steps, and backlog for scale-up milestones."
                    ),
                ),
                ProposalWriterSection(
                    title="Risk Management",
                    content=(
                        "Scope drift frozen with OpenAPI contract Week 1. Model regression blocked with golden eval set. "
                        "Secrets stay in env/Vault — no keys in git."
                    ),
                ),
                ProposalWriterSection(
                    title="Next Steps",
                    content="Reply with your preferred stack for embeddings and I will propose a 48h slice with acceptance checks.",
                ),
            ],
        ),
    )
    llm.register(
        "verifier_job",
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
    return llm


def stub_llm_compliance_fail() -> StubLLM:
    llm = stub_llm_happy_path()
    llm.register(
        "verifier",
        VerifierAgentOutput(
            score=52,
            issues=["Executive summary lacks measurable proof points"],
            missing_requirements=["EU data residency operational detail"],
            compliance_risks=["SOC 2 Type II evidence not explicit in proposal body"],
            weak_claims=[],
        ),
    )
    return llm
