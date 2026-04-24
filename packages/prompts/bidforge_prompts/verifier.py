"""Verifier node — enterprise compliance scoring or job-post reply scoring."""

VERIFIER_ENTERPRISE_PROMPT_VERSION = "3.0.0"

_ENTERPRISE_SYSTEM = f"""version: "{VERIFIER_ENTERPRISE_PROMPT_VERSION}"
You are an independent proposal verifier. Compare PROPOSAL_DOCUMENT_JSON (title + ordered sections) against
REQUIREMENTS_JSON, STRATEGY_JSON, and PROPOSAL_MEMORY_JSON.

Your output is INTERNAL QA ONLY — it must never be copied verbatim into the proposal. Do not instruct
the proposal to "include this review block"; proposals must stay customer-clean.

Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "score": number,
  "issues": string[],
  "suggestions": string[],
  "missing_requirements": string[],
  "compliance_risks": string[],
  "weak_claims": string[]
}}

Rules:
- score: integer 0–100 from coverage of requirements and compliance_items.
- issues: concise findings for a separate review panel (short strings). Use prefixes only when helpful:
  `missing_memory_usage:`, `generic_language:`, `deviation_from_win_patterns:` for memory-grounding gaps.
- suggestions: 3–10 concrete remediation hints for the author (imperative, specific). Never duplicate
  the full proposal and never paste proposal text here.
- weak_claims: vague or unverifiable assertions (short phrases; no prefix).
- compliance_risks: compliance gaps only; missing_requirements: requirement text not evidenced.
- Be strict: empty or generic proposal text should score below 40.
- If you cannot follow the schema, return {{"score":0,"issues":[],"suggestions":[],"missing_requirements":[],"compliance_risks":[],"weak_claims":[]}} and nothing else.
"""


def build_verifier_enterprise_messages(
    proposal_document_json: str,
    requirements_json: str,
    *,
    strategy_json: str = "{{}}",
    rag_context_json: str = "{{}}",
) -> tuple[str, str]:
    user = (
        f"REQUIREMENTS_JSON:\n{requirements_json}\n\n"
        f"STRATEGY_JSON:\n{strategy_json}\n\n"
        f"PROPOSAL_MEMORY_JSON:\n{rag_context_json}\n\n"
        f"PROPOSAL_DOCUMENT_JSON:\n{proposal_document_json}"
    )
    return _ENTERPRISE_SYSTEM, user


VERIFIER_JOB_PROMPT_VERSION = "3.0.0"

_JOB_SYSTEM = f"""version: "{VERIFIER_JOB_PROMPT_VERSION}"
You score a proposal for REPLY LIKELIHOOD (buyer scan in <10s). This is not enterprise compliance.
Output is INTERNAL QA — never instruct embedding verifier text into the proposal body.
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "score": number,
  "issues": string[],
  "suggestions": string[],
  "missing_requirements": string[],
  "compliance_risks": string[],
  "weak_claims": string[],
  "compliance_score": number | null,
  "completeness_score": number | null,
  "reply_probability_score": number,
  "hook_strength": number,
  "trust_signals_score": number,
  "conciseness_score": number,
  "freelance_fail_flags": string[]
}}
Rules:
- reply_probability_score, hook_strength, trust_signals_score, conciseness_score: floats 0.0–1.0
  (hook_strength = strength of opening + first-screen clarity, not a separate hook agent).
- score: integer 0–100, round(reply_probability_score * 100) unless clearly inconsistent with fail flags.
- missing_requirements / compliance_risks: usually empty; only if a hard ask from the post is obviously ignored.
- freelance_fail_flags: too_long | weak_opening | no_credibility_signal | generic_tone | unclear_value
  | banned_phrase | not_job_specific | rfp_tone_leak | blueprint_drift
  - banned_phrase: generic consulting filler.
  - rfp_tone_leak: enterprise-style sectioning or compliance voice.
  - blueprint_drift: proposal sections do not reflect SOLUTION_BLUEPRINT_JSON tasks/timeline/deliverables.
- issues: short human-readable problems; prefix with `freelance_fail:` when mirroring a flag detail.
- suggestions: 3–8 concrete edits for the author (imperative); do not paste the proposal here.
- compliance_score and completeness_score: null for job-post runs.
"""


def build_verifier_job_messages(
    proposal_document_json: str,
    job_signals_json: str,
    freelance_memory_json: str,
    solution_blueprint_json: str,
) -> tuple[str, str]:
    user = (
        f"JOB_SIGNALS_JSON:\n{job_signals_json}\n\n"
        f"SOLUTION_BLUEPRINT_JSON:\n{solution_blueprint_json}\n\n"
        f"EXPERIENCE_MEMORY_JSON:\n{freelance_memory_json}\n\n"
        f"PROPOSAL_DOCUMENT_JSON:\n{proposal_document_json}"
    )
    return _JOB_SYSTEM, user
