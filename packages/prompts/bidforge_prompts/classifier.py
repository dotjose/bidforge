"""Input type classifier — routes enterprise vs freelance brains."""

CLASSIFIER_PROMPT_VERSION = "1.0.0"

_SYSTEM = f"""version: "{CLASSIFIER_PROMPT_VERSION}"
You classify raw opportunity text for a dual-brain proposal system.
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "input_type": "rfp" | "job_post" | "upwork" | "freelancer",
  "recommended_pipeline": "enterprise" | "freelance",
  "rationale": string
}}
Rules:
- `rfp`: formal tender, compliance language, evaluation criteria, sections, due dates, legal/attachment tone → enterprise.
- `upwork` / `freelancer`: platform-specific layout (connects, milestones, job success score, fixed/hourly badges) → freelance.
- `job_post`: short informal hiring post without full RFP structure → usually freelance; if it clearly mirrors a formal procurement doc, choose enterprise.
- `recommended_pipeline`: enterprise for structured RFP work; freelance for conversion-first short replies (Upwork/Freelancer/typical job boards).
- rationale: one short sentence.
"""


def build_classifier_messages(rfp_excerpt: str) -> tuple[str, str]:
    user = f"RAW_INPUT_TEXT:\n{rfp_excerpt}"
    return _SYSTEM, user
