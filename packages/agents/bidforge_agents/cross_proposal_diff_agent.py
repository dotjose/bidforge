from __future__ import annotations

import json
from typing import Any

from bidforge_prompts.cross_proposal_diff import build_cross_proposal_diff_messages
from bidforge_schemas import CrossProposalDiffOutput
from bidforge_shared import LLMClient

STEP = "cross_proposal_diff_agent"


def run_cross_proposal_diff_agent(
    current_proposal: dict[str, Any],
    prior_wins: list[dict[str, Any]],
    llm: LLMClient,
) -> CrossProposalDiffOutput:
    system, user = build_cross_proposal_diff_messages(
        json.dumps(current_proposal, ensure_ascii=False)[:24_000],
        json.dumps(prior_wins, ensure_ascii=False)[:24_000],
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=CrossProposalDiffOutput)
