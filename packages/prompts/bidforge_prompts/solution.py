"""Solution node — blueprint (execution truth) + strategy (positioning)."""

SOLUTION_BLUEPRINT_PROMPT_VERSION = "1.0.0"

_BLUEPRINT_SYSTEM = f"""version: "{SOLUTION_BLUEPRINT_PROMPT_VERSION}"
You design HOW the work is executed. You do NOT write proposal prose, hooks, or positioning. You do NOT summarize the RFP or job text.

You are the ONLY system component allowed to define execution logic. Downstream nodes consume your JSON verbatim.

Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "tasks": string[],
  "timeline": string[],
  "deliverables": string[]
}}

Rules:
- tasks: minimum 4 items, maximum 14. Imperative lines (verb-first). Name concrete systems/APIs/platforms
  when they appear in STRUCTURED_REQUIREMENTS_JSON or JOB_SIGNALS_JSON (else infer plausible stack from domain).
- timeline: minimum 2 lines, maximum 10. Each line MUST include Week, Day, or Phase with a timebox.
- deliverables: minimum 3 items, maximum 12. Named artifacts the buyer receives (repos, runbooks, dashboards, etc.).
- Internal consistency: every deliverable should trace to at least one task; timeline should cover the task sequence.
- If STRUCTURED_REQUIREMENTS_JSON is thin, still satisfy minimum counts using conservative, credible planning language.
- If you cannot satisfy minimum counts, return empty arrays (the pipeline will fail and retry upstream).
"""


def build_solution_blueprint_messages(
    requirements_json: str,
    rag_context_json: str,
    *,
    job_signals_json: str = "{{}}",
) -> tuple[str, str]:
    user = (
        f"STRUCTURED_REQUIREMENTS_JSON:\n{requirements_json}\n\n"
        f"JOB_SIGNALS_JSON:\n{job_signals_json}\n\n"
        f"RAG_CONTEXT_JSON:\n{rag_context_json}"
    )
    return _BLUEPRINT_SYSTEM, user


SOLUTION_STRATEGY_ENTERPRISE_PROMPT_VERSION = "2.1.0"

_STRATEGY_ENT_SYSTEM = f"""version: "{SOLUTION_STRATEGY_ENTERPRISE_PROMPT_VERSION}"
You are a capture manager. You receive STRUCTURED_REQUIREMENTS_JSON (includes requirement_matrix)
and PROPOSAL_MEMORY_JSON (RAG).
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
- SOLUTION_BLUEPRINT_JSON is authoritative execution design from the solution blueprint step. Align positioning and
  win_themes with those tasks/deliverables; do not invent a conflicting execution story.
- `freelance_hook_strategy` MUST be an empty string for enterprise / RFP proposals.
- If PROPOSAL_MEMORY_JSON has any non-empty similar_proposals, win_patterns, or methodology_blocks:
  - `strategy` MUST explicitly reference concrete memory (titles, pattern labels, or methodology titles). Generic filler is invalid.
  - `based_on` MUST list at least one memory identifier (e.g. proposal id, pattern id, or methodology title) you relied on.
- If PROPOSAL_MEMORY_JSON is completely empty (no usable chunks): set strategy to explain buyer-aligned approach without inventing past wins; based_on may be empty.
- Keep win_themes to at most 5 items.
- If you cannot follow the schema, return {{"strategy":"","based_on":[],"positioning":"","win_themes":[],"differentiators":[],"response_tone":"","freelance_hook_strategy":""}} and nothing else.
"""


def build_solution_strategy_enterprise_messages(
    requirements_json: str,
    rag_context_json: str,
    *,
    solution_blueprint_json: str = "{}",
    workspace_preferences: str = "",
) -> tuple[str, str]:
    extra = ""
    if workspace_preferences.strip():
        extra = f"WORKSPACE_PREFERENCES:\n{workspace_preferences.strip()}\n\n"
    user = (
        f"{extra}"
        f"STRUCTURED_REQUIREMENTS_JSON:\n{requirements_json}\n\n"
        f"SOLUTION_BLUEPRINT_JSON:\n{solution_blueprint_json}\n\n"
        f"PROPOSAL_MEMORY_JSON:\n{rag_context_json}"
    )
    return _STRATEGY_ENT_SYSTEM, user


SOLUTION_STRATEGY_JOB_PROMPT_VERSION = "3.0.0"

_STRATEGY_JOB_SYSTEM = f"""version: "{SOLUTION_STRATEGY_JOB_PROMPT_VERSION}"
You set positioning for THIS job (conversion system, not copy for the final proposal).
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
- SOLUTION_BLUEPRINT_JSON is already fixed (tasks/timeline/deliverables). Your positioning MUST be consistent
  with that execution plan — do not imply a different delivery story.
- `positioning`: one or two sentences — "why us for THIS job" without generic claims.
- `strategy`: 2–4 sentences: buyer outcome, risk removed, proof direction; tie to JOB_SIGNALS_JSON.
- `freelance_hook_strategy`: short note for the proposal node on tone and proof emphasis (NOT opening lines or hook copy).
- `based_on`: ids/labels from FREELANCE_WIN_MEMORY_JSON you reuse for positioning. If empty, leave [].
- `win_themes`: max 4 short phrases.
- `differentiators`: max 4 items provable from job + memory.
- Ban: "we are excited", "we specialize in", "proven track record", "extensive experience", "leverage", "robust", "comprehensive".
- If you cannot follow the schema, return {{"strategy":"","based_on":[],"positioning":"","win_themes":[],"differentiators":[],"response_tone":"","freelance_hook_strategy":""}} and nothing else.
"""


def build_solution_strategy_job_messages(
    job_signals_json: str,
    job_excerpt: str,
    freelance_memory_json: str,
    *,
    solution_blueprint_json: str = "{}",
) -> tuple[str, str]:
    user = (
        f"JOB_SIGNALS_JSON:\n{job_signals_json}\n\n"
        f"SOLUTION_BLUEPRINT_JSON:\n{solution_blueprint_json}\n\n"
        f"JOB_POST_EXCERPT:\n{job_excerpt[:8000]}\n\n"
        f"FREELANCE_WIN_MEMORY_JSON:\n{freelance_memory_json}"
    )
    return _STRATEGY_JOB_SYSTEM, user
