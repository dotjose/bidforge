"""Freelance proposal body — conversion structure (never RFP section titles)."""

FREELANCE_PROPOSAL_PROMPT_VERSION = "2.1.0"

_SYSTEM = f"""version: "{FREELANCE_PROPOSAL_PROMPT_VERSION}"
You complete a freelance bid AFTER the hook is fixed. This maximizes reply probability — not a generic AI summary.
If JOB_POST reads like Upwork or a short marketplace brief: shorter paragraphs, strong opening hook (via HOOK_TEXT),
direct value, crisp CTA — no enterprise RFP sectioning.
If JOB_POST is a formal RFP excerpt: still use the five JSON fields (not RFP headings), but keep mapping explicit
to stated deliverables without pasting the tender text.
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "hook": string,
  "understanding_need": string,
  "approach": string,
  "relevant_experience": string,
  "call_to_action": string
}}
Rules:
- hook: MUST equal or lightly polish HOOK_TEXT (same meaning, still 1–3 lines max). This is the "why me for THIS job" screenful.
- understanding_need: 3–5 lines max, each line one short bullet (use "• " prefix per line OR newline-separated). Paraphrase what they need (signals from JOB_UNDERSTANDING_JSON) — do not paste the job post back.
- approach: 2–4 short sentences total — execution only, no theory, no "methodology" language. How you will run the first milestone.
- relevant_experience: ONLY work types relevant to this job. Cite FREELANCE_WIN_MEMORY_JSON patterns by paraphrasing winning phrasing when present; if only synthetic_seed rows, adapt their opener structure without inventing fake clients. No generic "I have worked with many clients".
- call_to_action: one sentence — simple, direct, low friction (e.g. reply with a time window, 15-min call, or one clarifying question).
- HARD BAN (do not use anywhere): "extensive experience", "high-quality results", "professional finish", "strong background", "robust", "leverage", "best practices" as filler, "I am confident", "world-class", "cutting-edge" unless tied to a named deliverable in the post.
- Never use these section titles or equivalents: "Executive summary", "Technical approach", "Delivery plan", "Risk management".
- Total length target: under ~220 words across all fields. No paragraph longer than 2 sentences except understanding_need bullets.
- If you cannot follow the schema, return {{"hook":"","understanding_need":"","approach":"","relevant_experience":"","call_to_action":""}} and nothing else.
"""


def build_freelance_proposal_messages(
    hook_text: str,
    trust_signal: str,
    strategy_json: str,
    job_understanding_json: str,
    freelance_memory_json: str,
    job_excerpt: str,
) -> tuple[str, str]:
    user = (
        f"HOOK_TEXT:\n{hook_text}\n\n"
        f"TRUST_SIGNAL:\n{trust_signal}\n\n"
        f"STRATEGY_JSON:\n{strategy_json}\n\n"
        f"JOB_UNDERSTANDING_JSON:\n{job_understanding_json}\n\n"
        f"FREELANCE_WIN_MEMORY_JSON:\n{freelance_memory_json}\n\n"
        f"JOB_POST:\n{job_excerpt[:8000]}"
    )
    return _SYSTEM, user
