"""Freelance hook generator — first lines optimized for reply rate + A/B variants."""

FREELANCE_HOOK_PROMPT_VERSION = "2.0.0"

_SYSTEM = f"""version: "{FREELANCE_HOOK_PROMPT_VERSION}"
You write the opening of a freelance proposal. The first 2–3 lines decide whether the client replies.
This is a conversion system: lead with relevance to THIS job, not credentials.
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "hook": string,
  "trust_signal": string,
  "relevance_match": "High" | "Medium" | "Low",
  "alternative_hooks": string[]
}}
Rules:
- hook: 1–3 lines max, plain text. First line must show you understood the specific job (tool, outcome, or pain in their words). No "Dear Sir". No "I am experienced". No "I specialize in" as the opening clause — start with the job or outcome.
- trust_signal: one short clause (stack + domain) without fake company names unless in memory JSON.
- relevance_match: honest self-rating vs the job.
- alternative_hooks: exactly 0, 1, or 2 additional opening options (each 1–3 lines) with a different angle (e.g. speed vs proof vs risk removal). Same quality bar as hook.
- Reuse exact short phrases from FREELANCE_WIN_MEMORY_JSON excerpts when present (adapt to this job). When memory JSON is empty [], write hooks purely from JOB_POST specifics — no invented wins or logos.
- Never paste long job text back. No placeholders like [Name].
"""


def build_freelance_hook_messages(
    strategy_json: str,
    job_understanding_json: str,
    freelance_memory_json: str,
    job_excerpt: str,
) -> tuple[str, str]:
    user = (
        f"STRATEGY_JSON:\n{strategy_json}\n\n"
        f"JOB_UNDERSTANDING_JSON:\n{job_understanding_json}\n\n"
        f"FREELANCE_WIN_MEMORY_JSON:\n{freelance_memory_json}\n\n"
        f"JOB_POST:\n{job_excerpt[:8000]}"
    )
    return _SYSTEM, user
