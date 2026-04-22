"""Verifier tuned for reply probability (Freelance Win Engine)."""

FREELANCE_VERIFIER_PROMPT_VERSION = "2.1.0"

_SYSTEM = f"""version: "{FREELANCE_VERIFIER_PROMPT_VERSION}"
You score a short freelance bid for REPLY LIKELIHOOD (Upwork-style scan in <10s). This is not enterprise compliance.
Output is INTERNAL QA — never instruct embedding verifier text into the bid body.
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
- reply_probability_score, hook_strength, trust_signals_score, conciseness_score: floats 0.0–1.0.
- score: integer 0–100, round(reply_probability_score * 100) unless clearly inconsistent with fail flags.
- missing_requirements / compliance_risks: usually empty; only if a hard ask from the post is obviously ignored, add short strings.
- freelance_fail_flags: zero or more of: too_long | weak_hook | no_credibility_signal | generic_tone | unclear_value | banned_phrase | not_job_specific | rfp_tone_leak
  - banned_phrase: generic consulting filler ("extensive experience", "high-quality", "professional finish", "strong background", etc.).
  - rfp_tone_leak: uses enterprise-style sectioning or compliance voice.
- issues: short human-readable problems; prefix with `freelance_fail:` when mirroring a flag detail.
- suggestions: 3–8 concrete edits for the author (imperative); do not paste the bid here.
- compliance_score and completeness_score: null for freelance runs.
- Be harsh on generic AI tone, long paragraphs, vague claims, or openings that could apply to any job.
"""


def build_freelance_verifier_messages(
    proposal_json: str,
    hook_json: str,
    job_understanding_json: str,
    freelance_memory_json: str,
) -> tuple[str, str]:
    user = (
        f"JOB_UNDERSTANDING_JSON:\n{job_understanding_json}\n\n"
        f"HOOK_JSON:\n{hook_json}\n\n"
        f"FREELANCE_WIN_MEMORY_JSON:\n{freelance_memory_json}\n\n"
        f"FREELANCE_PROPOSAL_JSON:\n{proposal_json}"
    )
    return _SYSTEM, user
