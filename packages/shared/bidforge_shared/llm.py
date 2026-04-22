from __future__ import annotations

import json
from typing import Protocol, TypeVar, runtime_checkable

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from bidforge_shared.errors import LLMTransportError, PipelineStepError

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """Strict JSON completion — no chat transcripts exposed."""

    def complete_json(self, *, step: str, system: str, user: str, response_model: type[T]) -> T: ...

    def generate_json(self, prompt: str, response_model: type[T]) -> T: ...


class OpenAILLM:
    """OpenAI chat completions with JSON object mode + Pydantic validation."""

    def __init__(self, *, api_key: str, model: str = "gpt-4o-mini", timeout_s: float = 120.0) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAILLM")
        self._client = OpenAI(api_key=api_key, timeout=timeout_s)
        self._model = model

    def complete_json(self, *, step: str, system: str, user: str, response_model: type[T]) -> T:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as e:  # noqa: BLE001 — surfaced to orchestrator
            raise LLMTransportError(step, str(e)) from e

        choice = resp.choices[0].message.content
        if not choice:
            raise PipelineStepError(step, "Empty model response", partial={})
        raw = choice.strip()
        try:
            return response_model.model_validate_json(raw)
        except ValidationError as e:
            try:
                data = json.loads(raw)
                return response_model.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as e2:
                raise PipelineStepError(
                    step,
                    f"Invalid JSON for {response_model.__name__}: {e}",
                    partial={"raw": raw[:2000]},
                ) from e2

    def generate_json(self, prompt: str, response_model: type[T]) -> T:
        system = (
            "Return a single JSON object only. No markdown fences, no natural language outside JSON. "
            "If the schema cannot be satisfied, return a JSON object with only empty strings and empty arrays."
        )
        return self.complete_json(step="generate_json", system=system, user=prompt, response_model=response_model)


class StubLLM:
    """Test double — inject canned responses by step name."""

    def __init__(self, responses: dict[str, BaseModel] | None = None) -> None:
        self._responses = responses or {}

    def register(self, step: str, model: BaseModel) -> None:
        self._responses[step] = model

    def complete_json(self, *, step: str, system: str, user: str, response_model: type[T]) -> T:
        hit = self._responses.get(step)
        if hit is not None and isinstance(hit, response_model):
            return hit
        if hit is not None:
            return response_model.model_validate(hit.model_dump())
        raise PipelineStepError(step, f"No stub response registered for step={step!r}")

    def generate_json(self, prompt: str, response_model: type[T]) -> T:
        return self.complete_json(
            step="generate_json",
            system="stub",
            user=prompt,
            response_model=response_model,
        )
