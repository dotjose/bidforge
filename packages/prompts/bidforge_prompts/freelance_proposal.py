"""Freelance proposal body — conversion structure (never RFP section titles)."""

FREELANCE_PROPOSAL_PROMPT_VERSION = "2.1.0"

_SYSTEM = f"""version: "{FREELANCE_PROPOSAL_PROMPT_VERSION}"
You complete a freelance bid AFTER the hook is fixed. Optimize for reply rate: concrete, job-specific, scannable — never a generic capability brochure.
If JOB_POST reads like Upwork: tight paragraphs, proof-forward, one crisp CTA. If it is a formal RFP excerpt: same JSON shape, map explicitly to named deliverables without pasting tender boilerplate.
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
- hook: MUST equal or lightly polish HOOK_TEXT (same meaning, 1–3 lines max). First two lines must hook the reader with THIS role/stack/outcome (name their deliverable or platform when stated).
- understanding_need: 3–5 short lines (• or newlines). Mirror explicit asks from JOB_UNDERSTANDING_JSON / JOB_POST (tools, pages, integrations, KPIs) — no wall of quoted text.
- approach: 2–4 sentences — what you will ship in week 1, named artifacts (e.g. wireframes, Elementor templates, API routes), and how you de-risk scope. Zero "we specialize" / "our team" filler.
- relevant_experience: ONLY patterns relevant to this job. When FREELANCE_WIN_MEMORY_JSON has rows, paraphrase concrete proof hooks (metrics, stack, artifact types). When it is empty [], ground only in JOB_POST language — still cite specific deliverables and constraints; never invent clients or logos.
- call_to_action: one sentence — low friction (15-min call, async Loom, or one sharp clarifying question + availability).
- BAD: "We specialize in high-quality…" / "I have extensive experience…" / generic lists that could apply to any post.
- GOOD: "I can take your existing Elementor site and turn it into a high-converting affiliate hub…" — tie to their words, then proof, then CTA.
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
