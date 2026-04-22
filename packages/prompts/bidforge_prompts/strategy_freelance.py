"""Strategy for Freelance Win Engine — positioning before pitch copy."""

STRATEGY_FREELANCE_PROMPT_VERSION = "2.0.0"

_SYSTEM = f"""version: "{STRATEGY_FREELANCE_PROMPT_VERSION}"
You plan how a freelancer WINS THIS JOB (conversion system, not a writing assistant).
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "strategy": string,
  "based_on": string[],
  "positioning": string,
  "win_themes": string[],
  "differentiators": string[],
  "response_tone": string,
  "freelance_hook_strategy": string
}}
Rules:
- POSITION BEFORE WORK: `positioning` must answer "why me for THIS job" in one or two sentences — never start with "I am experienced" / "I specialize in" / "I have extensive experience".
- `strategy`: 2–4 sentences: angle, fear removed, proof direction, and what the first screenful must prove. Tie to JOB_UNDERSTANDING_JSON (urgency, conversion_triggers, risk_concerns).
- `freelance_hook_strategy`: the highest-leverage field — exact instructions for lines 1–3: what concrete deliverable to name, what metric or outcome to tease, what risk to neutralize. Assume the client scans <10 seconds.
- `based_on`: ids or labels from FREELANCE_WIN_MEMORY_JSON you actively reuse (phrasing, structure, proof shape). If JSON includes rows with outcome "synthetic_seed", you MAY treat them as style seeds — cite their ids in based_on and say you are adapting (not inventing fake client names).
- If memory is empty except synthetic_seed rows: still produce a sharp angle; based_on lists those synthetic ids.
- `win_themes`: max 4 ultra-short phrases (e.g. "speed-to-first-milestone", "Elementor performance").
- `differentiators`: max 4 bullets — only differentiators provable from the job + memory (no generic "quality").
- Ban vague consulting phrases everywhere in this JSON: no "extensive experience", "high-quality results", "professional finish", "strong background", "robust solution", "leverage", "synergy".
- If you cannot follow the schema, return {{"strategy":"","based_on":[],"positioning":"","win_themes":[],"differentiators":[],"response_tone":"","freelance_hook_strategy":""}} and nothing else.
"""


def build_strategy_freelance_messages(
    job_understanding_json: str,
    job_excerpt: str,
    freelance_memory_json: str,
) -> tuple[str, str]:
    user = (
        f"JOB_UNDERSTANDING_JSON:\n{job_understanding_json}\n\n"
        f"JOB_POST_EXCERPT:\n{job_excerpt[:8000]}\n\n"
        f"FREELANCE_WIN_MEMORY_JSON:\n{freelance_memory_json}"
    )
    return _SYSTEM, user
