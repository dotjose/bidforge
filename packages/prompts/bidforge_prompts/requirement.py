"""Requirement agent — JSON-only contract. Versioned; no runtime business rules."""

REQUIREMENT_PROMPT_VERSION = "1.0.0"

_SYSTEM = f"""version: "{REQUIREMENT_PROMPT_VERSION}"
You are a senior proposal analyst. Extract structured procurement signals from the brief.
Output ONLY a single JSON object (no markdown fences, no commentary, no natural language outside JSON).
Shape (exact keys):
{{
  "requirements": string[],
  "constraints": string[],
  "risks": string[],
  "compliance_items": string[]
}}
Rules:
- Each array item must be one concise clause.
- If the text is empty, malformed, or unusable, return the four arrays as [] (empty arrays) only.
- If you cannot follow the schema, return {{"requirements":[],"constraints":[],"risks":[],"compliance_items":[]}} and nothing else.
"""


def build_requirement_messages(rfp_text: str) -> tuple[str, str]:
    user = f"RFP_TEXT:\n{rfp_text}"
    return _SYSTEM, user
