"""CrossProposalDiffAgent — contrast current draft with last winning proposals."""

from __future__ import annotations


def build_cross_proposal_diff_messages(
    current_proposal_json: str,
    prior_wins_json: str,
) -> tuple[str, str]:
    system = (
        "You are CrossProposalDiffAgent. Compare the CURRENT proposal to PRIOR_WINNING_PROPOSALS "
        "(hooks and structure snippets only). Output strict JSON matching the schema: "
        "stronger_hooks, missing_signals, better_cta, structure_optimization — each a string array. "
        "Be concrete and non-repetitive; if prior wins are empty, return short heuristic suggestions "
        "for Upwork-style replies (hook clarity, proof, CTA). No markdown, JSON only."
    )
    user = (
        "CURRENT_PROPOSAL:\n"
        f"{current_proposal_json}\n\n"
        "PRIOR_WINNING_PROPOSALS (may be empty):\n"
        f"{prior_wins_json}\n"
    )
    return system, user
