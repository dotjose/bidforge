"""OpenRouter-backed chat completions with JSON mode, fallback models, and retries."""

from __future__ import annotations

import json
import random
import time
from typing import Any, TypeVar

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from bidforge_shared.errors import LLMTransportError, PipelineStepError

T = TypeVar("T", bound=BaseModel)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterLLM:
    """OpenRouter (OpenAI-compatible API) with primary/fallback models and JSON validation."""

    def __init__(
        self,
        *,
        api_key: str,
        primary_model: str,
        fallback_model: str,
        embedding_model: str = "openai/text-embedding-3-small",
        timeout_s: float = 30.0,
        max_retries: int = 3,
        http_referer: str = "https://bidforge.app",
        app_title: str = "BidForge API",
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterLLM")
        self._client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            timeout=timeout_s,
            default_headers={
                "HTTP-Referer": http_referer,
                "X-Title": app_title,
            },
        )
        self._primary = primary_model
        self._fallback = fallback_model
        self._embedding_model = embedding_model
        self._timeout = timeout_s
        self._max_retries = max(1, max_retries)
        self.last_model_name: str | None = None
        self.last_usage: dict[str, int] | None = None

    def _sleep_backoff(self, attempt: int) -> None:
        base = 0.4 * (2**attempt)
        jitter = random.uniform(0, 0.25)
        time.sleep(min(base + jitter, 6.0))

    def _chat_once(self, *, step: str, model: str, system: str, user: str) -> tuple[str, dict[str, Any]]:
        last_err: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    timeout=self._timeout,
                )
            except (APITimeoutError, APIConnectionError, RateLimitError) as e:
                last_err = e
                if attempt + 1 < self._max_retries:
                    self._sleep_backoff(attempt)
                continue
            except Exception as e:  # noqa: BLE001
                raise LLMTransportError(step, str(e)) from e

            choice = resp.choices[0].message.content
            if not choice:
                raise PipelineStepError(step, "Empty model response", partial={})
            usage: dict[str, int] = {}
            if resp.usage is not None:
                usage = {
                    "prompt_tokens": int(resp.usage.prompt_tokens or 0),
                    "completion_tokens": int(resp.usage.completion_tokens or 0),
                    "total_tokens": int(resp.usage.total_tokens or 0),
                }
            self.last_model_name = model
            self.last_usage = usage or None
            return choice.strip(), usage

        raise LLMTransportError(step, f"Retries exhausted: {last_err!s}")

    def _parse_json(self, step: str, raw: str, response_model: type[T]) -> T:
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

    def complete_json(self, *, step: str, system: str, user: str, response_model: type[T]) -> T:
        models_to_try = [self._primary, self._fallback]
        seen: set[str] = set()
        last_transport: LLMTransportError | None = None
        for model in models_to_try:
            if not model or model in seen:
                continue
            seen.add(model)
            try:
                raw, _usage = self._chat_once(step=step, model=model, system=system, user=user)
                return self._parse_json(step, raw, response_model)
            except LLMTransportError as e:
                last_transport = e
                continue
        if last_transport:
            raise LLMTransportError(step, str(last_transport)) from last_transport
        raise LLMTransportError(step, "No OpenRouter models configured")

    def generate_json(self, prompt: str, response_model: type[T]) -> T:
        system = (
            "Return a single JSON object only. No markdown fences, no natural language outside JSON. "
            "If the schema cannot be satisfied, return a JSON object with only empty strings and empty arrays."
        )
        return self.complete_json(step="generate_json", system=system, user=prompt, response_model=response_model)

    def embed_text(self, text: str, *, max_chars: int = 8000) -> list[float]:
        chunk = (text or "")[:max_chars]
        try:
            resp = self._client.embeddings.create(
                model=self._embedding_model,
                input=chunk,
                timeout=min(self._timeout, 45.0),
            )
        except Exception as e:  # noqa: BLE001
            raise LLMTransportError("embedding", str(e)) from e
        vec = resp.data[0].embedding
        self.last_model_name = self._embedding_model
        if resp.usage is not None:
            self.last_usage = {
                "prompt_tokens": int(resp.usage.prompt_tokens or 0),
                "completion_tokens": int(resp.usage.completion_tokens or 0),
                "total_tokens": int(resp.usage.total_tokens or 0),
            }
        return list(vec)
