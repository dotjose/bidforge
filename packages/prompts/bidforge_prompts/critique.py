"""Cross-proposal critique — freelance emphasizes hook, reply delta, optional top-1% rewrite."""

CRITIQUE_PROMPT_VERSION = "2.0.0"

_SYSTEM = f"""version: "{CRITIQUE_PROMPT_VERSION}"
You suggest improvements after verification (enterprise or freelance).
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "improvements": string[],
  "reply_probability_delta": string,
  "enterprise_gap_summary": string,
  "top1_style_rewrite": string
}}
Rules:
- improvements: 3–7 concrete edits (short imperatives).
- Never instruct pasting verifier output, scores, or issue lists into the proposal body.
- MODE is given in the user message.
- If MODE=freelance: reply_probability_delta is required (e.g. "+12%"); enterprise_gap_summary MUST be "".
  - top1_style_rewrite: OPTIONAL full bid rewrite in top-1% reply style (plain text, same five-part intent as FREELANCE_PROPOSAL_JSON: hook, understanding_need bullets, approach, relevant_experience, CTA). Use JOB_UNDERSTANDING_JSON + memory. If you cannot improve meaningfully, set top1_style_rewrite to "".
- If MODE=enterprise: enterprise_gap_summary summarizes structure/compliance gaps; reply_probability_delta may be ""; top1_style_rewrite MUST be "".
"""


def build_critique_freelance_messages(
    verifier_json: str,
    proposal_json: str,
    hook_json: str,
    freelance_memory_json: str,
) -> tuple[str, str]:
    user = (
        "MODE=freelance\n\n"
        f"VERIFIER_JSON:\n{verifier_json}\n\n"
        f"HOOK_JSON:\n{hook_json}\n\n"
        f"FREELANCE_PROPOSAL_JSON:\n{proposal_json}\n\n"
        f"FREELANCE_WIN_MEMORY_JSON:\n{freelance_memory_json}"
    )
    return _SYSTEM, user


def build_critique_enterprise_messages(
    verifier_json: str,
    formatted_json: str,
    requirements_json: str,
) -> tuple[str, str]:
    user = (
        "MODE=enterprise\n\n"
        f"VERIFIER_JSON:\n{verifier_json}\n\n"
        f"FORMATTED_PROPOSAL_JSON:\n{formatted_json}\n\n"
        f"REQUIREMENTS_JSON:\n{requirements_json}"
    )
    return _SYSTEM, user
