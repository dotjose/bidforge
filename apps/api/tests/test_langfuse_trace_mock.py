from __future__ import annotations

from typing import Any

import pytest

from app.pipeline.orchestrator import execute_proposal_pipeline

from tests.conftest import stub_llm_happy_path


class _DummyObs:
    def __init__(self, lf: _DummyLangfuse, trace_id: str | None) -> None:
        self._lf = lf
        self.trace_id = trace_id or "trace-unknown"

    def update(self, **kwargs: Any) -> None:
        return None

    def score_trace(
        self,
        *,
        name: str,
        value: float,
        data_type: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._lf.create_score(
            name=name,
            value=value,
            trace_id=self.trace_id,
            data_type=data_type or "NUMERIC",
            metadata=metadata or {},
        )

    def __enter__(self) -> _DummyObs:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class _DummyLangfuse:
    def __init__(self) -> None:
        self.scores: list[dict[str, Any]] = []

    def start_as_current_observation(self, **kwargs: Any) -> _DummyObs:
        tc = kwargs.get("trace_context")
        tid: str | None = None
        if tc is not None and hasattr(tc, "trace_id"):
            tid = str(tc.trace_id)
        return _DummyObs(self, tid)

    def flush(self) -> None:
        return None

    def create_score(self, **kwargs: Any) -> None:
        self.scores.append(kwargs)


def test_proposal_trace_scores_when_langfuse_present(
    monkeypatch: pytest.MonkeyPatch,
    sample_rfp: str,
) -> None:
    dummy = _DummyLangfuse()

    def _fake() -> _DummyLangfuse:
        return dummy

    monkeypatch.setattr("app.pipeline.orchestrator.get_langfuse_client", _fake)
    llm = stub_llm_happy_path()
    execute_proposal_pipeline(sample_rfp, "clerk-user-langfuse", llm=llm)
    assert dummy.scores, "score_trace should invoke create_score"
    names = {s.get("name") for s in dummy.scores}
    for expected in (
        "proposal_quality",
        "workflow_latency_ms",
        "issue_count",
        "compliance_risk_count",
        "memory_grounded",
        "memory_chunk_count",
        "memory_alignment_score",
        "degradation_level",
    ):
        assert expected in names
