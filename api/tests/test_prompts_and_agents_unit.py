from __future__ import annotations

import json

from bidforge_prompts.job_intel import (
    JOB_INTEL_EXTRACT_PROMPT_VERSION,
    JOB_INTEL_MATRIX_PROMPT_VERSION,
    JOB_INTEL_SIGNALS_PROMPT_VERSION,
)
from bidforge_prompts.proposal import PROPOSAL_PROMPT_VERSION
from bidforge_prompts.solution import (
    SOLUTION_BLUEPRINT_PROMPT_VERSION,
    SOLUTION_STRATEGY_ENTERPRISE_PROMPT_VERSION,
    SOLUTION_STRATEGY_JOB_PROMPT_VERSION,
    build_solution_strategy_enterprise_messages,
)
from bidforge_prompts.verifier import VERIFIER_ENTERPRISE_PROMPT_VERSION, VERIFIER_JOB_PROMPT_VERSION, build_verifier_enterprise_messages
from bidforge_schemas import (
    ProposalWriterOutput,
    ProposalWriterSection,
    RagContext,
    RequirementAgentOutput,
    SolutionBlueprintOutput,
    StrategyAgentOutput,
)
from bidforge_shared import StubLLM

from bidforge_agents.solution_agent import run_solution_strategy_enterprise


def test_all_prompts_declare_version() -> None:
    assert JOB_INTEL_EXTRACT_PROMPT_VERSION == "1.0.0"
    assert JOB_INTEL_MATRIX_PROMPT_VERSION == "2.0.0"
    assert JOB_INTEL_SIGNALS_PROMPT_VERSION == "2.0.0"
    assert SOLUTION_STRATEGY_ENTERPRISE_PROMPT_VERSION == "2.1.0"
    assert SOLUTION_STRATEGY_JOB_PROMPT_VERSION == "3.0.0"
    assert SOLUTION_BLUEPRINT_PROMPT_VERSION == "1.0.0"
    assert PROPOSAL_PROMPT_VERSION == "1.0.0"
    assert VERIFIER_ENTERPRISE_PROMPT_VERSION == "3.0.0"
    assert VERIFIER_JOB_PROMPT_VERSION == "3.0.0"


def test_strategy_prompt_includes_memory_and_blueprint_blocks() -> None:
    sys, user = build_solution_strategy_enterprise_messages(
        '{"requirements":[]}',
        "{}",
        solution_blueprint_json='{"tasks":[]}',
    )
    assert "2.1.0" in sys
    assert "PROPOSAL_MEMORY_JSON" in user
    assert "SOLUTION_BLUEPRINT_JSON" in user


def test_solution_strategy_enterprise_receives_rag_json() -> None:
    llm = StubLLM()
    llm.register(
        "solution__strategy",
        StrategyAgentOutput(
            strategy="s",
            based_on=["p1"],
            positioning="p",
            win_themes=["w"],
            differentiators=["d"],
            response_tone="t",
            freelance_hook_strategy="",
        ),
    )
    req = RequirementAgentOutput()
    rag = RagContext(similar_proposals=[{"id": "1", "excerpt": "past win"}])
    bp = SolutionBlueprintOutput(tasks=["a", "b", "c", "d"], timeline=["Week 1 — x"], deliverables=["x", "y", "z"])
    out = run_solution_strategy_enterprise(req, llm, rag_context=rag, solution_blueprint=bp)
    assert out.positioning == "p"
    assert out.based_on == ["p1"]


def test_verifier_messages_shape() -> None:
    pw = ProposalWriterOutput(
        title="T",
        sections=[ProposalWriterSection(title="Overview", content="Hello with Postgres plan.")],
    )
    sys, _u = build_verifier_enterprise_messages(pw.model_dump_json(), "{}")
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
