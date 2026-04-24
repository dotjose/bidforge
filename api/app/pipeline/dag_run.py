"""Deterministic DAG node executor — contracts, hashes, retries, cache, Supabase event append."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from bidforge_shared import LLMClient

from app.integrations.proposal_store import (
    backfill_proposal_events_proposal_id,
    fetch_proposal_node_cache,
    insert_proposal_dag_event,
    upsert_proposal_node_cache,
)
from app.pipeline.errors import FailedPipeline

log = logging.getLogger(__name__)

PIPELINE_VERSION = "DAG_v1"
MAX_NODE_RETRIES = 2  # two retries after first attempt (three total tries)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _llm_meta(llm: LLMClient) -> tuple[str, dict[str, Any]]:
    model = str(getattr(llm, "last_model_name", None) or "")
    usage = getattr(llm, "last_usage", None)
    return model, usage if isinstance(usage, dict) else {}


def composite_job_intel_version_enterprise() -> str:
    from bidforge_prompts.job_intel import JOB_INTEL_EXTRACT_PROMPT_VERSION, JOB_INTEL_MATRIX_PROMPT_VERSION

    return f"{PIPELINE_VERSION}:job_intel:ent:{JOB_INTEL_EXTRACT_PROMPT_VERSION}:{JOB_INTEL_MATRIX_PROMPT_VERSION}:emb_v1"


def composite_job_intel_version_freelance() -> str:
    from bidforge_prompts.job_intel import JOB_INTEL_SIGNALS_PROMPT_VERSION

    return f"{PIPELINE_VERSION}:job_intel:job:{JOB_INTEL_SIGNALS_PROMPT_VERSION}:emb_v1"


def composite_solution_version_enterprise() -> str:
    from bidforge_prompts.solution import (
        SOLUTION_BLUEPRINT_PROMPT_VERSION,
        SOLUTION_STRATEGY_ENTERPRISE_PROMPT_VERSION,
    )

    return f"{PIPELINE_VERSION}:solution:ent:{SOLUTION_BLUEPRINT_PROMPT_VERSION}:{SOLUTION_STRATEGY_ENTERPRISE_PROMPT_VERSION}"


def composite_solution_version_freelance() -> str:
    from bidforge_prompts.solution import (
        SOLUTION_BLUEPRINT_PROMPT_VERSION,
        SOLUTION_STRATEGY_JOB_PROMPT_VERSION,
    )

    return f"{PIPELINE_VERSION}:solution:job:{SOLUTION_BLUEPRINT_PROMPT_VERSION}:{SOLUTION_STRATEGY_JOB_PROMPT_VERSION}"


def composite_verifier_version_enterprise() -> str:
    from bidforge_prompts.verifier import VERIFIER_ENTERPRISE_PROMPT_VERSION

    return f"{PIPELINE_VERSION}:verifier:ent:{VERIFIER_ENTERPRISE_PROMPT_VERSION}"


def composite_verifier_version_freelance() -> str:
    from bidforge_prompts.verifier import VERIFIER_JOB_PROMPT_VERSION

    return f"{PIPELINE_VERSION}:verifier:job:{VERIFIER_JOB_PROMPT_VERSION}"


def default_node_prompt_versions() -> dict[str, str]:
    """Version strings for the 5-node DAG + summary metadata (no prompt text changes)."""
    from bidforge_prompts.proposal import PROPOSAL_PROMPT_VERSION
    from bidforge_prompts.router import ROUTER_PROMPT_VERSION

    return {
        "router": ROUTER_PROMPT_VERSION,
        "job_intel_enterprise": composite_job_intel_version_enterprise(),
        "job_intel_freelance": composite_job_intel_version_freelance(),
        "solution_enterprise": composite_solution_version_enterprise(),
        "solution_freelance": composite_solution_version_freelance(),
        "proposal": PROPOSAL_PROMPT_VERSION,
        "verifier_enterprise": composite_verifier_version_enterprise(),
        "verifier_freelance": composite_verifier_version_freelance(),
        "persist": PIPELINE_VERSION,
    }


class DagRun:
    """Per-trace DAG context: sequential parent links + append-only events + optional node cache."""

    def __init__(
        self,
        *,
        user_id: str,
        trace_id: str,
        pipeline_mode: str,
        llm: LLMClient,
        node_prompt_versions: dict[str, str] | None = None,
        fail_fast_events: bool = False,
    ) -> None:
        self.user_id = user_id
        self.trace_id = trace_id
        self.pipeline_mode = pipeline_mode
        self.llm = llm
        self.node_prompt_versions = dict(node_prompt_versions or default_node_prompt_versions())
        self._parent_node_id: str = ""
        self.source_rfp_plain: str = ""
        self.source_input_type: str = ""
        self._events_ok: bool = True
        self._fail_fast_events = bool(fail_fast_events)
        self._node_outputs: dict[str, Any] = {}

    @property
    def parent_node_id(self) -> str:
        return self._parent_node_id

    @property
    def node_versions(self) -> dict[str, str]:
        return dict(self.node_prompt_versions)

    def deterministic_version_id(self, node_id: str, prompt_version: str) -> str:
        return f"{PIPELINE_VERSION}:{node_id}:{prompt_version}"

    def record(
        self,
        node_id: str,
        prompt_version: str,
        input_obj: dict[str, Any],
        work: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute `work` with cache + retries; emit one proposal_events row; return output dict."""
        input_hash = stable_hash(_canonical_json(input_obj))
        cache_key = stable_hash(f"{node_id}|{input_hash}|{prompt_version}")
        det_ver = self.deterministic_version_id(node_id, prompt_version)

        cached = fetch_proposal_node_cache(cache_key)
        if isinstance(cached, dict) and cached:
            out = dict(cached)
            output_hash = stable_hash(_canonical_json(out))
            ok = self._emit(
                node_id=node_id,
                prompt_version=prompt_version,
                input_obj=input_obj,
                output_obj=out,
                input_hash=input_hash,
                output_hash=output_hash,
                cache_key=cache_key,
                det_ver=det_ver,
                retries=0,
                latency_ms=0,
                model_used="cache_hit",
                token_usage={},
                cached=True,
            )
            self._events_ok = self._events_ok and ok
            self._maybe_raise_event_failure()
            self._node_outputs[node_id] = out
            self._parent_node_id = node_id
            return out

        last_exc: BaseException | None = None
        out: dict[str, Any] | None = None
        attempts_used = 0
        latency_ms = 0
        for attempt in range(MAX_NODE_RETRIES + 1):
            attempts_used = attempt + 1
            t0 = time.perf_counter()
            try:
                out = work()
                latency_ms = int((time.perf_counter() - t0) * 1000)
                break
            except BaseException as e:  # noqa: BLE001
                last_exc = e
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if attempt < MAX_NODE_RETRIES:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise
        if out is None:
            raise RuntimeError("dag node produced no output") from last_exc

        output_hash = stable_hash(_canonical_json(out))
        model_used, token_usage = _llm_meta(self.llm)
        ok = self._emit(
            node_id=node_id,
            prompt_version=prompt_version,
            input_obj=input_obj,
            output_obj=out,
            input_hash=input_hash,
            output_hash=output_hash,
            cache_key=cache_key,
            det_ver=det_ver,
            retries=max(0, attempts_used - 1),
            latency_ms=latency_ms,
            model_used=model_used,
            token_usage=token_usage,
            cached=False,
        )
        self._events_ok = self._events_ok and ok
        self._maybe_raise_event_failure()
        cache_ok = upsert_proposal_node_cache(cache_key=cache_key, output_hash=output_hash, output=out)
        if not cache_ok and self._fail_fast_events:
            raise FailedPipeline(
                trace_id=self.trace_id,
                failed_step="proposal_node_cache",
                message="proposal_node_cache upsert failed (strict persistence)",
                partial={"node_id": node_id},
            )
        self._node_outputs[node_id] = out
        self._parent_node_id = node_id
        return out

    def _maybe_raise_event_failure(self) -> None:
        if self._fail_fast_events and not self._events_ok:
            raise FailedPipeline(
                trace_id=self.trace_id,
                failed_step="proposal_events",
                message="proposal_events insert failed (strict persistence)",
                partial={},
            )

    def _emit(
        self,
        *,
        node_id: str,
        prompt_version: str,
        input_obj: dict[str, Any],
        output_obj: dict[str, Any],
        input_hash: str,
        output_hash: str,
        cache_key: str,
        det_ver: str,
        retries: int,
        latency_ms: int,
        model_used: str,
        token_usage: dict[str, Any],
        cached: bool,
    ) -> bool:
        contract = {
            "id": node_id,
            "input": input_obj,
            "output": output_obj,
            "version": prompt_version,
            "cache_key": cache_key,
            "retries": retries,
            "latency_ms": latency_ms,
            "parent_node_id": self._parent_node_id,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "model_used": model_used,
            "token_usage": token_usage,
            "deterministic_version_id": det_ver,
            "pipeline_version": PIPELINE_VERSION,
            "cached": cached,
        }
        return insert_proposal_dag_event(
            user_id=self.user_id,
            trace_id=self.trace_id,
            proposal_id=None,
            record=contract,
        )

    def attach_proposal_id(self, proposal_id: str) -> None:
        backfill_proposal_events_proposal_id(trace_id=self.trace_id, proposal_id=proposal_id)

    def emit_run_summary(self, *, proposal_id: str, pipeline_mode: str) -> bool:
        """Single aggregate row for `proposal_events` (5-node outputs + metadata)."""
        body: dict[str, Any] = {
            "proposal_id": str(proposal_id),
            "pipeline_mode": pipeline_mode,
            "nodes": dict(self._node_outputs),
            "source_input_text": (self.source_rfp_plain or "")[:120_000],
            "input_type": (self.source_input_type or "")[:128],
            "version": PIPELINE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": "openrouter",
        }
        input_hash = stable_hash(_canonical_json({"trace_id": self.trace_id}))
        output_hash = stable_hash(_canonical_json(body))
        cache_key = stable_hash(f"dag_summary|{input_hash}|{PIPELINE_VERSION}")
        det_ver = f"{PIPELINE_VERSION}:dag_summary:v1"
        contract = {
            "id": "dag_summary",
            "input": {"trace_id": self.trace_id},
            "output": body,
            "version": PIPELINE_VERSION,
            "cache_key": cache_key,
            "retries": 0,
            "latency_ms": 0,
            "parent_node_id": self._parent_node_id,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "model_used": "openrouter",
            "token_usage": {},
            "deterministic_version_id": det_ver,
            "pipeline_version": PIPELINE_VERSION,
            "cached": False,
        }
        ok = insert_proposal_dag_event(
            user_id=self.user_id,
            trace_id=self.trace_id,
            proposal_id=str(proposal_id),
            record=contract,
        )
        self._events_ok = self._events_ok and ok
        self._maybe_raise_event_failure()
        return ok

    @property
    def events_emitted_ok(self) -> bool:
        return self._events_ok
