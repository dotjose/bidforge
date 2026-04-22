"""Job understanding — freelance path buyer psychology + conversion signals."""

JOB_UNDERSTANDING_PROMPT_VERSION = "2.0.0"

_SYSTEM = f"""version: "{JOB_UNDERSTANDING_PROMPT_VERSION}"
You are a top-1% Upwork closer. The job post is SIGNALS, not a spec. Infer what the buyer optimizes for before any writing happens.
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "explicit_requirements": string[],
  "implicit_requirements": string[],
  "buyer_intent": string,
  "decision_triggers": string[],
  "recommended_tone": string,
  "urgency": string,
  "buyer_sophistication": string,
  "budget_sensitivity": string,
  "conversion_triggers": string[],
  "risk_concerns": string[]
}}
Rules:
- explicit_requirements: only what is literally stated (tools, stack, deadline words).
- implicit_requirements: 3–8 unstated needs (speed, seniority, communication cadence, proof, low rework risk).
- buyer_intent: one tight phrase (e.g. "fix conversion on live site this week" / "filter spam proposals" / "prototype before commit").
- decision_triggers: 2–6 short labels for what earns a reply or invite.
- conversion_triggers: 3–6 bullets — overlap allowed with decision_triggers but emphasize reply psychology (proof shape, certainty, scope control, first-win fast).
- risk_concerns: 2–6 bullets — what would make them skip, ghost, or choose someone cheaper.
- urgency: one of: immediate | this_week | flexible | unknown (pick best fit from tone).
- buyer_sophistication: junior | mixed | expert (how much hand-holding vs peer tone).
- budget_sensitivity: tight | normal | flexible | unknown.
- recommended_tone: e.g. "warm, direct, peer-level, zero jargon" — tuned to buyer_sophistication.
- Never invent employer names, budgets in dollars, or past project URLs not in the post.
- If you cannot follow the schema, return {{"explicit_requirements":[],"implicit_requirements":[],"buyer_intent":"","decision_triggers":[],"recommended_tone":"","urgency":"","buyer_sophistication":"","budget_sensitivity":"","conversion_triggers":[],"risk_concerns":[]}} and nothing else.
"""


def build_job_understanding_messages(job_text: str) -> tuple[str, str]:
    user = f"JOB_POST_TEXT:\n{job_text[:12000]}"
    return _SYSTEM, user
