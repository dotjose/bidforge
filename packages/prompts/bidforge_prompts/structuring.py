"""Requirement structuring — REQ matrix for downstream mapping."""

STRUCTURING_PROMPT_VERSION = "2.0.0"

_SYSTEM = f"""version: "{STRUCTURING_PROMPT_VERSION}"
You convert extracted requirements JSON into a typed coverage matrix for proposal traceability.
Output ONLY a single JSON object (no markdown fences, no commentary).
Shape (exact keys):
{{
  "requirements": [
    {{
      "id": string,
      "type": "deliverable" | "compliance" | "timeline",
      "description": string,
      "mandatory": boolean,
      "source": string
    }}
  ]
}}
Rules:
- Emit one object per atomic requirement derived from the input `requirements`, `constraints`,
  `compliance_items`, and explicit schedule language in the original brief.
- id must be REQ_1, REQ_2, ... sequential.
- type: deliverable for scope/work; compliance for certifications/legal; timeline for dates/milestones.
- description: single clear statement the proposal must satisfy.
- source: short provenance label (e.g. "Scope of Work", "Compliance", "Schedule").
- If input has no requirements, return {{"requirements":[]}}.
"""


def build_structuring_messages(requirements_json: str) -> tuple[str, str]:
    user = f"REQUIREMENTS_JSON:\n{requirements_json}"
    return _SYSTEM, user
