from __future__ import annotations

import json

from bidforge_prompts.formatter import FORMATTER_PROMPT_VERSION
from bidforge_prompts.proposal import PROPOSAL_PROMPT_VERSION, build_proposal_messages
from bidforge_prompts.requirement import REQUIREMENT_PROMPT_VERSION
from bidforge_prompts.structuring import STRUCTURING_PROMPT_VERSION
from bidforge_prompts.strategy import STRATEGY_PROMPT_VERSION, build_strategy_messages
from bidforge_prompts.verifier import VERIFIER_PROMPT_VERSION, build_verifier_messages
from bidforge_schemas import (
    FormatterAgentOutput,
    ProposalAgentOutput,
    ProposalSection,
    RagContext,
    RequirementAgentOutput,
    StrategyAgentOutput,
)
from bidforge_shared import StubLLM

from bidforge_agents.formatter_agent import run_formatter_agent
from bidforge_agents.strategy_agent import run_strategy_agent


def test_all_prompts_declare_version() -> None:
    assert REQUIREMENT_PROMPT_VERSION == "1.0.0"
    assert STRUCTURING_PROMPT_VERSION == "2.0.0"
    assert STRATEGY_PROMPT_VERSION == "2.1.0"
    assert PROPOSAL_PROMPT_VERSION == "3.0.0"
    assert FORMATTER_PROMPT_VERSION == "3.0.0"
    assert VERIFIER_PROMPT_VERSION == "3.0.0"


def test_strategy_prompt_includes_memory_block() -> None:
    sys, user = build_strategy_messages('{"requirements":[]}', "{}")
    assert "2.1.0" in sys
    assert "PROPOSAL_MEMORY_JSON" in user


def test_proposal_prompt_includes_memory_block() -> None:
    sys, user = build_proposal_messages('{"strategy":"x"}', '{"similar_proposals":[]}', "{}")
    assert "PROPOSAL_MEMORY_JSON" in user
    assert "REQUIREMENTS_JSON" in user


def test_strategy_agent_receives_rag_json() -> None:
    llm = StubLLM()
    llm.register(
        "strategy_agent",
        StrategyAgentOutput(
            strategy="s",
            based_on=["p1"],
            positioning="p",
            win_themes=["w"],
            differentiators=["d"],
            response_tone="t",
        ),
    )
    req = RequirementAgentOutput()
    rag = RagContext(similar_proposals=[{"id": "1", "excerpt": "past win"}])
    out = run_strategy_agent(req, llm, rag_context=rag)
    assert out.positioning == "p"
    assert out.based_on == ["p1"]


def test_formatter_normalization_stub_roundtrip() -> None:
    llm = StubLLM()
    llm.register(
        "formatter_agent",
        FormatterAgentOutput(
            executive_summary="A",
            technical_approach="B",
            delivery_plan="C",
            risk_management="D",
            format_notes=["n"],
        ),
    )
    prop = ProposalAgentOutput(
        sections=[
            ProposalSection(title="Executive summary", content="a"),
            ProposalSection(title="Technical approach", content="b"),
            ProposalSection(title="Delivery plan", content="c"),
            ProposalSection(title="Risk management", content="d"),
        ],
    )
    fmt = run_formatter_agent(prop, llm)
    assert fmt.executive_summary == "A"
    assert fmt.format_notes == ["n"]


def test_verifier_messages_shape() -> None:
    sys, _u = build_verifier_messages("{}", "{}")
    assert "score" in sys and "3.0.0" in sys and "weak_claims" in sys and "suggestions" in sys


def test_rag_context_json_shape() -> None:
    rag = RagContext(win_patterns=[{"label": "repeatable", "excerpt": "win theme"}])
    data = json.loads(rag.model_dump_json())
    assert set(data.keys()) == {
        "similar_proposals",
        "win_patterns",
        "methodology_blocks",
        "company_templates",
        "freelance_win_patterns",
    }
